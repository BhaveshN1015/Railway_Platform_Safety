"""
pa_announcer.py — Text-to-speech PA system (non-blocking).

Train arrival announcements are fully removed. Only these events speak:
  - boundary   : person crosses into track zone
  - crowd      : zone overcrowding
  - door       : door rush
  - rush       : crowd velocity surge

Set PA_ENABLED = False in config.py to silence everything.
"""

import threading
import time
from typing import Dict
import config


class PAAnnouncer:

    MESSAGES = {
        "boundary": (
            "Attention passengers. Please step back behind the yellow safety line. "
            "Standing near the platform edge is dangerous."
        ),
        "crowd": (
            "Attention. This section of the platform is getting crowded. "
            "Please spread out and maintain distance from the platform edge."
        ),
        "door": (
            "Passengers, please stand back from the train doors. "
            "Allow alighting passengers to exit before boarding."
        ),
        "rush": (
            "Caution. Please do not rush on the platform. "
            "Walk carefully and maintain safe distance from the edge."
        ),
    }

    def __init__(self) -> None:
        self.enabled = config.PA_ENABLED
        self._engine = None
        self._lock   = threading.Lock()
        self._cooldowns: Dict[str, float] = {}

        if self.enabled:
            self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate",   config.PA_RATE)
            engine.setProperty("volume", config.PA_VOLUME)
            self._engine = engine
            print("[PA] TTS engine ready.")
        except Exception as e:
            print(f"[PA] TTS unavailable ({e}). PA disabled.")
            self.enabled = False

    # ── Public API ────────────────────────────────────────────

    def announce(self, text: str, key: str = "") -> None:
        """Speak text on a background thread with cooldown."""
        if not self.enabled:
            return
        k   = key or text
        now = time.time()
        if now - self._cooldowns.get(k, 0) < config.PA_COOLDOWN:
            return
        self._cooldowns[k] = now
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def announce_event(self, event_type: str, custom_text: str = "") -> None:
        """Announce a named event. Train events are silently ignored."""
        # Explicitly block any train-related announcements
        if event_type in ("train_arriving", "boarding_open", "boarding_close"):
            return
        text = custom_text or self.MESSAGES.get(event_type, "")
        if text:
            self.announce(text, key=event_type)

    def announce_zone(self, zone: dict) -> None:
        """Announce zone-specific message."""
        text = zone.get("announce", "")
        if text:
            self.announce(text, key=f"zone_{zone['name']}")

    def _speak(self, text: str) -> None:
        with self._lock:
            if self._engine is None:
                return
            try:
                print(f"[PA] {text}")
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                print(f"[PA] Speak error: {e}")
