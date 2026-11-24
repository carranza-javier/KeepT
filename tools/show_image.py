"""Show an image full screen on the monitor at (x, y) so KeepT can be tested on known content.
    python tools/show_image.py image.png X Y
"""
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv[:1])
screen = QGuiApplication.screenAt(QPoint(int(sys.argv[2]), int(sys.argv[3]))) or app.primaryScreen()
pix = QPixmap(sys.argv[1])
pix.setDevicePixelRatio(screen.devicePixelRatio())
w = QLabel()
w.setWindowTitle("Test screen")
w.setWindowFlags(Qt.FramelessWindowHint)
w.setPixmap(pix)
w.setScreen(screen)
w.setGeometry(screen.geometry())
w.show()
app.exec()
