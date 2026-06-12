"""
main.py — Railway Platform Safety & Crowd Management System
============================================================
Keyboard Controls
-----------------
  Q       Quit
  A/D     Move safety line left/right
  W/S     Move safety line up/down
  E/R     Rotate line clockwise/counter-clockwise
  Z/X     Increase/decrease line thickness
  T       Toggle detection on/off
  H       Re-run Hough auto-detection
  M       Cycle display: ALL -> NO_HEATMAP -> MINIMAL
  I       Toggle info panel
  C       Toggle crowd zone overlays
  P       Test PA announcement
  B       Simulate train arrival boarding window (visual only, no speech)

Usage
-----
  python main.py
  python main.py --source videos/demo.mp4
  python main.py --source 0
  python main.py --source rtsp://192.168.1.10:554/stream --camera platform-01
  python main.py --no-auto-line
  python main.py --no-display
"""

import argparse
import datetime
import math
import os
import sys
import time

import cv2
import numpy as np
import pygame
from ultralytics import YOLO

import config
import db
from line_detector import detect_safety_line
from telegram_alert import TelegramAlerter
from zone_manager import ZoneManager
from pa_announcer import PAAnnouncer


# ============================================================
#  Argument Parsing
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(description="Railway Platform Safety & Crowd Management")
    p.add_argument("--source",       default=config.DEFAULT_SOURCE)
    p.add_argument("--camera",       default="cam-01")
    p.add_argument("--no-auto-line", action="store_true")
    p.add_argument("--debug-hough",  action="store_true")
    p.add_argument("--no-display",   action="store_true")
    p.add_argument("--no-sound",     action="store_true")
    p.add_argument("--no-pa",        action="store_true")
    return p.parse_args()


# ============================================================
#  Aspect-ratio-aware display resize
# ============================================================

# Maximum window dimensions — adjusts to screen without distorting video
MAX_DISPLAY_W = 1280
MAX_DISPLAY_H = 720

def compute_display_size(frame_w, frame_h):
    """
    Return (display_w, display_h) that fits within MAX_DISPLAY bounds
    while preserving the original aspect ratio exactly.
    """
    scale = min(MAX_DISPLAY_W / frame_w, MAX_DISPLAY_H / frame_h, 1.0)
    return int(frame_w * scale), int(frame_h * scale)


# ============================================================
#  Geometry
# ============================================================

def line_endpoints(lx, ly, angle_deg, length=4000):
    rad = math.radians(angle_deg)
    return (
        int(lx - length * math.cos(rad)),
        int(ly - length * math.sin(rad)),
        int(lx + length * math.cos(rad)),
        int(ly + length * math.sin(rad)),
    )


def cross_side(px, py, x1, y1, x2, y2):
    """Positive = danger side (left of directed line)."""
    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


def red_zone_poly(w, h, x1, y1, x2, y2):
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    pts = [c for c in corners if cross_side(c[0], c[1], x1, y1, x2, y2) > 0]
    pts += [(x1, y1), (x2, y2)]
    return np.array(pts, np.int32) if len(pts) >= 3 else None


# ============================================================
#  Drawing
# ============================================================

def draw_safety_line(frame, x1, y1, x2, y2, thickness, w, h):
    mask = frame.copy()
    poly = red_zone_poly(w, h, x1, y1, x2, y2)
    if poly is not None:
        cv2.fillPoly(mask, [poly], (0, 0, 255))
        cv2.addWeighted(mask, config.RED_ZONE_ALPHA, frame, 1 - config.RED_ZONE_ALPHA, 0, frame)
    cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), thickness)
    cv2.putText(frame, "YELLOW LINE ZONE", (15, 38),  cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 220), 2)
    cv2.putText(frame, "PLATFORM",         (15, 62),  cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 200, 0), 2)


def draw_person_box(frame, x1, y1, x2, y2, track_id, in_danger):
    color = (0, 0, 255) if in_danger else (0, 220, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    label = f"ID:{track_id}" if track_id is not None else "person"
    cv2.putText(frame, label, (x1, max(y1 - 6, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2)


def draw_train_box(frame, x1, y1, x2, y2):
    """Draw train bounding box — no alert, just visual label."""
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
    cv2.putText(frame, "TRAIN", (x1, max(y1 - 6, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)


def draw_info_panel(frame, fps, danger_count, today_v, today_c,
                    detect_on, auto_line, boarding, zone_counts):
    w = frame.shape[1]
    panel_w, panel_h = 248, 158
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w - 10, 8), (w - 8, 8 + panel_h), (18, 18, 18), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    rows = [
        f"FPS          {fps:>5.1f}",
        f"In danger    {danger_count:>5}",
        f"Violations   {today_v:>5}",
        f"Crowd alerts {today_c:>5}",
        f"Detection    {'ON ' if detect_on else 'OFF':>5}",
        f"Auto-line    {'ON ' if auto_line else 'OFF':>5}",
        f"Boarding     {'YES' if boarding else 'NO ':>5}",
    ]
    for i, ln in enumerate(rows):
        cv2.putText(frame, ln, (w - panel_w, 28 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (210, 210, 210), 1)
    # Zone mini bars
    y_base = 8 + panel_h + 8
    for j, (name, cnt) in enumerate(list(zone_counts.items())[:4]):
        short     = name.replace("Platform ", "Plt ").replace("Door Zone ", "Door ")
        threshold = next((z["max_persons"] for z in config.ZONES if z["name"] == name), 10)
        fill      = int(min(cnt / max(threshold, 1), 1.0) * 100)
        bar_color = (0, 200, 0) if cnt <= threshold * 0.7 else \
                    (0, 165, 255) if cnt <= threshold else (0, 0, 255)
        bx = w - panel_w - 8
        by = y_base + j * 20
        cv2.rectangle(frame, (bx, by), (bx + 100, by + 14), (50, 50, 50), -1)
        if fill > 0:
            cv2.rectangle(frame, (bx, by), (bx + fill, by + 14), bar_color, -1)
        cv2.putText(frame, f"{short[:9]} {cnt}/{threshold}",
                    (bx + 104, by + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 200), 1)


def draw_violation_banner(frame, w, h):
    ov = frame.copy()
    cv2.rectangle(ov, (0, 0), (w, 55), (0, 0, 180), -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, "!! SAFETY ALERT  --  PERSON NEAR PLATFORM EDGE !!",
                (max(0, w // 2 - 330), 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)


def draw_crowd_banner(frame, w, h, zone_name):
    ov = frame.copy()
    cv2.rectangle(ov, (0, h - 55), (w, h), (0, 60, 200), -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, f"!! PLATFORM CROWDING  --  {zone_name.upper()} !!",
                (max(0, w // 2 - 270), h - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.82, (255, 255, 255), 2)


def draw_rush_banner(frame, w, h):
    ov = frame.copy()
    cv2.rectangle(ov, (0, h // 2 - 30), (w, h // 2 + 30), (0, 0, 150), -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, "!! CROWD MOVEMENT ALERT  --  PLEASE WALK CAREFULLY !!",
                (max(0, w // 2 - 340), h // 2 + 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 220, 60), 2)


def draw_boarding_banner(frame, w, h, remaining):
    ov = frame.copy()
    cv2.rectangle(ov, (0, h - 28), (w, h), (20, 20, 160), -1)
    cv2.addWeighted(ov, 0.7, frame, 0.3, 0, frame)
    cv2.putText(frame, f"BOARDING WINDOW ACTIVE — {remaining}s remaining",
                (w // 2 - 220, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 220, 60), 2)


DISPLAY_MODES = ["ALL", "NO_HEATMAP", "MINIMAL"]


# ============================================================
#  Main
# ============================================================

def main():
    args = parse_args()
    if args.no_pa:    config.PA_ENABLED    = False
    if args.no_sound: config.SOUND_ENABLED = False

    # Init subsystems
    db.init_db()
    alerter = TelegramAlerter()
    pa      = PAAnnouncer()

    if config.SOUND_ENABLED:
        pygame.mixer.init()
        try:
            pygame.mixer.music.load(config.SOUND_PATH)
        except Exception as e:
            print(f"[Sound] {e}")
            config.SOUND_ENABLED = False

    src   = args.source if args.source != "0" else 0
    model = YOLO(config.MODEL_PATH)
    cap   = cv2.VideoCapture(src)

    if not cap.isOpened():
        sys.exit(f"[ERROR] Cannot open: {args.source}")

    print(f"[INFO] Source  : {args.source}")
    print(f"[INFO] Camera  : {args.camera}")

    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)

    ret, first_frame = cap.read()
    if not ret:
        sys.exit("[ERROR] Cannot read first frame.")
    h, w = first_frame.shape[:2]
    print(f"[INFO] Frame   : {w}x{h}  aspect={w/h:.3f}")

    # Compute display window size preserving aspect ratio
    disp_w, disp_h = compute_display_size(w, h)
    if not args.no_display:
        cv2.namedWindow(config.WINDOW_TITLE, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(config.WINDOW_TITLE, disp_w, disp_h)
        print(f"[INFO] Display : {disp_w}x{disp_h} (aspect-correct)")

    # Safety line
    auto_line_on = config.HOUGH_ENABLED and not args.no_auto_line
    if auto_line_on:
        lx, ly, angle = detect_safety_line(first_frame, debug=args.debug_hough)
    else:
        lx, ly, angle = config.DEFAULT_LINE_X, config.DEFAULT_LINE_Y, float(config.DEFAULT_ANGLE)
    thickness = 2

    # Zone manager
    zm = ZoneManager(h, w)
    alerter._zone_manager_ref = zm

    # State
    detect_on    = True
    show_info    = True
    show_zones   = True
    display_mode = 0

    track_state:    dict = {}
    crowd_cooldown: dict = {}
    # Boarding window (visual only — no speech)
    boarding_window  = False
    boarding_start   = 0.0
    last_train_alert = 0.0
    rush_active      = False

    fps_buf         = []
    frame_count     = 0
    today_v         = db.get_today_count()
    today_c         = db.get_today_crowd_count()
    last_db_refresh = time.time()
    pending         = [first_frame]

    print("[INFO] Running — Q quit | H hough | M mode | B boarding window | P test PA")

    while True:
        if pending:
            frame = pending.pop(0)
        else:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] End of source.")
                break

        frame_count += 1
        t0 = time.time()

        # Periodic Hough recalibration
        if (auto_line_on and config.HOUGH_RECALIBRATE_N > 0
                and frame_count % config.HOUGH_RECALIBRATE_N == 0):
            lx, ly, angle = detect_safety_line(frame)

        if frame_count % max(1, config.FRAME_SKIP) != 0:
            continue

        mode_label  = DISPLAY_MODES[display_mode]
        heatmap_was = config.HEATMAP_ENABLED
        if mode_label in ("NO_HEATMAP", "MINIMAL"):
            config.HEATMAP_ENABLED = False

        lx1, ly1, lx2, ly2 = line_endpoints(lx, ly, angle)
        draw_safety_line(frame, lx1, ly1, lx2, ly2, thickness, w, h)

        current_danger_ids: set = set()
        detections_for_zm:  list = []
        train_in_frame = False

        if detect_on:
            detect_classes = [0]
            if config.TRAIN_DETECT_ENABLED:
                detect_classes.append(config.TRAIN_CLASS_ID)

            if config.TRACK_ENABLED:
                results = model.track(
                    frame, classes=detect_classes, conf=config.CONFIDENCE,
                    persist=True, tracker="bytetrack.yaml", verbose=False,
                )
            else:
                results = model(frame, classes=detect_classes,
                                conf=config.CONFIDENCE, verbose=False)

            for r in results:
                for box in r.boxes:
                    cls     = int(box.cls[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2

                    # Train — draw box only, NO alerts, NO speech
                    if cls == config.TRAIN_CLASS_ID:
                        train_in_frame = True
                        if mode_label != "MINIMAL":
                            draw_train_box(frame, x1, y1, x2, y2)
                        # Boarding window (visual only) — no Telegram, no PA
                        now = time.time()
                        if (now - last_train_alert) > config.TRAIN_ARRIVE_COOLDOWN:
                            last_train_alert = now
                            boarding_window  = True
                            boarding_start   = now
                        continue

                    # Person
                    track_id  = int(box.id[0]) if box.id is not None else -1
                    in_danger = cross_side(cx, cy, lx1, ly1, lx2, ly2) > 0
                    detections_for_zm.append((cx, cy, track_id))

                    if mode_label != "MINIMAL":
                        draw_person_box(frame, x1, y1, x2, y2, track_id, in_danger)

                    if in_danger:
                        current_danger_ids.add(track_id)
                        now   = time.time()
                        state = track_state.get(track_id, {
                            "in_danger": False, "last_trigger": 0.0,
                            "row_id": None, "entry_ts": None,
                        })
                        if (not state["in_danger"] and
                                (now - state["last_trigger"]) > config.VIOLATION_COOLDOWN):
                            ts_str  = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                            ss_path = os.path.join(config.SCREENSHOT_DIR,
                                                   f"{ts_str}_track{track_id}.jpg")
                            cv2.imwrite(ss_path, frame)
                            entry_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            row_id   = db.log_entry(track_id, args.camera, ss_path)
                            alerter.send_violation(ss_path, track_id, args.camera, entry_ts)
                            pa.announce_event("boundary")
                            if config.SOUND_ENABLED:
                                try: pygame.mixer.music.play()
                                except Exception: pass
                            state.update({"in_danger": True, "last_trigger": now,
                                          "row_id": row_id, "entry_ts": entry_ts})
                            track_state[track_id] = state
                            today_v += 1
                    else:
                        state = track_state.get(track_id)
                        if state and state["in_danger"] and state["row_id"]:
                            db.log_exit(state["row_id"], state["entry_ts"])
                            state["in_danger"] = False
                            track_state[track_id] = state

        # Close out disappeared tracks
        for tid, state in list(track_state.items()):
            if tid not in current_danger_ids and state["in_danger"] and state["row_id"]:
                db.log_exit(state["row_id"], state["entry_ts"])
                state["in_danger"] = False
                track_state[tid] = state

        # Zone manager update
        zone_alerts = zm.update(detections_for_zm, train_in_frame=train_in_frame)
        if show_zones and mode_label != "MINIMAL":
            zm.draw(frame, detections_for_zm)

        # Rush detection
        rush_active = zm.rush_detected(detections_for_zm)
        if rush_active:
            pa.announce_event("rush")

        # Process crowd alerts
        active_crowd_zone = ""
        for alert in zone_alerts:
            zone  = alert["zone"]
            zname = zone["name"]
            now   = time.time()
            if (now - crowd_cooldown.get(zname, 0)) > config.PA_COOLDOWN:
                crowd_cooldown[zname] = now
                ts_str  = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                ss_path = os.path.join(config.SCREENSHOT_DIR,
                                       f"{ts_str}_crowd_{zname.replace(' ','_')}.jpg")
                cv2.imwrite(ss_path, frame)
                db.log_crowd_event(zname, args.camera, alert["count"],
                                   zone["max_persons"], alert["type"], ss_path)
                alerter.send_crowd_alert(zname, alert["count"], zone["max_persons"],
                                         alert["type"], ss_path, args.camera)
                pa.announce_zone(zone)
                today_c += 1
                active_crowd_zone = zname

        # Boarding window expiry check
        if boarding_window and (time.time() - boarding_start) > config.TRAIN_ARRIVE_COOLDOWN:
            boarding_window = False

        # Banners
        if current_danger_ids:
            draw_violation_banner(frame, w, h)
        if active_crowd_zone:
            draw_crowd_banner(frame, w, h, active_crowd_zone)
        if rush_active:
            draw_rush_banner(frame, w, h)
        if boarding_window and mode_label != "MINIMAL":
            remaining = int(config.TRAIN_ARRIVE_COOLDOWN - (time.time() - boarding_start))
            draw_boarding_banner(frame, w, h, remaining)

        # Info panel
        if show_info and mode_label != "MINIMAL":
            fps_val = 1.0 / (sum(fps_buf) / len(fps_buf)) if fps_buf else 0
            draw_info_panel(frame, fps_val, len(current_danger_ids),
                            today_v, today_c, detect_on, auto_line_on,
                            boarding_window, zm.get_zone_counts())

        # Watermark
        ts_now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(frame, f"{args.camera}  |  {ts_now}",
                    (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (180, 180, 180), 1)

        config.HEATMAP_ENABLED = heatmap_was

        fps_buf.append(time.time() - t0)
        if len(fps_buf) > 30:
            fps_buf.pop(0)

        if time.time() - last_db_refresh > 60:
            today_v = db.get_today_count()
            today_c = db.get_today_crowd_count()
            last_db_refresh = time.time()

        # Display — resize to correct aspect ratio for window
        if not args.no_display:
            display_frame = cv2.resize(frame, (disp_w, disp_h),
                                       interpolation=cv2.INTER_LINEAR)
            cv2.imshow(config.WINDOW_TITLE, display_frame)

        # Keyboard
        k = cv2.waitKey(1) & 0xFF
        if   k == ord("q"): break
        elif k == ord("a"): lx -= 5
        elif k == ord("d"): lx += 5
        elif k == ord("w"): ly -= 5
        elif k == ord("s"): ly += 5
        elif k == ord("e"): angle += 2
        elif k == ord("r"): angle -= 2
        elif k == ord("z"): thickness += 1
        elif k == ord("x"): thickness = max(1, thickness - 1)
        elif k == ord("t"):
            detect_on = not detect_on
            print(f"[INFO] Detection {'ON' if detect_on else 'OFF'}")
        elif k == ord("h"):
            lx, ly, angle = detect_safety_line(frame)
            print(f"[INFO] Hough -> x={lx} y={ly} angle={angle:.1f}")
        elif k == ord("m"):
            display_mode = (display_mode + 1) % len(DISPLAY_MODES)
            print(f"[INFO] Display: {DISPLAY_MODES[display_mode]}")
        elif k == ord("i"):
            show_info = not show_info
        elif k == ord("c"):
            show_zones = not show_zones
        elif k == ord("p"):
            pa.announce("PA test. Railway platform safety system is active.", key="test")
        elif k == ord("b"):
            # Boarding window — visual banner only, no PA speech
            boarding_window = True
            boarding_start  = time.time()
            print("[INFO] Boarding window activated (visual only).")

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Session ended.")


if __name__ == "__main__":
    main()
