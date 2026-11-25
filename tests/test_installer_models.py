from pathlib import Path


def test_installer_models_include_is_up_to_date():
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    import gen_installer_models

    current = (root / "installer" / "models.iss").read_text(encoding="utf-8-sig")
    assert current.replace("\r\n", "\n") == gen_installer_models.render().replace("\r\n", "\n"), \
        "run tools/gen_installer_models.py"
