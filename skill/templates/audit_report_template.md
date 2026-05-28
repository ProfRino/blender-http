# Audit Report Template

Fill this out **after** running `audit()` to record what was inspected.

## Run

- Script: `scripts/<name>.py` or `examples/<name>.py`
- Audit dir: `<WORKSPACE>/output/audits/<run_name>/`
- Date / iteration:
- Job ID (if streamed):

## Files present

| File | Present | Size sane (~0.5-2 MB) |
|---|---|---|
| 01_front.png |  |  |
| 02_back.png |  |  |
| 03_left.png |  |  |
| 04_right.png |  |  |
| 05_top.png |  |  |
| 06_isometric.png |  |  |
| 07_joint_closeup.png (optional) |  |  |

## Screenshot audit

| Check | Pass / Fail | Notes |
|---|---|---|
| Full model visible in every view |  |  |
| No floating / disconnected parts |  |  |
| No exploded assembly |  |  |
| No obvious gaps at joints |  |  |
| No unintended intersections |  |  |
| Rotations correct (cylinders / beams aligned to expected axes) |  |  |
| Scale plausible (compare against expected bbox) |  |  |
| Materials assigned and visible (not all gray) |  |  |
| Lighting adequate (not pitch black, not blown out) |  |  |
| Camera framing OK (no cropping at edges) |  |  |
| Top view shows useful detail (or is acceptable as roof-only) |  |  |
| No leftover audit cameras / gizmos in renders |  |  |
| Model centred in frame |  |  |

## Required repairs

List any repairs needed before final output. For each, note: which view exposed it, which checklist item, suspected code cause.

1.
2.
3.

## Final status

Pass / Needs repair

If pass: report `OUTPUT` paths to the user.
If needs repair: patch the script, rerun, and produce a new audit report.
