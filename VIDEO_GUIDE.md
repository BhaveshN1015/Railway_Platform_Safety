# Video Configuration Guide

Every video has a different camera angle, resolution, and layout.
This guide tells you exactly what to change in `config.py` for each scenario,
and how to use the calibration tool for any new video.

---

## Quick Reference — What to Change for a New Video

Open `config.py` and update these 6 values. Everything else stays the same.

```python
# 1. Point to your video
DEFAULT_SOURCE  = "videos/your_video.mp4"

# 2. Where is the yellow safety line in THIS video?
DEFAULT_LINE_X  = ???    # x-pixel where the line sits
DEFAULT_LINE_Y  = ???    # y-pixel (mid-height is fine)
DEFAULT_ANGLE   = 90     # 90=vertical, adjust if line is angled

# 3. Disable auto-detection if train/objects confuse Hough
HOUGH_ENABLED   = False

# 4. Only enable train detection if train MOVES in from outside frame
TRAIN_DETECT_ENABLED = False

# 5. Adjust zone polygon to cover the visible platform area
ZONES = [ ... ]   # use percentage coords (0.0 to 1.0)
```

---

## The Calibration Tool (Recommended)

Instead of guessing pixel values, run this first:

```bash
python calibrate.py --source videos/your_video.mp4
```

It will:
1. Show you the video frame with a draggable safety line
2. Highlight where it detected the yellow tactile strip
3. Print exact `DEFAULT_LINE_X / Y / ANGLE` and `ZONES` values to copy-paste

---

## Demo Video — demo.mp4 (included)

**What the video shows:**
- Indian Railways station, ground-level camera on the right platform
- Two trains STATIONARY on the left tracks — they never move
- Passengers standing on the right side of frame
- Yellow tactile paving strip clearly visible at ~x=635

**Video properties:**
```
Resolution : 898 x 506
Aspect     : 16:9 (widescreen)
FPS        : 30
Duration   : 15.6 seconds
```

**Layout (top view):**
```
x=0                x=618  x=635  x=660            x=898
|                    |      |      |                  |
|   TRACK ZONE       | ████ | LINE | PLATFORM (SAFE)  |
|   (Danger)         | Yel  |      |                  |
|   Train fills      | low  |      | Passengers here  |
|   most of this     | Stri |      |                  |
|                    | p    |      |                  |
```

**Correct config.py settings:**
```python
DEFAULT_SOURCE       = "videos/demo.mp4"
DEFAULT_LINE_X       = 635
DEFAULT_LINE_Y       = 253
DEFAULT_ANGLE        = 90
HOUGH_ENABLED        = False   # Train body confuses edge detector
TRAIN_DETECT_ENABLED = False   # Train is stationary — never "arrives"

ZONES = [
    {
        "name":        "Platform Zone",
        "polygon":     [(0.72, 0.4), (1.0, 0.4), (1.0, 1.0), (0.72, 1.0)],
        "max_persons": 8,
        "alert_type":  "crowd",
        "color_safe":  (0, 180, 0),
        "color_alert": (0, 100, 255),
        "announce":    "Platform zone is overcrowded. Please maintain safe distance.",
    },
]
```

---

## Video Type A — Overhead / Top-Down Camera

**Example:** Ceiling-mounted CCTV looking straight down at the platform

```
Camera up here
      |
      v
 ___________________
|  TRACKS  | PLATFM |
|__________|________|
      x=400 (line)

Frame width = 1280, line at x=550 (43% from left)
```

**Config:**
```python
DEFAULT_LINE_X  = 550
DEFAULT_LINE_Y  = 360   # mid-height
DEFAULT_ANGLE   = 90    # vertical

ZONES = [
    {
        "name":    "Platform North",
        "polygon": [(0.43, 0.0), (0.75, 0.0), (0.75, 0.5), (0.43, 0.5)],
        "max_persons": 15,
        "alert_type": "crowd",
        ...
    },
    {
        "name":    "Platform South",
        "polygon": [(0.43, 0.5), (0.75, 0.5), (0.75, 1.0), (0.43, 1.0)],
        "max_persons": 15,
        "alert_type": "crowd",
        ...
    },
]
```

---

## Video Type B — Side Angle, Train on Left, Platform on Right

**Example:** Camera mounted on pillar, looking along the platform length
(This matches demo.mp4)

```
[TRAIN] | [YELLOW LINE] | [PLATFORM]
  left         x~640          right
```

**Config:** Same as demo.mp4 above. Adjust `DEFAULT_LINE_X` to where
your yellow line pixel falls using the calibration tool.

---

## Video Type C — Platform on Left, Tracks on Right

**Example:** Camera on opposite side of the platform

```
[PLATFORM] | [YELLOW LINE] | [TRACKS/TRAIN]
   left         x~400           right
```

**Config:**
```python
DEFAULT_LINE_X  = 400
DEFAULT_LINE_Y  = 300
DEFAULT_ANGLE   = 90

# The DANGER side is now the RIGHT side of the line.
# You need to flip which side is "danger" — press R key to rotate
# the line 180° so the cross-product points right instead of left.
DEFAULT_ANGLE   = 270   # flips the danger side to the right
```

---

## Video Type D — Train Arriving (Moving Train)

**Example:** Train pulls in from one end of the frame during the video

```python
TRAIN_DETECT_ENABLED = True    # Enable only for moving train arrival
TRAIN_ARRIVE_COOLDOWN = 30.0   # Boarding window lasts 30 seconds
BOARDING_CROWD_MULTIPLIER = 0.7  # Tighten zone limits to 70% during boarding
```

A visual banner will appear when the train is detected. No PA speech
for train arrival — this is intentionally disabled system-wide.

---

## Video Type E — Metro / Underground Station

Usually wider platform, symmetric layout, doors visible.

```python
DEFAULT_LINE_X  = 200   # or wherever the platform edge is
DEFAULT_ANGLE   = 90

ZONES = [
    {
        "name":        "Door Zone A",
        "polygon":     [(0.2, 0.6), (0.4, 0.6), (0.4, 1.0), (0.2, 1.0)],
        "max_persons": 4,
        "alert_type":  "door",
        ...
    },
    {
        "name":        "Door Zone B",
        "polygon":     [(0.6, 0.6), (0.8, 0.6), (0.8, 1.0), (0.6, 1.0)],
        "max_persons": 4,
        "alert_type":  "door",
        ...
    },
    {
        "name":        "Platform Centre",
        "polygon":     [(0.2, 0.3), (0.8, 0.3), (0.8, 0.7), (0.2, 0.7)],
        "max_persons": 20,
        "alert_type":  "crowd",
        ...
    },
]
```

---

## How to Find DEFAULT_LINE_X for Any Video

### Method 1 — Calibration tool (easiest)
```bash
python calibrate.py --source videos/your_video.mp4
```
Click on the yellow line in the window and press SPACE. Values printed automatically.

### Method 2 — VLC player
1. Open video in VLC
2. Pause on a clear frame
3. Tools → Media Information → look at resolution
4. Estimate what fraction of the width the yellow line is at
5. Multiply: `line_x = fraction * frame_width`
   - Example: line at 65% of a 1280px wide video = `0.65 * 1280 = 832`

### Method 3 — Run with debug mode, press H
```bash
python main.py --debug-hough
```
Press `H` to run Hough detection and see where it places the line.
If it's close, nudge with `A`/`D`. Note the x value printed in terminal.

### Method 4 — OpenCV script
```python
import cv2
cap = cv2.VideoCapture("videos/your_video.mp4")
ret, frame = cap.read()
cap.release()

# Click anywhere on the frame to print coordinates
def onclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Clicked: x={x}, y={y}")

cv2.namedWindow("Find Line")
cv2.setMouseCallback("Find Line", onclick)
cv2.imshow("Find Line", frame)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

---

## Aspect Ratio — What the System Handles Automatically

The system detects your video resolution and resizes the display window
to match the correct aspect ratio. You never get a stretched or squashed image.

| Common formats | Ratio | Example resolutions |
|---|---|---|
| Widescreen HD | 16:9 | 1920x1080, 1280x720, 898x506 |
| Standard | 4:3 | 640x480, 800x600 |
| Older CCTV | 4:3 or 5:4 | 704x576 |
| Ultra-wide | 21:9 | 2560x1080 |
| Phone vertical | 9:16 | 1080x1920 |

All of these work. The `ZONES` polygon coordinates (0.0–1.0 percentages)
also scale correctly regardless of resolution — define zones once, they
fit any video from the same camera.

---

## Troubleshooting Common Issues

| Problem | Cause | Fix |
|---|---|---|
| Line appears in wrong position | Hough auto-calibration misfired on train/objects | Set `HOUGH_ENABLED=False`, set manual `DEFAULT_LINE_X` |
| PA says "train is coming" when train is stationary | `TRAIN_DETECT_ENABLED=True` + static train in frame | Set `TRAIN_DETECT_ENABLED=False` — this is already the default |
| Display window is stretched / wrong ratio | Old config window size hardcoded | Already fixed — window auto-sizes to video aspect ratio |
| Everyone is in "danger" zone | Line is on the wrong side | Press `E` or `R` to rotate 180°, or nudge line with `A`/`D` |
| No detections at all | Low contrast / dark video | Lower `CONFIDENCE` to `0.3` in config.py |
| Too many false detections | Flags, banners, stationary objects | Raise `CONFIDENCE` to `0.5` |
| Zones not covering right area | Zone percentages don't match this camera | Run `python calibrate.py` and re-estimate zone polygons |
| Heatmap looks wrong / empty | No people detected to accumulate | Normal — heatmap needs several detections to build up |
