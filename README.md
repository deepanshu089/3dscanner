# Laser Triangulation 3D Scanner — Project Folder Guide

This folder contains everything needed to go from raw scan videos to a
finished 3D model: the captured footage, the hardware capture scripts, and
the single script that turns the footage into a point cloud and mesh.

---

## Folder contents

| File | What it is |
|---|---|
| `scan_up_0deg.h264` | Raw video: laser sweeping the object top-to-bottom, object at 0° |
| `scan_up_120deg.h264` | Same sweep, object rotated 120° |
| `scan_up_240deg.h264` | Same sweep, object rotated 240° |
| `Move_Actuator2.py` | Hardware script: drives the linear actuator (Raspberry Pi GPIO) |
| `video_scan.py` | Hardware script: records video while the actuator sweeps |
| `run_pipeline.py` | **The main script.** Turns the 3 videos into a 3D model |

Everything below (`pointcloud_merged.ply`, `mesh_poisson.ply`, etc.) is
**output** — it gets regenerated every time you run `run_pipeline.py`, so it's
safe to delete and re-run if you ever want a clean slate.

---

## Quick start

```bash
python run_pipeline.py
```

This reads the three `.h264` videos already in this folder and, after a few
minutes, produces four output files (see below). To also pop up an
interactive 3D viewer at the end:

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
   points.
5. **Builds a surface mesh** from the cleaned points, two different ways.

---

## Output files — what each one means

| File | What it is | Do I need it? |
|---|---|---|
| `pointcloud_merged.ply` | Raw 3D points, before cleanup | No — intermediate step only |
| `pointcloud_merged_cleaned.ply` | Same points, noise/spikes removed | Keep if you want the raw point-cloud view |
| `mesh_poisson.ply` | Solid, closed surface — fills unscanned gaps with guessed geometry | **Use this if you just want one "finished-looking" 3D model** |
| `mesh_ballpivot.ply` | Surface built only where real data exists — leaves honest gaps | Use this if you want to show only what was actually measured |

If you only need one result to present, **`mesh_poisson.ply`** is the one
that looks like a complete 3D object.

---

## Viewing the output

**Quickest — one-liner:**
```bash
python -c "import open3d as o3d; o3d.visualization.draw_geometries([o3d.io.read_triangle_mesh('mesh_poisson.ply')])"
```
(Swap in `read_point_cloud(...)` instead of `read_triangle_mesh(...)` for the
two `pointcloud_*.ply` files.)

**Or:** open any `.ply` file in **MeshLab** (File → Import Mesh) for nicer
rendering controls, lighting, and measurement tools.

---

## Known limitation

The scan only covers **3 angles, 120° apart**. A boxy object has flat faces
with sharp edges, so there are real gaps between the three scanned faces —
parts of the surface were simply never facing the camera closely enough at
any of the three positions to be measured. This shows up as visible holes in
`mesh_ballpivot.ply`, and as smoothed-over (partly guessed) regions in
`mesh_poisson.ply`. It's a coverage limitation, not a bug — fixing it means
scanning from more angles (e.g. every 30–45°), which is the main item for the
next phase of the project.

---

## Re-capturing a new scan (on the Raspberry Pi)

1. Run `video_scan.py` while `Move_Actuator2.py` sweeps the actuator, for
   each of the 3 rotation angles, saving each as its own `.h264` file.
2. Copy the three videos to this folder (replacing the existing ones, or
   updating the filenames in `VIDEO_ANGLES` at the top of `run_pipeline.py`).
3. Run `python run_pipeline.py` again.
