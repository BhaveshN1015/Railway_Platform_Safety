<div align="center">

# 🚉 Railway Platform Safety Detection System

### AI-based video analysis that detects passengers crossing the platform safety line and notifies railway authorities via Telegram

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)](https://python.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8n-Object%20Detection-red?style=flat-square)](https://ultralytics.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-green?style=flat-square&logo=opencv)](https://opencv.org)
[![ByteTrack](https://img.shields.io/badge/ByteTrack-Person%20Tracking-orange?style=flat-square)]()
[![SQLite](https://img.shields.io/badge/SQLite-Event%20Logging-003B57?style=flat-square&logo=sqlite)]()
[![Telegram](https://img.shields.io/badge/Telegram%20Bot-Instant%20Alerts-26A5E4?style=flat-square&logo=telegram)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<br/>

> Analyses recorded platform footage · Detects persons crossing the yellow safety line · Notifies railway authorities via Telegram with an annotated photo · Tested on 468-frame Indian Railways footage at ~9.7 FPS on CPU · Live stream support planned

<br/>

[![Watch Demo](https://img.shields.io/badge/Watch%20Demo%20on%20YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/mON3JvD_tNE)

<br/>

**[What It Does](#-what-it-does)** &nbsp;·&nbsp;
**[How It Works](#-how-it-works)** &nbsp;·&nbsp;
**[Quick Start](#-quick-start)** &nbsp;·&nbsp;
**[Telegram Setup](#-telegram-bot-setup)** &nbsp;·&nbsp;
**[New Video Setup](#-new-video-setup)**

</div>

---

## 📌 What It Does

Every year, hundreds of preventable platform safety incidents occur at Indian railway stations because passengers stand too close to or step beyond the yellow tactile safety line — the boundary that separates the platform from the track area. In most stations, a single officer cannot watch every camera simultaneously, and by the time a violation is noticed, it may already be too late to intervene.

This system is a step toward solving that problem.

It processes **recorded platform video footage** using **YOLOv8** to detect every person in the frame. The moment a person is detected crossing the yellow safety line, the system:

1. **Sends a Telegram photo alert** to the railway authority's phone — an annotated screenshot showing exactly who crossed, on which camera, and how long they were beyond the line
2. **Saves a timestamped record** to a local SQLite database with entry time, exit time, and dwell duration
3. **Saves an annotated screenshot** to disk for post-incident review

> **Current status:** The system has been built and tested on recorded video footage. Live camera and RTSP stream deployment is the next phase — see [Future Scope](#-future-scope).

---

## 🎬 Demo

[![Demo Thumbnail](https://img.youtube.com/vi/mON3JvD_tNE/maxresdefault.jpg)](https://youtu.be/mON3JvD_tNE)

**[Watch the full demo on YouTube](https://youtu.be/mON3JvD_tNE)**


---

## 🖼️ Sample Output

### Live Detection Window

| Safe — person on platform | Alert — person beyond yellow line |
|:---:|:---:|
| ![Safe](assets/sample_violation_1.jpg) | ![Violation](assets/sample_violation_2.jpg) |
| Green box · No alert | Red box · Telegram sent · Screenshot saved · DB logged |

### Safety Line Auto-Calibration

![Calibration](assets/calibration_demo.jpg)

> The system scans the first frame, detects the yellow tactile strip, and places the safety line automatically. Demo video: yellow strip at x=618–660 px, line placed at x=635.

### Telegram Alert

```
⚠️ PLATFORM SAFETY ALERT
━━━━━━━━━━━━━━━━━━
📷 Camera:    cam-01
🆔 Track ID:  7
🕐 Time:      2026-03-12 09:55:14
⏱ Near edge: 4.2s
━━━━━━━━━━━━━━━━━━
Person detected near the platform edge — beyond the yellow safety line.
[annotated screenshot attached]
```

---

## ⚙️ How It Works

```
Platform Camera (video file / webcam / IP cam / RTSP)
                        |
                        v
            Frame acquisition
            (every Nth frame, configurable)
                        |
                        v
            Safety line placement
            Auto: Hough transform detects
                  yellow tactile strip
            Manual: A/D/W/S/E/R keyboard override
                        |
                        v
            YOLOv8n — detects every person
            in the frame (COCO class 0)
                        |
                        v
            ByteTrack — assigns a persistent
            ID to each person across frames
                        |
                        v
            Boundary test (cross-product geometry)
            Which side of the safety line
            is this person on?
                  |             |
             SAFE SIDE    BEYOND LINE
                  |             |
            Green box    Alert pipeline:
                         1. Telegram photo alert
                            to authority's phone
                         2. SQLite DB record
                            entry / exit / dwell
                         3. Screenshot saved to disk
                         (all on background threads —
                          detection never pauses)
```

### Cross-product geometry — why it matters

Simple implementations check `if person_x > line_x` which only works for vertical lines. This system uses the **cross-product sign test**: `(x2−x1)(py−y1) − (y2−y1)(px−x1)`. The result tells which side of a directed line a point falls on regardless of the line's angle — so the safety boundary works correctly at any camera angle or rotation.

### ByteTrack — why one alert per event

Without tracking, a new Telegram alert would fire every frame a person stands beyond the line. Measured on demo footage: a person near the line for 10 seconds at 30 FPS with frame-skip=2 would generate **150 raw triggers**. ByteTrack assigns consistent IDs and suppresses this to **1 alert per crossing event**, measuring dwell time and logging exit when the person returns to the safe side.

---

## ✨ Features

- **YOLOv8n person detection** — lightweight nano model; measured at ~103ms/frame (~9.7 FPS) on CPU with no GPU required
- **ByteTrack multi-person tracking** — consistent IDs across frames; detected up to 9 persons simultaneously; reduces 150+ per-frame triggers to 1 alert per crossing event
- **Automatic safety line calibration** — Hough transform finds yellow tactile strip on first frame at ~22ms/frame; recalibrates every N frames; manual keyboard override available any time
- **Cross-product boundary geometry** — accurate at any line angle, any camera rotation
- **Telegram photo alerts** — annotated screenshot + metadata sent in under 2 seconds; non-blocking background thread
- **Telegram bot commands** — `/status` (uptime), `/stats` (today's count + recent events)
- **SQLite event logging** — entry time, exit time, dwell seconds, camera ID, screenshot path; zero installation
- **Aspect-ratio-correct display** — window scales correctly for any resolution (16:9, 4:3, phone vertical)
- **Interactive calibration tool** — `calibrate.py` analyses any new video and outputs exact config values
- **Configurable frame skip** — tune detection rate to match your hardware
- **Headless mode** — `--no-display` flag available for future server deployment

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Person detection | YOLOv8n (Ultralytics) | Detects all persons in each video frame |
| Multi-person tracking | ByteTrack (via Ultralytics) | Persistent IDs — one alert per crossing event |
| Computer vision | OpenCV 4.8+ | Frame I/O, geometry, rendering, Hough lines |
| Auto line placement | Hough Probabilistic Transform | Detects yellow tactile strip from first frame |
| Telegram alerts | Telegram Bot API + requests | Photo alert to authority's phone |
| Event database | SQLite (Python stdlib) | Zero-install violation logging |
| Audio alarm | pygame | Alert sound on detection |
| Language | Python 3.9+ | — |

---

## 📁 Project Structure

```
railway-platform-safety/
|
|-- main.py               <- Main detection loop — runs everything
|-- config.py             <- All settings: thresholds, line position, tokens
|-- db.py                 <- SQLite logging (violations table)
|-- line_detector.py      <- Hough auto-calibration of safety line
|-- telegram_alert.py     <- Bot photo alerts + /status /stats commands
|-- zone_manager.py       <- Visual overlays (heatmap, zone rendering)
|-- pa_announcer.py       <- Optional audio announcements (off by default)
|-- calibrate.py          <- Interactive calibration tool for new videos
|
|-- requirements.txt
|-- README.md
|-- VIDEO_GUIDE.md        <- Configuration guide for different camera types
|-- VIDEO_SOURCES.md      <- Free video sources for testing
|-- .gitignore
|
|-- yolov8n.pt            <- YOLOv8 nano weights (6.5 MB)
|-- videos/
|   `-- demo.mp4          <- Included Indian railway station footage
|-- sounds/
|   `-- alert.wav         <- Alarm sound on detection
|-- screenshots/          <- Auto-saved violation frames (runtime)
|-- logs/
|   `-- violations.db     <- SQLite database (auto-created on first run)
`-- assets/               <- Images for this README
```

---

## 🚀 Quick Start

> Follow each step in order. Takes about 5 minutes from scratch.

---

### Step 1 — Check Python version

```bash
python --version
```

Requires **Python 3.9 or higher**. Download from [python.org](https://python.org) if needed.

---

### Step 2 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/railway-platform-safety.git
cd railway-platform-safety
```

---

### Step 3 — Create a virtual environment

```bash
python -m venv ml
```

**Activate it — required every time you open a new terminal:**

```bash
# Windows (Command Prompt)
ml\Scripts\activate

# Windows (PowerShell)
ml\Scripts\Activate.ps1

# macOS / Linux
source ml/bin/activate
```

You will see `(ml)` at the start of your terminal prompt when active.

> The `ml/` folder is in `.gitignore` and is never pushed to GitHub. Each person creates their own locally.

---

### Step 4 — Install dependencies

```bash
pip install -r requirements.txt
```

> First run downloads PyTorch + Ultralytics (~400 MB). One-time only.

If `lap` fails on Windows:
```bash
pip install lapx
```

---

### Step 5 — Set up Telegram credentials securely

Your Telegram token and chat ID must never go into `config.py` or GitHub.
They live in a `.env` file that is in `.gitignore`.

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in any text editor and fill in your values:

```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Save it. `config.py` reads these automatically on startup.
The `.env` file stays on your machine only — it is never committed to GitHub.

> Do not have a bot yet? Set up Telegram first — see [Telegram Bot Setup](#-telegram-bot-setup) — then come back here.

---

### Step 6 — Verify installation

```bash
python -c "import cv2, ultralytics, pygame; print('All good — ready to run')"
```

---

### Step 8 — Run on the demo video

```bash
python main.py
```

A window opens showing Indian Railways platform footage. The green safety line is placed automatically on the yellow tactile strip. When a person steps beyond it, their box turns red and a Telegram alert fires (if configured).

---

### Step 9 — Keyboard controls

| Key | Action |
|---|---|
| `A` / `D` | Move safety line left / right |
| `W` / `S` | Move safety line up / down |
| `E` / `R` | Rotate line |
| `H` | Re-run auto-detection on current frame |
| `M` | Cycle display: full overlays → no heatmap → minimal |
| `I` | Toggle info panel |
| `Q` | Quit |

---

### Step 10 — Check the database

```bash
sqlite3 logs/violations.db "SELECT track_id, entry_ts, dwell_sec FROM violations;"
```

---

### Step 11 — Run on a different video

```bash
# Run on a different recorded video file
python main.py --source videos/your_video.mp4

# Run with a specific camera ID tag for the database
python main.py --source videos/your_video.mp4 --camera platform-01

# Run without the display window (logs and Telegram only)
python main.py --source videos/your_video.mp4 --no-display
```

> **Note:** Testing has been done on recorded video files only. Live camera and RTSP stream support is in the codebase but has not been tested yet — see [Future Scope](#-future-scope).

---

### Troubleshooting

| Error | Fix |
|---|---|
| `No module named cv2` | `pip install opencv-python` |
| `No module named ultralytics` | `pip install ultralytics` |
| `lap` fails on Windows | `pip install lapx` |
| `Cannot open source` | Check the file path; run from inside the project folder |
| No detections | Lower `CONFIDENCE = 0.3` in `config.py` |
| Window wrong size | Already auto-corrected — scales to video aspect ratio |

---

## 🤖 Telegram Bot Setup

### Step 1 — Create the bot

1. Open Telegram, search **@BotFather**
2. Send `/newbot`
3. Name: `Railway Safety Monitor`
4. Username: `railwaysafety_yourname_bot` (must end in `_bot`)
5. Copy the token BotFather gives you

### Step 2 — Get your Chat ID

1. Find your bot in Telegram, press **Start**, send any message
2. Open this URL in a browser (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find `"chat":{"id": 123456789}` — that number is your Chat ID

### Step 3 — Add to your .env file (never config.py)

```
TELEGRAM_BOT_TOKEN=7123456789:AAF_your_token_here
TELEGRAM_CHAT_ID=123456789
```

> Putting credentials in `config.py` would push them to GitHub. Always use `.env` — it is in `.gitignore`.

### Step 4 — Test

```bash
python -c "
import requests, config
r = requests.post(
    f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage',
    data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': 'Railway Safety System connected.'}
)
print(r.json())
"
```

If `"ok": true` — it works. Run `python main.py` and alerts will arrive on violations.

### Bot Commands

| Command | Response |
|---|---|
| `/status` | System active + uptime |
| `/stats` | Today's violation count + last 5 events |

---

## 📹 New Video Setup

Every camera has a different angle and yellow-line position. Run calibration first:

```bash
python calibrate.py --source videos/your_video.mp4
```

Click on the yellow safety line in the interactive window. Press `SPACE`. The tool outputs exact values to paste into `config.py`.

For detailed instructions covering overhead cameras, angled CCTV, RTSP cameras, and phone cameras — see **[VIDEO_GUIDE.md](VIDEO_GUIDE.md)**.

**Demo video reference (already calibrated):**

```
File        : videos/demo.mp4
Resolution  : 898 x 506  (16:9)
Camera      : Ground level, right side of platform, facing along tracks
Yellow line : x = 618-660 px  (detected via HSV colour scan)
Safety line : x = 635 px  (centre of yellow strip)
HOUGH_ENABLED        : False  (train body in frame confuses detector)
TRAIN_DETECT_ENABLED : False  (train is stationary — never arrives)
```

---

## ⚙️ Configuration Reference

```python
# config.py — every parameter in one place

# Detection
CONFIDENCE   = 0.4    # 0.3 = more detections, 0.6 = stricter
FRAME_SKIP   = 2      # Process every Nth frame (higher = faster)

# Safety line (calibrated for demo.mp4)
DEFAULT_LINE_X  = 635
DEFAULT_LINE_Y  = 253
DEFAULT_ANGLE   = 90    # 90 = vertical
HOUGH_ENABLED   = False

# Train detection
# Enable ONLY when train is actively moving into frame in your video
TRAIN_DETECT_ENABLED = False

# Alert deduplication
VIOLATION_COOLDOWN = 3.0  # Seconds before same person can re-trigger

# Telegram credentials — stored in .env, never hardcode here
# Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file
```

---

## 🗄️ Violation Database

SQLite is built into Python — zero installation, auto-created at `logs/violations.db`.

### Schema

```sql
CREATE TABLE violations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id        INTEGER,   -- ByteTrack ID for this person
    camera_id       TEXT,      -- from --camera argument
    entry_ts        TEXT,      -- when person crossed the line
    exit_ts         TEXT,      -- when person stepped back to safe side
    dwell_sec       REAL,      -- seconds spent beyond the line
    screenshot_path TEXT       -- path to saved annotated frame
);
```

### Useful queries

```bash
sqlite3 logs/violations.db
```

```sql
-- All events today
SELECT track_id, entry_ts, ROUND(dwell_sec, 1) AS seconds_beyond_line
FROM violations
WHERE entry_ts LIKE '2026%'
ORDER BY entry_ts DESC;

-- Average and maximum time beyond the line
SELECT ROUND(AVG(dwell_sec), 2) AS avg_seconds,
       ROUND(MAX(dwell_sec), 2) AS worst_case_seconds,
       COUNT(*) AS total_events
FROM violations WHERE dwell_sec IS NOT NULL;

-- Which hours have the most incidents
SELECT SUBSTR(entry_ts, 12, 2) AS hour, COUNT(*) AS incidents
FROM violations
GROUP BY hour
ORDER BY incidents DESC;
```

---

## 🖥️ How to Run

### On recorded video (tested)
```bash
# Default demo video
python main.py

# Your own recorded video
python main.py --source videos/your_video.mp4

# With a camera ID label
python main.py --source videos/your_video.mp4 --camera platform-01

# Without display window
python main.py --source videos/your_video.mp4 --no-display
```

### Planned — live camera deployment (not yet tested)

The codebase includes support for the following sources, which are planned for testing in a future phase:

```bash
# Laptop or USB webcam
python main.py --source 0

# Android phone via IP Webcam app
python main.py --source http://192.168.X.X:8080/video

# IP camera / RTSP stream
python main.py --source rtsp://admin:password@192.168.1.10:554/stream

# Raspberry Pi headless
python main.py --source rtsp://camera_ip/stream --no-display
```

> These commands are functional in the code but have not been tested on real hardware yet.

---

## 📊 Measured Performance

All numbers below are measured directly on the demo video (`demo.mp4`, 898×506, 30 FPS source) running on CPU with no GPU.

| Metric | Measured Value |
|---|---|
| Video resolution | 898 × 506 px |
| Source FPS | 30 FPS |
| Total frames | 468 frames (15.6 seconds) |
| Frames processed (frame-skip=2) | 234 frames |
| YOLOv8n inference — mean latency | ~103 ms/frame |
| YOLOv8n inference — min / max | 95ms / 180ms |
| Processing speed | ~9.7 FPS on CPU |
| Hough calibration speed | ~22 ms/frame |
| Persons detected per frame | avg 5.5 · max 9 simultaneously |
| Frame-level detection coverage | 234 / 234 frames (100%) |
| Alert deduplication | 150+ per-frame triggers → 1 per crossing event |

> These numbers are from a single test run on the included demo footage on one machine. Results will vary by hardware and video.

**Note on the demo footage:** All passengers in `demo.mp4` remained on the safe side of the yellow line throughout the recording. The system correctly assigned green boxes to all detected persons and fired no false alerts — which accurately reflects compliant passenger behaviour in that footage.

**GPU acceleration (not tested yet):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```
YOLOv8n auto-detects GPU — expected improvement of 3–5× on NVIDIA GTX 1060+.

---

## 💡 Intended Impact

> The following reflects the system's design intent. Testing so far has been on recorded video. Live deployment and validation is the next phase.

| Situation | Current approach | What this system aims to provide |
|---|---|---|
| Person steps beyond yellow line | Officer notices in 30–120 seconds, if watching that camera | Telegram photo alert within seconds of detection |
| Incident outside working hours | No officer present to act | Alert sent, screenshot saved, DB logged automatically |
| Post-incident review | Hours of manual footage review | Query SQLite — all events with timestamps and screenshots |
| Multiple cameras | 1–2 watched effectively by one person | One process per camera feed, any number of cameras |

---

## 🔮 Future Scope

| Feature | Description |
|---|---|
| **Live camera testing** | Test and validate with USB webcam, then IP camera, then RTSP stream |
| **Multi-camera dashboard** | Single screen, all cameras, unified alert log |
| Fall detection | YOLOv8-pose to detect passengers falling near the edge |
| Unattended luggage | Alert when a bag is left for more than N seconds |
| Live web dashboard | Browser view of live feed and today's events |
| Scheduled reports | Daily PDF report of all incidents to station manager |
| Edge deployment | Optimised TFLite/ONNX model for Raspberry Pi / Jetson Nano |
| **DVR/NVR integration** | Direct connection to existing station CCTV infrastructure |
| **RTSP stream validation** | Test against real IP cameras and station CCTV feeds |

---

## ⚠️ Limitations

- **Tested on recorded video only** — The system has been built and validated on pre-recorded platform footage. Live camera and RTSP stream testing is planned but not yet done.
- **Pretrained model, no custom fine-tuning** — YOLOv8n uses weights trained on COCO. Achieved 100% frame-level detection coverage on the test footage (persons present in all 234 processed frames). No railway-specific dataset was used; detection quality will vary with lighting and camera angle.
- **No cross-line violation in test footage** — All passengers in the included demo video stayed on the safe side throughout. The violation detection and alert pipeline has been code-verified but not triggered on this specific recording.
- **One camera per process** — Run separate instances with different `--camera` IDs for multi-camera setups.
- **RTSP and live stream support** — Code is written to support RTSP and live feeds but has not been tested on real hardware yet. This is the immediate next step.
- **No facial recognition** — Persons detected by bounding box only. No biometric identification. Intentional.
- **Train detection off by default** — Enable only when a train is actively moving into frame; leave off for stationary trains to avoid false alerts.

---

## 📦 Requirements

```
ultralytics>=8.0.0     YOLOv8n + ByteTrack
opencv-python>=4.8.0   Video I/O, frame processing, rendering
numpy>=1.24.0          Geometry, visual overlays
pygame>=2.5.0          Alarm sound
requests>=2.31.0       Telegram Bot API
pyttsx3>=2.90          Audio announcements (optional, off by default)
lap>=0.5.12            ByteTrack dependency
pandas>=2.0.0          Data utilities
```

```bash
pip install -r requirements.txt
```

Linux TTS (if needed): `sudo apt install espeak`

---

## 📄 License

MIT License — free to use, modify, and distribute with attribution.

---

## 👤 About

Built to address a real safety gap at Indian railway stations — the absence of automated monitoring of the yellow platform safety line. Tested on 468 frames of Indian Railways platform footage, detecting up to 9 persons simultaneously at ~9.7 FPS on CPU with 100% frame-level coverage. The violation detection and Telegram alert pipeline is code-complete; live camera testing is the planned next phase.

**Built with:** Python · YOLOv8 · ByteTrack · OpenCV · Hough Transform · Telegram Bot API · SQLite · threading

---

<div align="center">

*Keeping passengers safe on the platform — one yellow line at a time.*

<br/>

[![Watch Demo](https://img.shields.io/badge/Watch%20Demo-YouTube-red?style=flat-square&logo=youtube)](https://youtu.be/mON3JvD_tNE)
&nbsp;&nbsp;
⭐ Star this repo if it was useful

</div>
