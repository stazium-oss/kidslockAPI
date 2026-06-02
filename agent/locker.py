import ctypes
import subprocess
import logging

logger = logging.getLogger(__name__)


def lock_screen():
    """Lock the Windows workstation screen."""
    try:
        result = ctypes.windll.user32.LockWorkStation()
        if result:
            logger.info("Screen locked successfully")
        else:
            logger.error("LockWorkStation() returned 0")
    except Exception as e:
        logger.error(f"Failed to lock screen: {e}")


def logoff_user():
    """Force log off the current user session."""
    try:
        subprocess.run(
            ["shutdown", "/l", "/f"],
            check=True,
            capture_output=True
        )
        logger.info("User logged off successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to logoff: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during logoff: {e}")


def perform_lockout(mode: str = "logoff"):
    """
    Perform the lockout action.
    mode: 'lock' - lock screen only
          'logoff' - force logoff (default, harder to bypass)
    """
    logger.warning(f"Performing lockout: mode={mode}")
    if mode == "lock":
        lock_screen()
    else:
        logoff_user()
