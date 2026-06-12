# ============================================================
#  Railway Platform Safety & Crowd Management System
#  Configuration
# ============================================================
import os
from dotenv import load_dotenv
load_dotenv()
# --- Detection ---
CONFIDENCE          = 0.4
FRAME_SKIP          = 2
MODEL_PATH          = "yolov8n.pt"
TRAIN_CLASS_ID      = 6

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# --- Video Source ---
DEFAULT_SOURCE      = "videos/demo.mp4"

# ============================================================
#  SAFETY LINE — calibrated for demo.mp4 (898x506, 16:9)
#
#  Frame layout:
#    LEFT  (x=0   to x=635) : Track zone — stationary Indian Railways train
#    x=618 to x=660         : Yellow tactile safety strip (pixel-measured)
#    RIGHT (x=635 to x=898) : Platform — safe zone for passengers
#
#  HOUGH auto-detection is OFF for this video because the train
#  body fills the left half and confuses the edge detector.
#  Manual defaults below are pixel-accurate.
#
#  FOR A NEW VIDEO: set HOUGH_ENABLED=True first and press H.
#  If Hough misfires, set it False and nudge with A/D/W/S/E/R.
# ============================================================
DEFAULT_LINE_X      = 635
DEFAULT_LINE_Y      = 253
DEFAULT_ANGLE       = 90        # 90 = perfectly vertical

HOUGH_ENABLED           = False
HOUGH_THRESHOLD         = 80
HOUGH_MIN_LENGTH        = 100
HOUGH_MAX_GAP           = 10
HOUGH_RECALIBRATE_N     = 300

# --- Tracking ---
TRACK_ENABLED       = True
VIOLATION_COOLDOWN  = 3.0

# ============================================================
#  CROWD ZONES — calibrated for demo.mp4
#
#  Coordinates are PERCENTAGE of frame (0.0 to 1.0) so they
#  scale correctly to any resolution automatically.
#
#  demo.mp4 only has a visible platform strip on the right 28%.
#  Door zones are commented — not visible in this video angle.
#  Uncomment and adjust for videos showing train door areas.
# ============================================================
ZONES = [
    {
        "name":        "Platform Zone",
        "polygon":     [(0.72, 0.4), (1.0, 0.4), (1.0, 1.0), (0.72, 1.0)],
        "max_persons": 8,
        "alert_type":  "crowd",
        "color_safe":  (0, 180, 0),
        "color_alert": (0, 100, 255),
        "announce":    "Attention. The platform is getting crowded. Please spread out and stay behind the yellow line.",
    },
    # ── Uncomment for videos with visible door areas ──────────
    # {
    #     "name":        "Door Zone A",
    #     "polygon":     [(0.74, 0.55), (0.87, 0.55), (0.87, 1.0), (0.74, 1.0)],
    #     "max_persons": 3,
    #     "alert_type":  "door",
    #     "color_safe":  (255, 180, 0),
    #     "color_alert": (0, 0, 255),
    #     "announce":    "Door area: allow passengers to exit before boarding.",
    # },
]

# --- Crowd / Rush Detection ---
CROWD_VELOCITY_THRESHOLD    = 18.0
CROWD_RUSH_COOLDOWN         = 8.0
VELOCITY_HISTORY_FRAMES     = 10

# ============================================================
#  TRAIN DETECTION
#
#  DISABLED by default.
#  YOLOv8 detects a stationary train in demo.mp4 from frame 1.
#  Since it never "arrives", firing "train is arriving" every
#  30 seconds is wrong and annoying.
#
#  Set TRAIN_DETECT_ENABLED = True ONLY when your video shows
#  a train actively pulling into the station (you can see it
#  moving in from one end of the frame).
# ============================================================
TRAIN_DETECT_ENABLED        = False
TRAIN_ARRIVE_COOLDOWN       = 30.0
BOARDING_CROWD_MULTIPLIER   = 0.7

# --- Heatmap ---
HEATMAP_ENABLED     = True
HEATMAP_ALPHA       = 0.45
HEATMAP_DECAY       = 0.92
HEATMAP_RADIUS      = 30

# --- Logging ---
DB_PATH             = "logs/violations.db"
SCREENSHOT_DIR      = "screenshots"

# --- Alerts ---
SOUND_ENABLED       = True
SOUND_PATH          = "sounds/alert.wav"

# ============================================================
#  PA ANNOUNCEMENTS
#  Text-to-speech is enabled but TRAIN announcements are
#  suppressed via TRAIN_DETECT_ENABLED=False above.
#  Boundary violation and crowd alerts still speak.
#  Set PA_ENABLED=False to silence all speech entirely.
# ============================================================
PA_ENABLED          = False   # Set True to enable voice announcements
PA_RATE             = 150
PA_VOLUME           = 1.0
PA_COOLDOWN         = 10.0



# --- Display ---
WINDOW_TITLE        = "Railway Platform Safety & Crowd Management"
RED_ZONE_ALPHA      = 0.15
ZONE_OVERLAY_ALPHA  = 0.18
