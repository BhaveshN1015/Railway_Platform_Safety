# 🎥 Video Sources for Testing

A curated list of free, royalty-free video sources for testing the Railway Platform Safety & Crowd Management System. All sources below are either completely free or have a free tier with no attribution required.

---

## ✅ Best Sources by Use Case

### For boundary violation testing
*(people walking close to platform edge, static camera angle)*

| Source | Link | Notes |
|---|---|---|
| Pexels — Train station platform | https://www.pexels.com/search/videos/train+station/ | Search "train platform" — look for videos with a clear platform edge visible |
| Pixabay — Railway station | https://pixabay.com/videos/search/railway%20station/ | Good static overhead angles |
| Coverr — Railway station | https://coverr.co/stock-video-footage/railway-station | High quality, no account needed |

### For crowd density / overcrowding testing
*(lots of people in a confined space)*

| Source | Link | Notes |
|---|---|---|
| Pexels — Crowded train station | https://www.pexels.com/video/crowded-train-station-6023186/ | Indian railway station timelapse — great for density testing |
| Pixabay — Crowded train station | https://pixabay.com/videos/search/crowded%20train%20station/ | 1400+ free clips |
| Pexels — Crowd videos | https://www.pexels.com/search/videos/crowd/ | Generic crowd footage works fine |

### For door rush / boarding detection
*(people rushing toward train doors)*

| Source | Link | Notes |
|---|---|---|
| Pexels — Train boarding | https://www.pexels.com/video/video-of-train-853994/ | Passengers boarding — shows door clustering |
| Pexels — Metro station | https://www.pexels.com/search/videos/metro+station/ | Underground metro doors work well |

### For rush / velocity detection
*(fast-moving crowd, people running)*

| Source | Link | Notes |
|---|---|---|
| Pexels — People walking fast | https://www.pexels.com/search/videos/people+walking/ | Filter by "rush hour" tag |
| Pixabay — Commuters | https://pixabay.com/videos/search/commuter/ | Morning rush videos |

### For train detection testing
*(actual train visible in frame)*

| Source | Link | Notes |
|---|---|---|
| Pexels — Train videos | https://www.pexels.com/search/videos/train/ | 30,000+ free clips |
| Pixabay — Train arriving station | https://pixabay.com/videos/search/train+station/ | Train pulling into platform |

---

## 📥 How to Download

### Method 1 — Direct from Pexels/Pixabay website
1. Go to any link above
2. Click the video you want
3. Click **Free Download** → choose resolution (720p recommended)
4. Save to your `videos/` folder

### Method 2 — yt-dlp (any YouTube or supported site)

```bash
# Install
pip install yt-dlp

# Download a single video (720p)
yt-dlp -f "best[height<=720]" "VIDEO_URL" -o "videos/%(title)s.mp4"

# Download and rename
yt-dlp -f "best[height<=720]" "VIDEO_URL" -o "videos/crowd_test.mp4"

# Download best quality available
yt-dlp "VIDEO_URL" -o "videos/%(title)s.mp4"
```

Then run:
```bash
python main.py --source videos/crowd_test.mp4
```

### Method 3 — Phone camera (zero cost, live stream)

**Android — IP Webcam app:**
1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)
2. Open app → Start Server
3. Note IP shown (e.g. `192.168.1.5:8080`)

```bash
python main.py --source http://192.168.1.5:8080/video
```

**Android/iOS — DroidCam:**
1. Install DroidCam on phone and PC from https://www.dev47apps.com/
2. Connect on same WiFi

```bash
python main.py --source http://192.168.1.5:4747/video
```

---

## 🎯 Recommended Test Sequence

Once you have a video, test each system feature in order:

```bash
# Step 1: Run on a train station crowd video
python main.py --source videos/crowded_station.mp4

# Step 2: Press H to auto-detect the safety line
# Step 3: Adjust with A/D/W/S/E/R until line sits on platform edge
# Step 4: Watch zone counts in the info panel
# Step 5: Press B to simulate train arrival — observe boarding window
# Step 6: Press M to cycle display modes (heatmap vs minimal)
# Step 7: Check Telegram for alerts (if configured)
# Step 8: Query the database after running:
```

```bash
sqlite3 logs/violations.db "SELECT * FROM crowd_events ORDER BY id DESC LIMIT 10;"
```

---

## 💡 Tips for Better Detection

- **720p or 1080p** works better than 4K (same YOLOv8 input size, but 4K is slower to decode)
- **Static camera angle** is better than handheld footage
- **Good lighting** — avoid very dark or heavily backlit scenes
- **Crowd visible from above or at angle** works best — side-on footage where people overlap is harder
- **Set CONFIDENCE = 0.3** in config.py for dense crowds where people partially overlap

---

## 📌 Specific Recommended Videos (free, direct links)

| # | Title | Platform | Link | Good for |
|---|---|---|---|---|
| 1 | Crowded Train Station Timelapse | Pexels | https://www.pexels.com/video/crowded-train-station-6023186/ | Crowd density, zone overcrowding |
| 2 | Passengers Boarding Train | Pexels | https://www.pexels.com/video/video-of-train-853994/ | Door zone, train detection |
| 3 | People Walking in Station | Pexels | https://www.pexels.com/video/video-of-people-walking-855564/ | Boundary testing, tracking |
| 4 | Railway Station Search | Pixabay | https://pixabay.com/videos/search/railway%20station/ | Various scenarios |
| 5 | Train Station Coverr | Coverr | https://coverr.co/stock-video-footage/railway-station | High quality test footage |
