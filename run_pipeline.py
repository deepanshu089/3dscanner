#!/usr/bin/env python3
"""
run_pipeline.py

Single end-to-end script: raw scan videos -> calibrated, merged, cleaned 3D
point cloud.

Consolidates what used to be four separate steps (extract_frames.py,
process_scan.py, build_pointcloud_multiangle.py, view_pointcloud.py) into
one pass per video, processed frame-by-frame in memory (no intermediate
.jpg/.npy files written to disk).

Usage:
    python run_pipeline.py [--view]

Reads:
    scan_up_0deg.h264, scan_up_120deg.h264, scan_up_240deg.h264

Writes:
    pointcloud_merged_cleaned.ply  calibrated, merged, outlier/spike-cleaned
                                    point cloud (the only output file)

Pass --view to open the cleaned cloud in an interactive Open3D window
after processing.
"""

import sys
import numpy as np
import cv2
from scipy.signal import find_peaks
from scipy.ndimage import median_filter
import open3d as o3d

# ============================================
# Input videos: angle (degrees) -> file
# ============================================
VIDEO_ANGLES = {
    0:   "scan_up_0deg.h264",
    120: "scan_up_120deg.h264",
    240: "scan_up_240deg.h264",
}
DIRECTION = "up"  # all three scans were captured sweeping the actuator upward

# ============================================
# Laser-line tracking parameters
# ============================================
MIN_HEIGHT = 80        # minimum score value for a peak to be considered at all
MIN_PROMINENCE = 20    # minimum peak prominence (ignores flat noise)
MAX_JUMP = 15           # max row distance allowed between adjacent columns' tracked point
DRIFT_WINDOW = 41      # column window (odd) for the local-median drift check
DRIFT_MAX_DEV = 12     # reject a point if it deviates more than this many px
                        # from the local median row - MAX_JUMP alone only
                        # bounds step-to-step movement, so a slow one-sided
                        # drift over many columns can still wander far off
                        # the real surface without ever violating it

# ============================================
# Geometric calibration (derived from measured rig geometry, not guessed)
# ============================================
ACTUATOR_SPEED_MM_PER_SEC = 3.75
CAPTURE_INTERVAL_SEC = 0.040
MM_PER_PIXEL_X = 0.338  # Camera Module 3 standard FOV (66deg H) at 500mm
                         # working distance: D / (imgW/2 / tan(HFOV/2))
Z_SCALE = 1.333  # real measured box depth (120mm) / its measured row-shift
                  # from the background baseline (90px median, angle 0 scan)
REFERENCE_ROW = 706   # measured background-wall baseline row
REFERENCE_COL = 960   # image horizontal center (1920px wide) - must align
                       # with the rotation axis so each angle's cloud wraps
                       # around a shared center instead of swinging out
MIN_Z_MM = 8.0  # drop points within this distance of the background wall
                 # (wall row jitters ~5px = ~6.7mm at this Z_SCALE)

# ============================================
# Point cloud cleanup
# ============================================
RADIUS_CUTOFF_MM = 200.0  # drop points beyond this XZ-radius from the
                           # cloud's robust center - catches thin "spike"
                           # artifacts from occasional mistracked columns
NB_NEIGHBORS = 20
STD_RATIO = 2.0

OUT_CLEAN_PLY = "pointcloud_merged_cleaned.ply"


# ----------------------------------------
# Stage 1: laser centerline tracking (per frame)
# ----------------------------------------
def compute_score(img):
    """Combined redness + brightness score. Redness alone collapses to ~0 on
    the overexposed white core of the laser line, so brightness is added to
    keep that region detectable, while still letting nearest-neighbor
    tracking reject pedestal-reflection glow (a very different row)."""
    b, g, r = cv2.split(img)
    b = b.astype(np.float32)
    g = g.astype(np.float32)
    r = r.astype(np.float32)
    redness = np.clip(r - np.maximum(g, b), 0, None)
    brightness = (r + g + b) / 3.0
    return redness + 0.6 * brightness


def reject_drift_outliers(row_positions, window=DRIFT_WINDOW, max_dev=DRIFT_MAX_DEV):
    """Local-median drift check: NaNs out any point that deviates too far
    from a local median reference, catching slow drift that per-step jump
    limits alone let through."""
    valid = ~np.isnan(row_positions)
    if valid.sum() < 3:
        return row_positions
    w = len(row_positions)
    idx = np.arange(w)
    filled = np.interp(idx, idx[valid], row_positions[valid])
    local_median = median_filter(filled, size=window, mode="nearest")
    deviation = np.abs(row_positions - local_median)
    keep = valid & (deviation <= max_dev)
    cleaned = np.full(w, np.nan, dtype=np.float32)
    cleaned[keep] = row_positions[keep]
    return cleaned


def track_line(score, seed_col):
    """Track the laser centerline across all columns starting from seed_col,
    walking outward in both directions and always choosing the candidate
    peak nearest the previous column's row - forcing one continuous path
    instead of hopping between two valid surfaces (e.g. a fold/seam)."""
    h, w = score.shape

    col_peaks = [None] * w
    for c in range(w):
        peaks, props = find_peaks(score[:, c], height=MIN_HEIGHT, prominence=MIN_PROMINENCE)
        col_peaks[c] = (peaks, props.get("peak_heights", np.array([])))

    row_positions = np.full(w, np.nan, dtype=np.float32)

    peaks, heights = col_peaks[seed_col]
    if len(peaks) == 0:
        for offset in range(1, 50):
            for c in (seed_col + offset, seed_col - offset):
                if 0 <= c < w:
                    peaks, heights = col_peaks[c]
                    if len(peaks) > 0:
                        seed_col = c
                        break
            if len(peaks) > 0:
                break
        if len(peaks) == 0:
            return np.empty((0, 2))

    best_idx = np.argmax(heights)
    row_positions[seed_col] = peaks[best_idx]
    prev_row = peaks[best_idx]

    for c in range(seed_col + 1, w):
        peaks, heights = col_peaks[c]
        if len(peaks) == 0:
            continue
        dists = np.abs(peaks - prev_row)
        nearest = np.argmin(dists)
        if dists[nearest] <= MAX_JUMP:
            row_positions[c] = peaks[nearest]
            prev_row = peaks[nearest]

    prev_row = row_positions[seed_col]
    for c in range(seed_col - 1, -1, -1):
        peaks, heights = col_peaks[c]
        if len(peaks) == 0:
            continue
        dists = np.abs(peaks - prev_row)
        nearest = np.argmin(dists)
        if dists[nearest] <= MAX_JUMP:
            row_positions[c] = peaks[nearest]
            prev_row = peaks[nearest]

    row_positions = reject_drift_outliers(row_positions)
    row_positions = reject_drift_outliers(row_positions)  # second pass tightens ragged chains

    valid_cols = np.nonzero(~np.isnan(row_positions))[0]
    coords = np.stack([row_positions[valid_cols], valid_cols.astype(np.float32)], axis=1)
    return coords


# ----------------------------------------
# Stage 2: coordinate conversion + rotation into shared frame
# ----------------------------------------
def rotate_point(x, z, angle_degrees):
    """Rotate a point (x, z) around the vertical (Y) axis so each angle's
    scan wraps around a shared center instead of overlapping flat."""
    theta = np.radians(angle_degrees)
    x_rot = x * np.cos(theta) - z * np.sin(theta)
    z_rot = x * np.sin(theta) + z * np.cos(theta)
    return x_rot, z_rot


def process_video(video_path, angle_degrees):
    """Read every frame of one angle's video, track the laser line, and
    return the list of rotated (x, y, z) mm points for that angle."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ! Could not open video: {video_path}")
        return []

    points = []
    frame_idx = 0
    success_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        score = compute_score(frame)
        seed_col = frame.shape[1] // 2
        coords = track_line(score, seed_col)

        if len(coords) >= 10:
            travel_mm = frame_idx * CAPTURE_INTERVAL_SEC * ACTUATOR_SPEED_MM_PER_SEC
            y_mm = -travel_mm if DIRECTION == "down" else travel_mm

            for row, col in coords:
                z_mm = (row - REFERENCE_ROW) * Z_SCALE
                if abs(z_mm) < MIN_Z_MM:
                    continue  # background wall, not the object's surface
                x_mm = (col - REFERENCE_COL) * MM_PER_PIXEL_X
                x_rot, z_rot = rotate_point(x_mm, z_mm, angle_degrees)
                points.append((x_rot, y_mm, z_rot))
            success_count += 1

        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  ...{frame_idx} frames processed")

    cap.release()
    print(f"  {success_count}/{frame_idx} frames tracked -> {len(points)} points")
    return points


# ----------------------------------------
# Stage 3: point cloud cleanup
# ----------------------------------------
def clean_point_cloud(points):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    print(f"  {len(pcd.points)} points loaded")

    pts = np.asarray(pcd.points)
    cx = np.median(pts[:, 0])
    cz = np.median(pts[:, 2])
    r = np.hypot(pts[:, 0] - cx, pts[:, 2] - cz)
    pcd = pcd.select_by_index(np.nonzero(r <= RADIUS_CUTOFF_MM)[0])
    print(f"  {len(pcd.points)} points kept after radial spike removal")

    pcd_clean, _ = pcd.remove_statistical_outlier(nb_neighbors=NB_NEIGHBORS, std_ratio=STD_RATIO)
    print(f"  {len(pcd_clean.points)} points kept after statistical outlier removal")

    pcd_clean.paint_uniform_color([0.9, 0.7, 0.1])
    o3d.io.write_point_cloud(OUT_CLEAN_PLY, pcd_clean)
    return pcd_clean


def main():
    all_points = []
    for angle, video_path in VIDEO_ANGLES.items():
        print(f"Processing angle {angle} deg from {video_path}...")
        all_points.extend(process_video(video_path, angle))

    print(f"\nTotal merged points: {len(all_points)}")
    if not all_points:
        print("No points generated - check that the video files are present.")
        return

    print("\nCleaning point cloud...")
    pcd_clean = clean_point_cloud(all_points)
    print(f"Saved cleaned point cloud: {OUT_CLEAN_PLY}")

    if "--view" in sys.argv:
        print("\nOpening interactive viewer (close window or press Q to exit)...")
        o3d.visualization.draw_geometries(
            [pcd_clean], window_name="Scanned Object - Point Cloud", width=1280, height=800
        )


if __name__ == "__main__":
    main()
