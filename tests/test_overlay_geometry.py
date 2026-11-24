import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("overlay_geometry_check.py")


@pytest.mark.parametrize("scale", ["1", "1.25", "1.5"])
def test_click_and_overlay_map_to_exact_physical_pixels(scale):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=scale)
    proc = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0 and "OK" in proc.stdout, proc.stdout + proc.stderr
