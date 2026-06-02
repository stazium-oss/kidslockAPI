import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# File to persist today's usage (minutes used today)
USAGE_FILE = Path(__file__).parent / "usage.json"


def _load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_usage() -> dict:
    """Load today's session usage from disk."""
    today = date.today().isoformat()
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return data
        except Exception:
            pass
    # New day or corrupted file
    return {"date": today, "used_minutes": 0.0, "session_start": None}


def _save_usage(usage: dict):
    USAGE_FILE.write_text(json.dumps(usage, indent=2), encoding="utf-8")


class Scheduler:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._usage = _load_usage()

    def _config(self) -> dict:
        """Reload config fresh each time (supports live editing)."""
        return _load_config(self.config_path)

    def _today_name(self) -> str:
        return DAYS[datetime.now().weekday()]

    def _parse_time(self, t: str) -> datetime:
        """Parse 'HH:MM' into today's datetime."""
        h, m = map(int, t.split(":"))
        now = datetime.now()
        return now.replace(hour=h, minute=m, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_session_start(self):
        """Call when agent detects allowed session begins."""
        usage = _load_usage()
        if usage.get("session_start") is None:
            usage["session_start"] = datetime.now().isoformat()
            _save_usage(usage)
            self._usage = usage
            logger.info("Session start recorded")

    def record_session_end(self):
        """Call on lockout — accumulate used minutes."""
        usage = _load_usage()
        if usage.get("session_start"):
            start = datetime.fromisoformat(usage["session_start"])
            elapsed = (datetime.now() - start).total_seconds() / 60.0
            usage["used_minutes"] = usage.get("used_minutes", 0.0) + elapsed
            usage["session_start"] = None
            _save_usage(usage)
            self._usage = usage
            logger.info(f"Session ended. Used today: {usage['used_minutes']:.1f} min")

    def get_used_minutes_today(self) -> float:
        """Total minutes used today (including current running session)."""
        usage = _load_usage()
        total = usage.get("used_minutes", 0.0)
        if usage.get("session_start"):
            start = datetime.fromisoformat(usage["session_start"])
            total += (datetime.now() - start).total_seconds() / 60.0
        return total

    def is_allowed_now(self) -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Checks both allowed_hours window and daily_limit.
        """
        cfg = self._config()
        now = datetime.now()
        day = self._today_name()
        schedule = cfg.get("schedule", {})

        # --- Check allowed hours window ---
        hours = schedule.get("allowed_hours", {}).get(day)
        if hours:
            window_start = self._parse_time(hours["start"])
            window_end = self._parse_time(hours["end"])
            if not (window_start <= now <= window_end):
                return False, f"outside allowed hours ({hours['start']}–{hours['end']})"

        # --- Check daily limit ---
        limits = schedule.get("daily_limit_minutes", {})
        limit = limits.get(day)
        if limit is not None:
            used = self.get_used_minutes_today()
            if used >= limit:
                return False, f"daily limit reached ({used:.0f}/{limit} min)"

        return True, "ok"

    def minutes_left_in_window(self) -> Optional[float]:
        """Minutes until the allowed hours window closes (None if no window set)."""
        cfg = self._config()
        day = self._today_name()
        hours = cfg.get("schedule", {}).get("allowed_hours", {}).get(day)
        if not hours:
            return None
        window_end = self._parse_time(hours["end"])
        delta = (window_end - datetime.now()).total_seconds() / 60.0
        return max(0.0, delta)

    def minutes_left_in_limit(self) -> Optional[float]:
        """Minutes remaining from daily limit (None if no limit set)."""
        cfg = self._config()
        day = self._today_name()
        limits = cfg.get("schedule", {}).get("daily_limit_minutes", {})
        limit = limits.get(day)
        if limit is None:
            return None
        used = self.get_used_minutes_today()
        return max(0.0, limit - used)

    def minutes_until_lockout(self) -> Optional[float]:
        """
        How many minutes until the next forced lockout.
        Returns None if no lockout expected (or already should be locked).
        """
        allowed, _ = self.is_allowed_now()
        if not allowed:
            return 0.0

        candidates = []
        w = self.minutes_left_in_window()
        l = self.minutes_left_in_limit()
        if w is not None:
            candidates.append(w)
        if l is not None:
            candidates.append(l)

        return min(candidates) if candidates else None

    def status(self) -> dict:
        """Return a status dict for the API / web panel."""
        allowed, reason = self.is_allowed_now()
        cfg = self._config()
        day = self._today_name()
        schedule = cfg.get("schedule", {})

        hours = schedule.get("allowed_hours", {}).get(day, {})
        limit = schedule.get("daily_limit_minutes", {}).get(day)
        used = self.get_used_minutes_today()

        return {
            "allowed": allowed,
            "reason": reason,
            "day": day,
            "now": datetime.now().strftime("%H:%M:%S"),
            "allowed_window": hours,
            "daily_limit_minutes": limit,
            "used_minutes": round(used, 1),
            "minutes_until_lockout": self.minutes_until_lockout(),
        }
