"""Windowless launcher used for autostart when running from source."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keept.app import main  # noqa: E402

raise SystemExit(main())
