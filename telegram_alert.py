"""
telegram_alert.py — Non-blocking Telegram notification pipeline.

Handles both boundary violations and crowd management events.
Sends annotated screenshots with structured metadata.

Supported bot commands
----------------------
  /status   — system uptime + active zone counts
  /stats    — today's violations + crowd events summary
  /zones    — current person count per zone
"""

import threading
import time
import os
import requests
from datetime import datetime
from typing import Optional

import config


class TelegramAlerter:

    def __init__(self) -> None:
        self.token   = config.TELEGRAM_BOT_TOKEN.strip()
        self.chat_id = config.TELEGRAM_CHAT_ID.strip()
        self.enabled = bool(self.token and self.chat_id)
        self._start_ts = datetime.now()
        self._zone_manager_ref = None   # set by main.py after ZoneManager is created

        if self.enabled:
            print(f"[Telegram] Bot active → chat {self.chat_id}")
            self._start_polling()
        else:
            print("[Telegram] No credentials — alerts disabled.")

    # ── Public API ────────────────────────────────────────────

    def send_violation(self, screenshot_path: str, track_id: int,
                       camera_id: str = "cam-01", timestamp: str = "",
                       dwell_sec: Optional[float] = None) -> None:
        if not self.enabled:
            return
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        t = threading.Thread(
            target=self._send_violation_photo,
            args=(screenshot_path, track_id, camera_id, ts, dwell_sec),
            daemon=True,
        )
        t.start()

    def send_crowd_alert(self, zone_name: str, count: int, threshold: int,
                         event_type: str, screenshot_path: str = "",
                         camera_id: str = "cam-01") -> None:
        if not self.enabled:
            return
        t = threading.Thread(
            target=self._send_crowd_photo,
            args=(zone_name, count, threshold, event_type, screenshot_path, camera_id),
            daemon=True,
        )
        t.start()

    def send_train_alert(self, camera_id: str = "cam-01") -> None:
        if not self.enabled:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"🚆 *TRAIN ARRIVING*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📷 Camera: `{camera_id}`\n"
            f"🕐 Time: `{ts}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Boarding window activated. Crowd thresholds tightened."
        )
        threading.Thread(target=self._send_text, args=(text,), daemon=True).start()

    # ── Internal send helpers ─────────────────────────────────

    def _api(self, method, **kwargs):
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            return requests.post(url, timeout=15, **kwargs)
        except Exception as e:
            print(f"[Telegram] Request failed: {e}")
            return None

    def _send_text(self, text: str) -> None:
        self._api("sendMessage",
                  data={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"})

    def _send_photo_with_caption(self, path: str, caption: str) -> None:
        if os.path.exists(path):
            with open(path, "rb") as f:
                self._api("sendPhoto",
                          data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"},
                          files={"photo": f})
        else:
            self._send_text(caption)

    def _send_violation_photo(self, screenshot_path, track_id, camera_id, timestamp, dwell_sec):
        dwell_str = f"{dwell_sec:.1f}s" if dwell_sec else "ongoing"
        caption = (
            f"⚠️ *PLATFORM SAFETY ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📷 Camera: `{camera_id}`\n"
            f"🆔 Track ID: `{track_id}`\n"
            f"🕐 Time: `{timestamp}`\n"
            f"⏱ Near edge: `{dwell_str}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Person detected near the platform edge — beyond the yellow safety line."
        )
        self._send_photo_with_caption(screenshot_path, caption)

    def _send_crowd_photo(self, zone_name, count, threshold, event_type, screenshot_path, camera_id):
        icon = "👥" if event_type == "crowd" else "🚪" if event_type == "door" else "⚡"
        event_label = {
            "crowd": "PLATFORM CROWDING ALERT",
            "door":  "DOOR AREA CONGESTION",
            "rush":  "CROWD MOVEMENT ALERT",
        }.get(event_type, "PLATFORM ALERT")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        caption = (
            f"{icon} *{event_label}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📷 Camera: `{camera_id}`\n"
            f"📍 Zone: `{zone_name}`\n"
            f"👥 Count: `{count}` (safe limit: {threshold})\n"
            f"🕐 Time: `{ts}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Passengers exceeding safe platform capacity. Crowd management required."
        )
        self._send_photo_with_caption(screenshot_path, caption)

    # ── Command polling ───────────────────────────────────────

    def _start_polling(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        import db as vdb
        offset = 0
        while True:
            try:
                resp = self._api("getUpdates", data={"offset": offset, "timeout": 20})
                if resp and resp.ok:
                    for upd in resp.json().get("result", []):
                        offset = upd["update_id"] + 1
                        msg    = upd.get("message", {})
                        text   = msg.get("text", "")
                        chat   = str(msg.get("chat", {}).get("id", ""))
                        if chat != str(self.chat_id):
                            continue
                        if text.startswith("/status"):
                            uptime = str(datetime.now() - self._start_ts).split(".")[0]
                            self._send_text(
                                f"✅ *System Status*\n"
                                f"Status: `ACTIVE`\nUptime: `{uptime}`"
                            )
                        elif text.startswith("/stats"):
                            v_count = vdb.get_today_count()
                            c_count = vdb.get_today_crowd_count()
                            recent  = vdb.get_recent(5)
                            lines = [f"📊 *Today's Events*\n"
                                     f"Boundary violations: {v_count}\n"
                                     f"Crowd alerts: {c_count}\n\n*Recent violations:*"]
                            for r in recent:
                                d = f"{r['dwell_sec']:.1f}s" if r["dwell_sec"] else "—"
                                lines.append(f"• `{r['entry_ts']}` · Track {r['track_id']} · {d}")
                            self._send_text("\n".join(lines))
                        elif text.startswith("/zones"):
                            if self._zone_manager_ref:
                                counts = self._zone_manager_ref.get_zone_counts()
                                lines = ["📍 *Zone Counts*"]
                                for name, count in counts.items():
                                    lines.append(f"• {name}: `{count}` persons")
                                self._send_text("\n".join(lines))
                            else:
                                self._send_text("Zone data not yet available.")
            except Exception as e:
                print(f"[Telegram] Poll error: {e}")
            time.sleep(1)
