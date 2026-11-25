"""Tray "Languages" window: the target language and the languages to translate from, with the
download size, as on the installer's language page. Only used from the tray, never in the main flow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel,
                               QVBoxLayout)

from . import i18n
from .icon import app_icon
from .languages import CODES
from .translate import setup_plan


def _mb(n: int) -> int:
    return round(n / 2**20)


class LanguagesDialog(QDialog):
    def __init__(self, store, target: str, sources: list[str]):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.store = store
        self.setWindowTitle(i18n.tr("languages_title"))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(i18n.tr("languages_into")))
        self.target = QComboBox()
        for code in CODES:
            self.target.addItem(i18n.lang_name(code), code)
        self.target.setCurrentIndex(list(CODES).index(target))
        lay.addWidget(self.target)

        lay.addSpacing(8)
        lay.addWidget(QLabel(i18n.tr("languages_from")))
        grid = QGridLayout()
        self.boxes: dict[str, QCheckBox] = {}
        for i, code in enumerate(CODES):
            box = QCheckBox(i18n.lang_name(code))
            box.setChecked(code in sources or code == target)
            box.toggled.connect(self.update_size)
            grid.addWidget(box, i // 2, i % 2)
            self.boxes[code] = box
        lay.addLayout(grid)

        lay.addSpacing(8)
        self.size = QLabel()
        self.size.setWordWrap(True)
        lay.addWidget(self.size)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.target.currentIndexChanged.connect(self._target_changed)
        self.update_size()
        self.resize(420, 0)

    def chosen_target(self) -> str:
        return self.target.currentData()

    def chosen_sources(self) -> list[str]:
        return [c for c, b in self.boxes.items() if b.isChecked()]

    def _target_changed(self) -> None:
        self.boxes[self.chosen_target()].setChecked(True)
        self.update_size()

    def update_size(self) -> None:
        tgt, src = self.chosen_target(), self.chosen_sources()
        need = setup_plan.download_bytes(self.store, tgt, src)
        free = sum(m.size_bytes for m in self.store.installed()
                   if (m.src, m.tgt) in set(setup_plan.unneeded_installed(self.store, tgt, src)))
        lines = [i18n.tr("languages_download", mb=max(1, _mb(need))) if need else i18n.tr("languages_ready")]
        if free:
            lines.append(i18n.tr("languages_free", mb=max(1, _mb(free))))
        self.size.setText("\n".join(lines))
