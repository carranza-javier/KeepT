"""Write the app icon as a multi size .ico (PNG compressed entries).

    python tools/make_icon.py packaging/keept.ico
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from keept.icon import SIZES, render_icon  # noqa: E402


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # noqa: F841
    blobs = []
    for size in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        render_icon(size).save(buf, "PNG")
        blobs.append((size, bytes(buf.data())))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, png in blobs:
        s = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    Path(sys.argv[1]).write_bytes(header + entries + data)
    print("wrote", sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
