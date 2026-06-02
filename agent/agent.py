"""
KidLock Agent — main loop.
Run as: python agent.py
Install as Windows service: python agent.py install  (requires pywin32)

Flow:
  Every CHECK_INTERVAL seconds:
    1. Ask scheduler: is_allowed_now?
    2. If yes → record session start, note how many minutes until lockout
       2a. If <WARNING_SECONDS left → show warning popup
    3. If no  → record session end, perform lockout
"""

import sys
import time
import logging
import json
from pathlib import Path
from datetime import datetime

# ── paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "kidlock.log"

# ── logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("kidlock.agent")

# ── local imports (after path setup) ───────────────────────────────────
from scheduler import Scheduler
from locker import perform_lockout
from notifier import show_warning, show_toast


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_loop():
    logger.info("KidLock agent started")
    show_toast("KidLock", "Агент родительского контроля запущен")

    scheduler = Scheduler(CONFIG_PATH)

    # State flags to avoid spamming notifications
    warning_shown: dict[int, bool] = {}   # {threshold_seconds: shown}
    session_active = False
    locked_out = False

    WARNING_THRESHOLDS = [120, 60, 30]    # seconds before lockout → show popup

    while True:
        try:
            cfg = load_config()
            check_interval = cfg.get("check_interval_seconds", 30)
            warning_seconds = cfg.get("warning_seconds", 120)

            allowed, reason = scheduler.is_allowed_now()

            if allowed:
                locked_out = False

                # Record start of allowed session
                if not session_active:
                    scheduler.record_session_start()
                    session_active = True
                    warning_shown = {}
                    logger.info("Session started (allowed)")

                # Check how long until lockout
                minutes_left = scheduler.minutes_until_lockout()

                if minutes_left is not None:
                    seconds_left = int(minutes_left * 60)

                    for threshold in WARNING_THRESHOLDS:
                        if seconds_left <= threshold and not warning_shown.get(threshold):
                            show_warning(seconds_left)
                            warning_shown[threshold] = True
                            logger.info(f"Warning shown: {seconds_left}s until lockout")

            else:
                # Not allowed → lock if not already locked
                if not locked_out:
                    logger.warning(f"Lockout triggered: {reason}")

                    if session_active:
                        scheduler.record_session_end()
                        session_active = False

                    perform_lockout(mode="logoff")
                    locked_out = True
                    warning_shown = {}

        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)

        time.sleep(check_interval)


# ── Windows Service support (optional, requires pywin32) ───────────────
def try_run_as_service():
    """If pywin32 is available, support 'install'/'start'/'stop' commands."""
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager

        class KidLockService(win32serviceutil.ServiceFramework):
            _svc_name_ = "KidLockAgent"
            _svc_display_name_ = "KidLock Parental Control Agent"
            _svc_description_ = "Monitors computer usage time and enforces schedule."

            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.stop_event = win32event.CreateEvent(None, 0, 0, None)

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.stop_event)

            def SvcDoRun(self):
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, "")
                )
                run_loop()

        if len(sys.argv) > 1 and sys.argv[1] in ("install", "remove", "start", "stop", "restart"):
            win32serviceutil.HandleCommandLine(KidLockService)
            return True

    except ImportError:
        pass  # pywin32 not installed, run as plain script

    return False


if __name__ == "__main__":
    if not try_run_as_service():
        # Plain mode: just run the loop
        run_loop()
