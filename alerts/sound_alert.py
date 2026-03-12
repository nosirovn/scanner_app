"""
Sound Alert System.
Plays audio alerts for trading signals.
"""

import asyncio
import platform
from typing import Optional
from utils.logger import logger, log_error

class SoundAlertSystem:
    """Handle in-app sound alerts."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.platform = platform.system()

    async def play_alert(self, alert_type: str = "beep") -> bool:
        """
        Play alert sound.

        Args:
            alert_type: 'beep' (default), 'alert', 'hot'
        """
        if not self.enabled:
            return False

        try:
            if self.platform == "Darwin":  # macOS
                await self._play_macos_alert(alert_type)
            elif self.platform == "Linux":
                await self._play_linux_alert(alert_type)
            elif self.platform == "Windows":
                await self._play_windows_alert(alert_type)

            return True
        except Exception as e:
            log_error("sound_alert.play_alert", str(e))
            return False

    async def _play_macos_alert(self, alert_type: str):
        """Play alert on macOS."""
        sounds = {
            "beep": "Glass",
            "alert": "Alert",
            "hot": "Alarm"
        }
        sound = sounds.get(alert_type, "Glass")

        proc = await asyncio.create_subprocess_exec(
            "afplay", f"/System/Library/Sounds/{sound}.aiff"
        )
        await proc.wait()

    async def _play_linux_alert(self, alert_type: str):
        """Play alert on Linux."""
        # Try using speaker-test or beep
        try:
            proc = await asyncio.create_subprocess_exec(
                "paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"
            )
            await proc.wait()
        except:
            # Fallback to simple beep
            import sys
            print('\a', end='', file=sys.stderr, flush=True)

    async def _play_windows_alert(self, alert_type: str):
        """Play alert on Windows."""
        import winsound

        sounds = {
            "beep": winsound.SND_EXCLAMATION,
            "alert": winsound.SND_HAND,
            "hot": winsound.SND_EXCLAMATION
        }
        sound = sounds.get(alert_type, winsound.SND_EXCLAMATION)

        winsound.Beep(1000, 500)  # Frequency, Duration in ms

    def toggle(self, enabled: bool):
        """Toggle sound alerts on/off."""
        self.enabled = enabled
        logger.info(f"Sound alerts {'enabled' if enabled else 'disabled'}")
