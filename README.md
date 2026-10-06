# Laser Triangulation 3D Scanner — Project Folder Guide

This folder contains everything needed to go from raw scan videos to a
calibrated 3D point cloud: the captured footage, the hardware capture
scripts, and the single script that turns the footage into the final point
cloud.

---

## Folder contents

| File | What it is |
|---|---|
| `scan_up_0deg.h264` | Raw video: laser sweeping the object top-to-bottom, object at 0° |
| `scan_up_120deg.h264` | Same sweep, object rotated 120° |
| `scan_up_240deg.h264` | Same sweep, object rotated 240° |
| `Move_Actuator2.py` | Hardware script: drives the linear actuator (Raspberry Pi GPIO) |
| `video_scan.py` | Hardware script: records video while the actuator sweeps |
| `run_pipeline.py` | **The main script.** Turns the 3 videos into one cleaned point cloud |

`pointcloud_merged_cleaned.ply` is the **output** — it gets regenerated every
time you run `run_pipeline.py`, so it's safe to delete and re-run if you ever
want a clean slate.

---

## Quick start

```bash
python run_pipeline.py
```

This reads the three `.h264` videos already in this folder and, after a few
minutes, produces one output file: `pointcloud_merged_cleaned.ply`. To also
pop up an interactive 3D viewer at the end:

```bash
python run_pipeline.py --view
```
(Left-drag to rotate, right-drag to pan, scroll to zoom, `Q` to close.)

### Requirements
```bash
pip install opencv-python numpy scipy open3d
```

---

## What the pipeline actually does

1. **Reads each video frame-by-frame** and finds the red laser line in every
   frame, tracking it continuously across the image so it doesn't jump onto
   reflections or overexposed highlights.
2. **Converts pixel positions into real millimetres** using calibration
   values measured from the actual camera and rig (not guessed numbers).
3. **Rotates and merges** the three angle scans into one shared 3D point
   cloud.
4. **Cleans up noise** — removes background-wall points and stray mistracked
   points, and saves the result as `pointcloud_merged_cleaned.ply`.

---

## Output file — what it means

| File | What it is |
|---|---|
| `pointcloud_merged_cleaned.ply` | The final result: a calibrated, merged, noise-cleaned 3D point cloud combining all three scan angles |

This is a **point cloud** (a set of individual 3D dots, not a solid surface).
If you later want an actual closed surface mesh (e.g. for 3D printing), that
would be a separate step on top of this file — ask if you want that added
back in.

---

## Viewing the output

**Quickest — one-liner:**
```bash
python -c "import open3d as o3d; o3d.visualization.draw_geometries([o3d.io.read_point_cloud('pointcloud_merged_cleaned.ply')])"
```

**Or:** open `pointcloud_merged_cleaned.ply` in **MeshLab** (File → Import
Mesh) for nicer rendering controls, lighting, and measurement tools.

---

## Known limitation

The scan only covers **3 angles, 120° apart**. A boxy object has flat faces
with sharp edges, so there are real gaps between the three scanned faces —
parts of the surface were simply never facing the camera closely enough at
any of the three positions to be measured — so `pointcloud_merged_cleaned.ply`
will show three dense clusters of points with real empty gaps between them,
not a fully enclosed surface. It's a coverage limitation, not a bug — fixing
it means scanning from more angles (e.g. every 30–45°), which is the main
item for the next phase of the project.

---

## Re-capturing a new scan (on the Raspberry Pi)

1. Run `video_scan.py` while `Move_Actuator2.py` sweeps the actuator, for
   each of the 3 rotation angles, saving each as its own `.h264` file.
2. Copy the three videos to this folder (replacing the existing ones, or
   updating the filenames in `VIDEO_ANGLES` at the top of `run_pipeline.py`).
3. Run `python run_pipeline.py` again.
