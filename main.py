"""
PicTools — 图片批量处理工具

功能：
  - ICO 生成（多尺寸独立文件）
  - 格式互转（PNG / JPG / BMP / GIF / WEBP / TIFF）
  - 图片压缩（质量 + 尺寸 + 目标文件大小）
  - 批量处理（整个文件夹）

运行:
  python main.py
"""

import os
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from pictools import MainWindow


def _icon_path() -> str:
    """获取图标文件路径（同时兼容开发模式和 PyInstaller 打包模式）。"""
    # PyInstaller 打包后资源在 _MEIPASS 目录
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    # 优先 .ico，其次 .png
    for name in ("logo.ico", "logo.png"):
        p = base / name
        if p.exists():
            return str(p)
    return ""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用图标（任务栏 + 标题栏）
    ico = _icon_path()
    if ico:
        qicon = QIcon(ico)
        app.setWindowIcon(qicon)

    window = MainWindow()
    if ico:
        window.setWindowIcon(QIcon(ico))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()