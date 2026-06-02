"""
KidLock API routes.
All /api/* endpoints. Auth via Bearer JWT in Authorization header.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))
from scheduler import Scheduler, USAGE_FILE
from auth import verify_token, check_parent_password, create_token

CONFIG_PATH = Path(__file__).parent.parent / "agent" / "config.json"

router    = APIRouter(prefix="/api")
security  = HTTPBearer(auto_error=False)
scheduler = Scheduler(CONFIG_PATH)


# ── Auth helpers ─────────────────────────────────────────────────────

def get_current_role(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    if not creds:
        return None
    payload = verify_token(creds.credentials)
    return payload["role"] if payload else None


def require_parent(role: str = Depends(get_current_role)):
    if role != "parent":
        raise HTTPException(status_code=403, detail="Parent access required")
    return role


def require_auth(role: str = Depends(get_current_role)):
    if role not in ("parent", "child"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return role


# ── Models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str

class ExtendRequest(BaseModel):
    minutes: int          # positive = add time, negative = subtract

class ScheduleDay(BaseModel):
    start: Optional[str] = None   # "HH:MM" or null to remove
    end:   Optional[str] = None

class ScheduleUpdate(BaseModel):
    allowed_hours:       Optional[dict[str, ScheduleDay]] = None
    daily_limit_minutes: Optional[dict[str, Optional[int]]] = None
    warning_seconds:     Optional[int] = None
    check_interval_seconds: Optional[int] = None


# ── Auth endpoints ───────────────────────────────────────────────────

@router.post("/login")
def login(req: LoginRequest):
    if check_parent_password(req.password):
        return {"token": create_token("parent"), "role": "parent"}
    raise HTTPException(status_code=401, detail="Wrong password")


@router.post("/login/child")
def login_child():
    """Child gets a read-only token (no password needed)."""
    return {"token": create_token("child"), "role": "child"}


# ── Status endpoints ─────────────────────────────────────────────────

@router.get("/status")
def get_status(role: str = Depends(require_auth)):
    """Current lock status, time remaining, usage today."""
    status = scheduler.status()
    status["role"] = role
    return status


@router.get("/status/public")
def get_status_public():
    """Minimal public status — no auth required (for home screen widget)."""
    s = scheduler.status()
    return {
        "allowed":              s["allowed"],
        "minutes_until_lockout": s.get("minutes_until_lockout"),
        "used_minutes":         s["used_minutes"],
        "daily_limit_minutes":  s.get("daily_limit_minutes"),
    }


# ── Schedule endpoints ───────────────────────────────────────────────

@router.get("/schedule")
def get_schedule(_: str = Depends(require_auth)):
    """Return current config.json content."""
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg


@router.put("/schedule")
def update_schedule(update: ScheduleUpdate, _: str = Depends(require_parent)):
    """
    Partial update of schedule. Only provided fields are changed.
    Example: send only daily_limit_minutes to update limits without touching hours.
    """
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    if update.warning_seconds is not None:
        cfg["warning_seconds"] = update.warning_seconds

    if update.check_interval_seconds is not None:
        cfg["check_interval_seconds"] = update.check_interval_seconds

    if update.allowed_hours is not None:
        cfg.setdefault("schedule", {})["allowed_hours"] = {
            day: {"start": v.start, "end": v.end}
            for day, v in update.allowed_hours.items()
            if v.start and v.end
        }

    if update.daily_limit_minutes is not None:
        cfg.setdefault("schedule", {})["daily_limit_minutes"] = {
            day: minutes
            for day, minutes in update.daily_limit_minutes.items()
            if minutes is not None
        }

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "config": cfg}


# ── Time control ─────────────────────────────────────────────────────

@router.post("/extend")
def extend_time(req: ExtendRequest, _: str = Depends(require_parent)):
    """
    Add or subtract minutes from today's daily limit.
    Positive minutes = more time. Negative = less time.
    Min result is 0, max is 1440 (24h).
    """
    if not (-480 <= req.minutes <= 480):
        raise HTTPException(status_code=400, detail="minutes must be between -480 and 480")

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    from scheduler import DAYS
    from datetime import datetime
    day = DAYS[datetime.now().weekday()]

    limits = cfg.setdefault("schedule", {}).setdefault("daily_limit_minutes", {})
    current = limits.get(day, 120)
    new_limit = max(0, min(1440, current + req.minutes))
    limits[day] = new_limit

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "ok":        True,
        "day":       day,
        "old_limit": current,
        "new_limit": new_limit,
        "delta":     req.minutes,
    }


@router.post("/unlock/now")
def unlock_now(_: str = Depends(require_parent)):
    """
    Temporarily extend today's allowed window end to end of day (23:59).
    Useful for quick 'unlock until midnight'.
    """
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    from scheduler import DAYS
    from datetime import datetime
    day = DAYS[datetime.now().weekday()]

    hours = cfg.setdefault("schedule", {}).setdefault("allowed_hours", {})
    existing = hours.get(day, {"start": "00:00", "end": "23:59"})
    hours[day] = {"start": existing.get("start", "00:00"), "end": "23:59"}

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "day": day, "window": hours[day]}


# ── Usage history ─────────────────────────────────────────────────────

@router.get("/usage/today")
def usage_today(_: str = Depends(require_auth)):
    """Today's usage stats."""
    if USAGE_FILE.exists():
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    else:
        data = {"date": "", "used_minutes": 0.0, "session_start": None}

    used = scheduler.get_used_minutes_today()
    return {
        "date":          data.get("date"),
        "used_minutes":  round(used, 1),
        "session_active": data.get("session_start") is not None,
    }
