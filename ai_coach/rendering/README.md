# Rendering

Lightweight video rendering helpers. Use these to produce shareable
artifacts without invoking the full pose / Gemini stacks.

## Quick recipe

| Scenario | Recipe |
|---|---|
| Side-by-side hstack student vs reference | `features/rendering/run_compare.sh <left_video> <right_video>` |

For vstack (vertical Shorts), custom labels, or a slowdown factor, use the Python CLI directly — see below.

## Command

### `render_side_by_side.py` — stack two clips into one MP4

Stacks left/right or top/bottom via ffmpeg's `hstack` / `vstack` filter.
Burns in optional labels via `drawtext` (gracefully drops the labels if
your ffmpeg build was compiled without libfreetype).

```bash
python features/rendering/render_side_by_side.py [options]
```

| Flag | Default | Purpose |
|---|---|---|
| `--left PATH` | required | Left/top input video |
| `--right PATH` | required | Right/bottom input video |
| `--out PATH` | required | Output MP4 |
| `--layout {hstack,vstack}` | `hstack` | hstack = side-by-side; vstack = top/bottom (better for vertical Shorts) |
| `--target-size INT` | `720` | Height (hstack) or width (vstack) to normalize each clip to |
| `--left-label TEXT` | `STUDENT` | Burned-in label on the left/top |
| `--right-label TEXT` | `REFERENCE` | Burned-in label on the right/bottom |
| `--slowdown FLOAT` | `1.0` | `setpts` factor (1.0 = original speed) |
| `--no-shortest` | off | Don't trim output to the shorter input duration |

## Examples

```bash
# Student vs Kohli
python features/rendering/render_side_by_side.py \
    --left  data/raw_videos/student_drive.mp4 \
    --right data/reference_library/videos/cover-drive/kohli-cover-1.mp4 \
    --left-label  "STUDENT" \
    --right-label "VIRAT KOHLI" \
    --out data/reports/student_vs_kohli.mp4

# Vertical stack for Shorts
python features/rendering/render_side_by_side.py \
    --left  data/reference_library/videos/cover-drive/kohli-cover-1.mp4 \
    --right data/reference_library/videos/cover-drive/kohli-explains-cover-1.mp4 \
    --layout vstack \
    --out data/reports/kohli_vs_kohli_vertical.mp4
```

For richer comparisons (synced impact frames + pose-overlay), see the
roadmap entry for `render_comparison_video.py` in
[`/FEATURES.md`](../../FEATURES.md).
