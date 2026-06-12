"""
zone_manager.py — Multi-zone crowd management engine.

Responsibilities
----------------
1. Scale percentage-based zone polygons to actual frame resolution.
2. Count tracked persons per zone every frame.
3. Compute per-track velocity vectors from ByteTrack position history.
4. Detect crowd rush (sudden velocity spike).
5. Maintain a persistent heatmap accumulator.
6. Render all overlays: zone polygons, counts, heatmap, velocity arrows.
7. Return per-zone alert status for the rule engine in main.py.
"""

import time
import collections
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional

import config


# ── Helpers ──────────────────────────────────────────────────

def _scale_polygon(poly_pct: list, w: int, h: int) -> np.ndarray:
    """Convert [(x%, y%), ...] to integer pixel coordinates."""
    return np.array([(int(px * w), int(py * h)) for px, py in poly_pct], dtype=np.int32)


def _point_in_polygon(px: int, py: int, poly: np.ndarray) -> bool:
    return cv2.pointPolygonTest(poly, (float(px), float(py)), False) >= 0


# ── Zone Manager ─────────────────────────────────────────────

class ZoneManager:
    """
    Stateful per-session zone manager.
    Instantiate once, call update() every processed frame.
    """

    def __init__(self, frame_h: int, frame_w: int):
        self.h = frame_h
        self.w = frame_w

        # Pre-scale all zone polygons
        self.zones = []
        for z in config.ZONES:
            self.zones.append({
                **z,
                "poly_px": _scale_polygon(z["polygon"], frame_w, frame_h),
                "current_count": 0,
                "alert_active": False,
                "last_alert_time": 0.0,
            })

        # Velocity history: track_id → deque of (cx, cy) positions
        self._pos_history: Dict[int, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=config.VELOCITY_HISTORY_FRAMES)
        )

        # Heatmap accumulator (float32, single channel)
        self._heatmap_acc = np.zeros((frame_h, frame_w), dtype=np.float32)

        # Rush state
        self._last_rush_alert = 0.0

        # Train / boarding window
        self.train_detected     = False
        self.boarding_window    = False
        self._boarding_start    = 0.0

        # Gaussian kernel for heatmap blobs
        r = config.HEATMAP_RADIUS
        k = cv2.getGaussianKernel(r * 2 + 1, r / 2)
        self._gauss_kernel = k @ k.T  # 2-D gaussian blob

    # ── Public API ────────────────────────────────────────────

    def update(
        self,
        detections: List[Tuple[int, int, int]],   # [(cx, cy, track_id), ...]
        train_in_frame: bool = False,
    ) -> List[dict]:
        """
        Process one frame's detections.

        Parameters
        ----------
        detections      : list of (cx, cy, track_id) for every tracked person
        train_in_frame  : True if a train was detected in this frame

        Returns
        -------
        List of alert dicts for zones that are over threshold:
          {"zone": zone_dict, "count": int, "type": str}
        """
        self._update_boarding_window(train_in_frame)
        self._update_positions(detections)
        self._update_heatmap(detections)
        alerts = self._evaluate_zones(detections)
        return alerts

    def draw(self, frame: np.ndarray, detections: List[Tuple[int, int, int]]) -> None:
        """Render all overlays onto frame in-place."""
        if config.HEATMAP_ENABLED:
            self._draw_heatmap(frame)
        self._draw_zones(frame)
        self._draw_velocity_arrows(frame)
        self._draw_rush_indicator(frame, detections)
        if self.boarding_window:
            self._draw_boarding_banner(frame)

    def get_zone_counts(self) -> Dict[str, int]:
        return {z["name"]: z["current_count"] for z in self.zones}

    def rush_detected(self, detections: List[Tuple[int, int, int]]) -> bool:
        """Return True if average crowd velocity exceeds threshold."""
        if len(detections) < 3:
            return False
        velocities = []
        for cx, cy, tid in detections:
            hist = self._pos_history.get(tid)
            if hist and len(hist) >= 2:
                dx = hist[-1][0] - hist[-2][0]
                dy = hist[-1][1] - hist[-2][1]
                velocities.append((dx**2 + dy**2) ** 0.5)
        if not velocities:
            return False
        avg_v = sum(velocities) / len(velocities)
        now = time.time()
        if avg_v > config.CROWD_VELOCITY_THRESHOLD and (now - self._last_rush_alert) > config.CROWD_RUSH_COOLDOWN:
            self._last_rush_alert = now
            return True
        return False

    # ── Internal ──────────────────────────────────────────────

    def _update_boarding_window(self, train_in_frame: bool) -> None:
        now = time.time()
        if train_in_frame and not self.boarding_window:
            self.boarding_window = True
            self._boarding_start = now
            self.train_detected = True
        if self.boarding_window and (now - self._boarding_start) > config.TRAIN_ARRIVE_COOLDOWN:
            self.boarding_window = False

    def _update_positions(self, detections: List[Tuple[int, int, int]]) -> None:
        for cx, cy, tid in detections:
            self._pos_history[tid].append((cx, cy))

    def _update_heatmap(self, detections: List[Tuple[int, int, int]]) -> None:
        # Decay existing accumulator
        self._heatmap_acc *= config.HEATMAP_DECAY

        r = config.HEATMAP_RADIUS
        h, w = self.h, self.w
        for cx, cy, _ in detections:
            x0, x1 = max(0, cx - r), min(w, cx + r + 1)
            y0, y1 = max(0, cy - r), min(h, cy + r + 1)
            kx0 = r - (cx - x0)
            kx1 = kx0 + (x1 - x0)
            ky0 = r - (cy - y0)
            ky1 = ky0 + (y1 - y0)
            if x1 > x0 and y1 > y0 and kx1 > kx0 and ky1 > ky0:
                blob = self._gauss_kernel[ky0:ky1, kx0:kx1]
                self._heatmap_acc[y0:y1, x0:x1] += blob

    def _evaluate_zones(self, detections: List[Tuple[int, int, int]]) -> List[dict]:
        alerts = []
        for zone in self.zones:
            poly = zone["poly_px"]
            count = sum(1 for cx, cy, _ in detections if _point_in_polygon(cx, cy, poly))
            zone["current_count"] = count

            # Tighten threshold during boarding window
            threshold = zone["max_persons"]
            if self.boarding_window and zone["alert_type"] in ("crowd", "door"):
                threshold = max(1, int(threshold * config.BOARDING_CROWD_MULTIPLIER))

            over = count > threshold
            zone["alert_active"] = over

            if over:
                now = time.time()
                if (now - zone["last_alert_time"]) > config.PA_COOLDOWN:
                    zone["last_alert_time"] = now
                    alerts.append({
                        "zone":  zone,
                        "count": count,
                        "type":  zone["alert_type"],
                    })
        return alerts

    def _draw_heatmap(self, frame: np.ndarray) -> None:
        acc = self._heatmap_acc
        if acc.max() < 1e-3:
            return
        norm = np.clip(acc / (acc.max() + 1e-6), 0, 1)
        norm_u8 = (norm * 255).astype(np.uint8)
        colored = cv2.applyColorMap(norm_u8, cv2.COLORMAP_JET)
        # Mask very low-density areas to keep overlay clean
        mask = (norm_u8 > 20).astype(np.uint8)
        alpha_map = (norm * config.HEATMAP_ALPHA).clip(0, config.HEATMAP_ALPHA)
        for c in range(3):
            frame[:, :, c] = np.where(
                mask,
                (frame[:, :, c] * (1 - alpha_map) + colored[:, :, c] * alpha_map).clip(0, 255).astype(np.uint8),
                frame[:, :, c],
            )

    def _draw_zones(self, frame: np.ndarray) -> None:
        overlay = frame.copy()
        for zone in self.zones:
            color = zone["color_alert"] if zone["alert_active"] else zone["color_safe"]
            cv2.fillPoly(overlay, [zone["poly_px"]], color)
        cv2.addWeighted(overlay, config.ZONE_OVERLAY_ALPHA, frame, 1 - config.ZONE_OVERLAY_ALPHA, 0, frame)

        for zone in self.zones:
            color = zone["color_alert"] if zone["alert_active"] else zone["color_safe"]
            cv2.polylines(frame, [zone["poly_px"]], True, color, 2)

            # Label at centroid
            M = cv2.moments(zone["poly_px"])
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                label = f"{zone['name']}: {zone['current_count']}"
                if zone["alert_active"]:
                    label += " CROWDED" if zone["alert_type"] == "crowd" else " CONGESTED"
                cv2.putText(frame, label, (cx - 70, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2)

    def _draw_velocity_arrows(self, frame: np.ndarray) -> None:
        for tid, hist in self._pos_history.items():
            if len(hist) < 2:
                continue
            dx = hist[-1][0] - hist[-2][0]
            dy = hist[-1][1] - hist[-2][1]
            speed = (dx**2 + dy**2) ** 0.5
            if speed < 3:
                continue
            x, y = hist[-1]
            scale = min(speed * 1.5, 40)
            ex = int(x + dx / (speed + 1e-6) * scale)
            ey = int(y + dy / (speed + 1e-6) * scale)
            arrow_color = (0, 255, 255) if speed < config.CROWD_VELOCITY_THRESHOLD else (0, 80, 255)
            cv2.arrowedLine(frame, (x, y), (ex, ey), arrow_color, 1, tipLength=0.4)

    def _draw_rush_indicator(self, frame: np.ndarray, detections: List[Tuple[int, int, int]]) -> None:
        velocities = []
        for cx, cy, tid in detections:
            hist = self._pos_history.get(tid)
            if hist and len(hist) >= 2:
                dx = hist[-1][0] - hist[-2][0]
                dy = hist[-1][1] - hist[-2][1]
                velocities.append((dx**2 + dy**2) ** 0.5)
        if not velocities:
            return
        avg_v = sum(velocities) / len(velocities)
        bar_w = int(min(avg_v / config.CROWD_VELOCITY_THRESHOLD, 1.0) * 120)
        bar_color = (0, 255, 0) if avg_v < config.CROWD_VELOCITY_THRESHOLD * 0.6 else \
                    (0, 165, 255) if avg_v < config.CROWD_VELOCITY_THRESHOLD else (0, 0, 255)
        cv2.putText(frame, "MVMT", (frame.shape[1] - 175, frame.shape[0] - 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.rectangle(frame, (frame.shape[1] - 140, frame.shape[0] - 45),
                      (frame.shape[1] - 140 + 120, frame.shape[0] - 30), (60, 60, 60), -1)
        if bar_w > 0:
            cv2.rectangle(frame, (frame.shape[1] - 140, frame.shape[0] - 45),
                          (frame.shape[1] - 140 + bar_w, frame.shape[0] - 30), bar_color, -1)

    def _draw_boarding_banner(self, frame: np.ndarray) -> None:
        remaining = int(config.TRAIN_ARRIVE_COOLDOWN - (time.time() - self._boarding_start))
        msg = f"TRAIN BOARDING WINDOW — {remaining}s"
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 28), (w, h), (20, 20, 160), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.putText(frame, msg, (w // 2 - 200, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 220, 60), 2)
