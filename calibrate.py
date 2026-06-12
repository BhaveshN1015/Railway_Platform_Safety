"""
calibrate.py — Interactive calibration tool for new videos.

Run this BEFORE main.py whenever you switch to a new video.
It analyses the video, detects the yellow tactile strip, and
gives you exact config.py values to copy-paste.

Usage
-----
    python calibrate.py                          # uses DEFAULT_SOURCE from config.py
    python calibrate.py --source videos/new.mp4
    python calibrate.py --source 0              # webcam

What it does
------------
1. Opens the video and samples 5 frames spread across its duration.
2. For each frame, detects the yellow/orange tactile safety strip via HSV.
3. Runs Hough lines on the clearest frame to estimate boundary angle.
4. Renders an interactive window where you can click to place the line
   and press SPACE to confirm each frame.
5. Prints the exact DEFAULT_LINE_X / DEFAULT_LINE_Y / DEFAULT_ANGLE
   values to paste into config.py.
6. Shows the correct ZONES polygon coordinates for the detected layout.

Interactive controls (calibration window)
-----------------------------------------
  Left-click      Place safety line at clicked x position
  A / D           Nudge line left / right
  W / S           Nudge line up / down
  E / R           Rotate line +/- 2 degrees
  SPACE           Confirm and save these values
  Q               Quit without saving
"""

import argparse
import math
import sys
import time

import cv2
import numpy as np

import config


# ── Geometry ─────────────────────────────────────────────────

def line_endpoints(lx, ly, angle_deg, length=4000):
    rad = math.radians(angle_deg)
    return (
        int(lx - length * math.cos(rad)),
        int(ly - length * math.sin(rad)),
        int(lx + length * math.cos(rad)),
        int(ly + length * math.sin(rad)),
    )


# ── Yellow strip detector ─────────────────────────────────────

def detect_yellow_strip(frame):
    """
    Find the yellow/orange tactile safety strip via HSV.
    Returns (x_left, x_right) pixel bounds, or None if not found.

    Indian railway tactile paving: yellow-orange, roughly Hue 15-35.
    """
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]

    # Focus on bottom 60% of frame (strip is near ground level)
    roi_y = int(h * 0.4)
    roi   = hsv[roi_y:, :]

    mask = cv2.inRange(roi, np.array([12, 60, 80]), np.array([38, 255, 255]))
    # Sum per column
    col_sum = mask.sum(axis=0)
    threshold = col_sum.max() * 0.25
    yellow_cols = np.where(col_sum > threshold)[0]

    if len(yellow_cols) < 5:
        return None

    # Find the main dense cluster (ignore scattered noise)
    gaps = np.diff(yellow_cols)
    # Split at large gaps
    split_pts = np.where(gaps > 30)[0] + 1
    segments  = np.split(yellow_cols, split_pts)
    # Pick the narrowest tall segment (the actual strip, not the entire platform)
    candidates = [s for s in segments if 5 < len(s) < 200]
    if not candidates:
        candidates = segments

    best = max(candidates, key=lambda s: col_sum[s].sum())
    return int(best.min()), int(best.max())


# ── Video analysis ────────────────────────────────────────────

def analyse_video(source):
    cap = cv2.VideoCapture(source if source != "0" else 0)
    if not cap.isOpened():
        sys.exit(f"[ERROR] Cannot open: {source}")

    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    fc  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    aspect = w / h
    if   abs(aspect - 16/9)  < 0.05: aspect_label = "16:9 (widescreen)"
    elif abs(aspect - 4/3)   < 0.05: aspect_label = "4:3 (standard)"
    elif abs(aspect - 16/10) < 0.05: aspect_label = "16:10"
    elif abs(aspect - 1)     < 0.05: aspect_label = "1:1 (square)"
    else:                             aspect_label = f"non-standard ({aspect:.2f})"

    print(f"\n{'='*54}")
    print(f"  VIDEO ANALYSIS")
    print(f"{'='*54}")
    print(f"  Source      : {source}")
    print(f"  Resolution  : {w} x {h}")
    print(f"  Aspect ratio: {aspect_label}")
    print(f"  FPS         : {fps:.1f}")
    print(f"  Duration    : {fc/fps:.1f}s  ({fc} frames)")
    print(f"{'='*54}\n")

    # Sample 5 frames spread across video
    sample_indices = [0, fc//4, fc//2, int(fc*0.75), fc-2] if fc > 5 else [0]
    frames = []
    strip_detections = []

    for idx in sample_indices:
        if fc > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx))
        ret, frame = cap.read()
        if not ret:
            continue
        frames.append(frame.copy())
        strip = detect_yellow_strip(frame)
        strip_detections.append(strip)
        label = f"x={strip[0]}-{strip[1]}" if strip else "not detected"
        pct   = f"({strip[0]/w:.2f}-{strip[1]/w:.2f})" if strip else ""
        print(f"  Frame #{idx:4d} : yellow strip {label} {pct}")

    cap.release()

    # Consensus strip position
    valid = [s for s in strip_detections if s is not None]
    if valid:
        avg_left  = int(np.median([s[0] for s in valid]))
        avg_right = int(np.median([s[1] for s in valid]))
        line_x    = (avg_left + avg_right) // 2
        print(f"\n  Consensus strip : x={avg_left} to x={avg_right}")
        print(f"  Safety line     : x={line_x}  ({line_x/w:.3f} of width)")
    else:
        line_x = w // 2
        print(f"\n  Yellow strip not detected. Defaulting to centre x={line_x}.")
        print(f"  Manually adjust with A/D keys in the calibration window.")

    line_y    = h // 2
    line_angle = 90.0   # assume vertical as starting point

    return frames, w, h, line_x, line_y, line_angle, fps


# ── Render calibration frame ──────────────────────────────────

def render_frame(frame, lx, ly, angle, w, h, strip_bounds=None):
    out = frame.copy()
    lx1, ly1, lx2, ly2 = line_endpoints(lx, ly, angle)

    # Red zone overlay
    mask = out.copy()
    pts  = []
    corners = [(0,0),(w,0),(w,h),(0,h)]
    def cross(px,py):
        return (lx2-lx1)*(py-ly1) - (ly2-ly1)*(px-lx1)
    red_pts = [c for c in corners if cross(c[0],c[1]) > 0]
    red_pts += [(lx1,ly1),(lx2,ly2)]
    if len(red_pts) >= 3:
        cv2.fillPoly(mask, [np.array(red_pts,np.int32)], (0,0,200))
        cv2.addWeighted(mask, 0.2, out, 0.8, 0, out)

    # Safety line
    cv2.line(out, (lx1,ly1), (lx2,ly2), (0,255,0), 3)

    # Yellow strip highlight if detected
    if strip_bounds:
        cv2.rectangle(out, (strip_bounds[0],0),(strip_bounds[1],h),(0,255,255),2)
        cv2.putText(out, f"Yellow strip x={strip_bounds[0]}-{strip_bounds[1]}",
                    (strip_bounds[0]-10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0,255,255), 1)

    # Info labels
    cv2.putText(out, "TRACK ZONE", (20, h//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80,80,255), 2)
    cv2.putText(out, "PLATFORM",   (lx+10, h//2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80,255,80), 2)

    # Controls legend
    legend = [
        "SPACE = confirm & save",
        "A/D = move left/right",
        "W/S = move up/down",
        "E/R = rotate",
        "Click = place line",
        "Q = quit",
    ]
    for i, ln in enumerate(legend):
        cv2.putText(out, ln, (w-230, 25+i*20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, (220,220,220), 1)

    # Current values
    cv2.putText(out, f"LINE  x={lx} y={ly} angle={angle:.0f}",
                (10, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

    return out


# ── Mouse callback ────────────────────────────────────────────

_mouse_x = None

def _on_mouse(event, x, y, flags, param):
    global _mouse_x
    if event == cv2.EVENT_LBUTTONDOWN:
        _mouse_x = x


# ── Main calibration loop ─────────────────────────────────────

def calibrate(source):
    frames, w, h, line_x, line_y, line_angle, fps = analyse_video(source)

    if not frames:
        sys.exit("[ERROR] No frames could be read.")

    # Use the median-detection frame as primary calibration frame
    frame_idx = len(frames) // 2
    frame     = frames[frame_idx]

    strip = detect_yellow_strip(frame)

    print(f"\n{'='*54}")
    print("  INTERACTIVE CALIBRATION WINDOW")
    print(f"{'='*54}")
    print("  Adjust the green line to sit ON the yellow tactile")
    print("  strip. Everything left = TRACK ZONE (danger).")
    print("  Press SPACE to confirm and save config values.")
    print(f"{'='*54}\n")

    win = "Railway Safety — Calibration (SPACE to confirm)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(w, 1280), min(h, 720))
    cv2.setMouseCallback(win, _on_mouse)

    global _mouse_x

    while True:
        # Apply mouse click
        if _mouse_x is not None:
            line_x  = _mouse_x
            _mouse_x = None

        display = render_frame(frame, line_x, line_y, line_angle, w, h, strip)

        # Resize display to fit screen while preserving aspect ratio
        disp_w = min(w, 1280)
        disp_h = int(disp_w * h / w)
        display_resized = cv2.resize(display, (disp_w, disp_h))
        cv2.imshow(win, display_resized)

        k = cv2.waitKey(30) & 0xFF
        if k == ord("q"):
            cv2.destroyAllWindows()
            print("[Calibration] Cancelled.")
            return None
        elif k == ord("a"): line_x -= 3
        elif k == ord("d"): line_x += 3
        elif k == ord("w"): line_y -= 3
        elif k == ord("s"): line_y += 3
        elif k == ord("e"): line_angle += 2
        elif k == ord("r"): line_angle -= 2
        elif k == 32:   # SPACE — confirm
            break

    cv2.destroyAllWindows()

    # ── Compute config values ──────────────────────────────────
    # Zone: safe side is wherever line_x places the boundary
    safe_x_pct  = line_x / w
    zone_top_pct = 0.35   # zones start 35% down (above is usually ceiling/sky)

    print(f"\n{'='*54}")
    print("  CONFIRMED CONFIG VALUES — copy to config.py")
    print(f"{'='*54}")
    print(f"\n# Safety line")
    print(f"DEFAULT_LINE_X  = {line_x}")
    print(f"DEFAULT_LINE_Y  = {line_y}")
    print(f"DEFAULT_ANGLE   = {line_angle:.0f}")
    print(f"HOUGH_ENABLED   = False  # use these manual values")
    print()

    # Determine which side is the platform
    # If line is in left half, platform is on right
    if line_x < w * 0.5:
        platform_x0 = round(safe_x_pct, 2)
        platform_x1 = 1.0
        direction = "RIGHT of line = platform (safe)"
    else:
        platform_x0 = 0.0
        platform_x1 = round(safe_x_pct, 2)
        direction = "LEFT of line = platform (safe)"

    print(f"# {direction}")
    print(f"ZONES = [")
    print(f"    {{")
    print(f'        "name":        "Platform Zone",')
    print(f'        "polygon":     [({platform_x0}, {zone_top_pct}), ({platform_x1}, {zone_top_pct}), ({platform_x1}, 1.0), ({platform_x0}, 1.0)],')
    print(f'        "max_persons": 10,')
    print(f'        "alert_type":  "crowd",')
    print(f'        "color_safe":  (0, 180, 0),')
    print(f'        "color_alert": (0, 100, 255),')
    print(f'        "announce":    "Platform zone is overcrowded. Please maintain safe distance.",')
    print(f"    }},")
    print(f"]")
    print()
    print(f"# Video info: {w}x{h}  aspect={w/h:.3f}  fps={fps:.0f}")
    print(f"{'='*54}\n")

    # Save a calibration screenshot
    final = render_frame(frame, line_x, line_y, line_angle, w, h, strip)
    cv2.imwrite("calibration_result.jpg", final)
    print("[Calibration] Screenshot saved to calibration_result.jpg")

    return line_x, line_y, line_angle


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Railway Safety — Video Calibration Tool")
    parser.add_argument("--source", default=config.DEFAULT_SOURCE,
                        help="Video file, 0=webcam, or rtsp:// URL")
    args = parser.parse_args()

    calibrate(args.source)
