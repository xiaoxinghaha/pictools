"""
PicTools — 图片批量处理工具

功能：
  - ICO 生成（多尺寸）
  - 格式互转（PNG / JPG / BMP / GIF / WEBP / TIFF）
  - 图片压缩（质量 + 尺寸限制）
  - 批量处理（整个文件夹）

运行:
  python main.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from pictools import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()