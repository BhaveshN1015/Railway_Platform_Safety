"""
line_detector.py — Automatic platform safety boundary detection.

Strategy
--------
1. Convert frame to grayscale and apply Canny edge detection.
2. Run Hough Probabilistic Line Transform to find line segments.
3. Cluster segments by angle into two dominant groups (the two rail/platform edges).
4. Compute their vanishing point (intersection) if they converge.
5. Place the safety boundary at a configurable pixel offset from the
   track centre line, perpendicular to the viewing direction.

Falls back to manual defaults (config.py) if detection fails.
"""

import math
import numpy as np
import cv2
from typing import Optional, Tuple

import config


# ------------------------------------------------------------------
# Public interface
# ------------------------------------------------------------------

def detect_safety_line(
    frame: np.ndarray,
    debug: bool = False,
) -> Tuple[int, int, float]:
    """
    Analyse a frame and return (line_x, line_y, angle_deg) for the
    safety boundary. Falls back to config defaults on failure.

    Parameters
    ----------
    frame : BGR image as numpy array
    debug : if True, overlay Hough lines on the frame in-place (for tuning)

    Returns
    -------
    (line_x, line_y, angle_degrees)
    """
    try:
        result = _run_hough(frame, debug=debug)
        if result:
            print(f"[AutoLine] Safety boundary auto-placed at x={result[0]}, y={result[1]}, angle={result[2]:.1f}°")
            return result
    except Exception as e:
        print(f"[AutoLine] Detection failed ({e}), using defaults.")

    return config.DEFAULT_LINE_X, config.DEFAULT_LINE_Y, float(config.DEFAULT_ANGLE)


# ------------------------------------------------------------------
# Internal pipeline
# ------------------------------------------------------------------

def _run_hough(frame: np.ndarray, debug: bool) -> Optional[Tuple[int, int, float]]:
    h, w = frame.shape[:2]

    # Work on bottom 60% of frame (platform edge is in lower portion)
    roi_top = int(h * 0.35)
    roi = frame[roi_top:h, :]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=config.HOUGH_THRESHOLD,
        minLineLength=config.HOUGH_MIN_LENGTH,
        maxLineGap=config.HOUGH_MAX_GAP,
    )

    if lines is None or len(lines) == 0:
        return None

    # Offset y-coordinates back to full-frame coords
    segments = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        y1 += roi_top
        y2 += roi_top
        segments.append((x1, y1, x2, y2))

    if debug:
        for x1, y1, x2, y2 in segments:
            cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 0), 1)

    # Compute angle (deg) for each segment
    def seg_angle(x1, y1, x2, y2):
        return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

    angles = [seg_angle(*s) for s in segments]

    # Cluster into roughly-horizontal (platform edge) vs near-vertical lines
    # Platform edges are typically 10–50° from horizontal in a station view
    platform_segs = [
        s for s, a in zip(segments, angles) if 10 < a < 60 or 120 < a < 170
    ]

    if len(platform_segs) < 2:
        # Try using all segments if narrow cluster is empty
        platform_segs = segments

    # Find the two dominant lines by length
    def seg_len(s):
        return math.hypot(s[2] - s[0], s[3] - s[1])

    platform_segs.sort(key=seg_len, reverse=True)
    top_segs = platform_segs[:min(8, len(platform_segs))]

    # Group into left-leaning vs right-leaning by centroid x
    mid_x = w / 2
    left_segs  = [s for s in top_segs if (s[0] + s[2]) / 2 < mid_x]
    right_segs = [s for s in top_segs if (s[0] + s[2]) / 2 >= mid_x]

    if not left_segs or not right_segs:
        # Cannot distinguish two edges; place boundary using longest line midpoint
        best = top_segs[0]
        mx = (best[0] + best[2]) // 2
        my = (best[1] + best[3]) // 2
        a = seg_angle(*best)
        return int(mx), int(my), a

    # Average representative line for each side
    def avg_line(segs):
        x1 = int(np.mean([s[0] for s in segs]))
        y1 = int(np.mean([s[1] for s in segs]))
        x2 = int(np.mean([s[2] for s in segs]))
        y2 = int(np.mean([s[3] for s in segs]))
        return x1, y1, x2, y2

    L = avg_line(left_segs)
    R = avg_line(right_segs)

    # Safety boundary = midpoint between the two rail/platform edges
    boundary_x = (L[0] + L[2] + R[0] + R[2]) // 4
    boundary_y = (L[1] + L[3] + R[1] + R[3]) // 4

    # Angle of boundary = average of two edge angles, rotated 90°
    angle_L = seg_angle(*L)
    angle_R = seg_angle(*R)
    boundary_angle = ((angle_L + angle_R) / 2 + 90) % 180

    return int(boundary_x), int(boundary_y), boundary_angle
