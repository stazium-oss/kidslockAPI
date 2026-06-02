import subprocess
import logging
import sys

logger = logging.getLogger(__name__)


def show_warning(seconds_left: int):
    """
    Show a native Windows warning dialog with countdown.
    Uses PowerShell to display a non-closeable always-on-top message box.
    """
    minutes = seconds_left // 60
    seconds = seconds_left % 60

    if minutes > 0:
        time_str = f"{minutes} мин {seconds} сек"
    else:
        time_str = f"{seconds} сек"

    message = (
        f"⚠️ Время за компьютером заканчивается!\\n\\n"
        f"Осталось: {time_str}\\n\\n"
        f"Сохрани все файлы — компьютер скоро заблокируется."
    )

    try:
        ps_command = f"""
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "{message}",
    "Родительский контроль",
    [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]::Warning
)
"""
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-Command", ps_command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        logger.info(f"Warning shown: {seconds_left}s remaining")

    except Exception as e:
        logger.error(f"Failed to show warning: {e}")


def show_toast(title: str, message: str):
    """
    Show a Windows toast notification (non-blocking).
    """
    try:
        ps_command = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02
)
$template.SelectSingleNode('//text[@id=1]').InnerText = "{title}"
$template.SelectSingleNode('//text[@id=2]').InnerText = "{message}"
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("KidLock").Show($toast)
"""
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-Command", ps_command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000
        )
    except Exception as e:
        logger.error(f"Failed to show toast: {e}")
