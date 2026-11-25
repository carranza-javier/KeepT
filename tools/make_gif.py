"""Build docs/keept-demo.gif from the frames written by tools/record_demo.py (needs Pillow).

    python tools/make_gif.py shots/demo_frames docs/keept-demo.gif 960
Frame file names carry their display time: 012_60.png is shown for 60 ms.
"""

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    frames_dir, out, width = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    files = sorted(frames_dir.glob("*.png"))
    frames, durations = [], []
    for f in files:
        img = Image.open(f).convert("RGB")
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        frames.append(img.quantize(colors=192, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
        durations.append(int(f.stem.split("_")[1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    frames[-1].convert("RGB").save(out.with_name(out.stem.replace("demo", "translated") + ".png"), optimize=True)
    print(out, f"{out.stat().st_size / 2**20:.1f} MB, {len(frames)} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
