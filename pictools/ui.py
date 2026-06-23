"""
pictools/ui.py — PyQt6 图形界面

标签页布局：
  1. ICO 生成  — 单图生成多尺寸 ICO
  2. 格式转换  — 多图格式互转
  3. 图片压缩  — 多图质量/尺寸压缩
  4. 批量处理  — 整个文件夹批量操作
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl
from PyQt6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pictools.core import (
    ICO_DEFAULT_SIZES,
    OUTPUT_FORMAT_MAP,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
    batch_process_images,
    compress_image,
    convert_format,
    get_image_info,
    open_image,
    save_as_ico,
    save_image,
    verify_ico,
)


# ── 工具 ─────────────────────────────────────────────────────────────


def _format_size(size_bytes: int) -> str:
    """人性化文件大小显示。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"


def _pixmap_from_path(filepath: str, max_width: int = 160) -> QPixmap:
    """加载图片缩略图。"""
    pix = QPixmap(filepath)
    if pix.isNull():
        return pix
    return pix.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)


def _create_check_pixmaps(size: int = 16):
    """生成绿色背景 + 白色对勾的复选框指示器图片。

    对勾使用 QPainterPath 绘制流畅的 √ 形状（而非文字符号）。

    Returns:
        (checked_pixmap, unchecked_pixmap)
    """
    # ── 已勾选：绿色背景 + 白色 √ ──
    checked = QPixmap(size, size)
    checked.fill(Qt.GlobalColor.transparent)
    p = QPainter(checked)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 绿色背景方块
    p.setBrush(QColor("#4CAF50"))
    p.setPen(QPen(QColor("#388E3C"), 1))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)

    # 白色 √ 对勾（QPainterPath 流畅曲线）
    check_path = QPainterPath()
    # 按 size 比例缩放，让对勾在任意尺寸下都居中美观
    s = size / 16.0
    check_path.moveTo(4 * s, 8 * s)   # 起点（左下短笔）
    check_path.lineTo(7 * s, 11 * s)  # 转折点（底部）
    check_path.lineTo(12 * s, 5 * s)  # 终点（右上长笔）
    pen = QPen(QColor("white"), 2 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QBrush(Qt.GlobalColor.transparent))
    p.drawPath(check_path)
    p.end()

    # ── 未勾选：白色底 + 灰边框 ──
    unchecked = QPixmap(size, size)
    unchecked.fill(Qt.GlobalColor.transparent)
    p = QPainter(unchecked)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("white"))
    p.setPen(QPen(QColor("#aaa"), 1))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
    p.end()

    return checked, unchecked


# ── 标签页基类 ───────────────────────────────────────────────────────


class BaseTab(QWidget):
    """所有标签页的基类，提供共有方法。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666;")

    def set_status(self, msg: str, error: bool = False):
        self.status_label.setText(msg)
        if error:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("color: #666;")

    def info_box(self, title: str, msg: str):
        QMessageBox.information(self, title, msg)

    def warn_box(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)


# ── Tab 1: ICO 生成 ──────────────────────────────────────────────────


class IcoTab(BaseTab):
    """单图 → 多尺寸 ICO"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path: str | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        self.setAcceptDrops(True)

        # ── 左侧：预览 ──
        left = QVBoxLayout()
        self.preview_label = QLabel("未选择图片\n\n拖拽图片到此处")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setStyleSheet(
            "border: 2px dashed #ccc; border-radius: 8px; color: #999;"
        )
        left.addWidget(self.preview_label)
        left.addStretch()

        # ── 右侧：控制区 ──
        right = QVBoxLayout()

        # 文件选择
        file_group = QGroupBox("选择图片")
        fg = QVBoxLayout(file_group)
        self.btn_select = QPushButton("📁 选择图片 (PNG/JPG/BMP/GIF/WEBP)")
        self.btn_select.clicked.connect(self._select_file)
        self.file_label = QLabel("")
        self.file_label.setWordWrap(True)
        fg.addWidget(self.btn_select)
        fg.addWidget(self.file_label)
        right.addWidget(file_group)

        # 尺寸选择
        size_group = QGroupBox("ICO 包含尺寸")
        sg = QGridLayout(size_group)
        self.size_checks: dict[tuple[int, int], QCheckBox] = {}
        default_active = {(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
        for i, s in enumerate(ICO_DEFAULT_SIZES):
            cb = QCheckBox(f"{s[0]}×{s[1]}")
            cb.setChecked(s in default_active)
            self.size_checks[s] = cb
            sg.addWidget(cb, i // 3, i % 3)
        # 自定义尺寸
        sg.addWidget(QLabel("自定义:"), 2, 0)
        self.custom_w = QSpinBox()
        self.custom_w.setRange(1, 1024)
        self.custom_w.setValue(64)
        self.custom_h = QSpinBox()
        self.custom_h.setRange(1, 1024)
        self.custom_h.setValue(64)
        h = QHBoxLayout()
        h.addWidget(self.custom_w)
        h.addWidget(QLabel("×"))
        h.addWidget(self.custom_h)
        sg.addLayout(h, 2, 1, 1, 2)
        right.addWidget(size_group)

        # 操作
        self.btn_convert = QPushButton("🎯 生成 ICO")
        self.btn_convert.clicked.connect(self._convert)
        self.btn_convert.setEnabled(False)
        right.addWidget(self.btn_convert)

        right.addWidget(self.status_label)
        right.addStretch()

        layout.addLayout(left, 1)
        layout.addLayout(right, 2)

    def _select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff)"
        )
        if filepath:
            self._load_image(filepath)

    def _get_selected_sizes(self) -> list[tuple[int, int]]:
        sizes = [s for s, cb in self.size_checks.items() if cb.isChecked()]
        sizes.append((self.custom_w.value(), self.custom_h.value()))
        # 去重并保持顺序
        seen = set()
        unique = []
        for s in sizes:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique

    def _convert(self):
        if not self.file_path:
            self.warn_box("提示", "请先选择图片")
            return

        sizes = self._get_selected_sizes()
        if not sizes:
            self.warn_box("提示", "请至少选择一个尺寸")
            return

        settings = QSettings("PicTools", "图片批量处理")
        last_dir = settings.value("ico/last_save_dir", "")

        # 改为选输出文件夹（每个尺寸一个独立 ICO 文件）
        out_dir = QFileDialog.getExistingDirectory(self, "选择 ICO 输出文件夹", last_dir)
        if not out_dir:
            return

        # 记住目录
        settings.setValue("ico/last_save_dir", out_dir)

        # 为每个尺寸生成独立 ICO 文件，命名: {原名}_{宽}x{高}.ico
        stem = Path(self.file_path).stem
        generated_files: list[str] = []
        failed: list[str] = []

        try:
            img = open_image(self.file_path)
            for w, h in sizes:
                out_name = f"{stem}_{w}x{h}.ico"
                out_path = os.path.join(out_dir, out_name)
                try:
                    save_as_ico(img, out_path, sizes=[(w, h)])
                    generated_files.append(out_name)
                    self.set_status(
                        f"进度: {len(generated_files)}/{len(sizes)} — {out_name}"
                    )
                    QApplication.processEvents()
                except Exception as e:
                    failed.append(f"{out_name}: {e}")
            img.close()

            # 结果汇总
            ok_count = len(generated_files)
            total = len(sizes)
            files_detail = "\n".join(f"  ✓ {f}" for f in generated_files)
            msg = (
                f"ICO 生成完成！\n"
                f"成功 {ok_count}/{total} 个文件\n"
                f"输出目录: {out_dir}\n\n"
                f"{files_detail}"
            )
            if failed:
                msg += "\n\n失败:\n" + "\n".join(f"  ✗ {f}" for f in failed)
            self.set_status(f"✅ ICO 生成完成！{ok_count}/{total} 个文件")
            self.info_box("成功", msg)
        except Exception as e:
            self.set_status(f"❌ 生成失败: {e}", error=True)

    # ── 拖拽支持 ────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile().lower()
                if path.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")):
                    event.acceptProposedAction()
                    self.preview_label.setStyleSheet(
                        "border: 2px solid #4a90d9; border-radius: 8px; color: #4a90d9; "
                        "background-color: #f0f7ff;"
                    )

    def dragLeaveEvent(self, event):
        self.preview_label.setStyleSheet(
            "border: 2px dashed #ccc; border-radius: 8px; color: #999;"
        )

    def dropEvent(self, event):
        self.preview_label.setStyleSheet(
            "border: 2px dashed #ccc; border-radius: 8px; color: #999;"
        )
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._load_image(path)

    def _load_image(self, filepath: str):
        """加载图片文件（供选择文件和拖拽共用）。"""
        self.file_path = filepath
        self.file_label.setText(f"已选择: {filepath}")
        self.btn_convert.setEnabled(True)
        pix = _pixmap_from_path(filepath)
        if not pix.isNull():
            self.preview_label.setPixmap(pix)
        self.set_status(f"已加载: {Path(filepath).name}")


# ── Tab 2: 格式转换 ──────────────────────────────────────────────────


class ConvertTab(BaseTab):
    """多图格式互转"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_list: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.setAcceptDrops(True)

        # 文件选择
        file_group = QGroupBox("选择图片（支持拖拽添加）")
        fg = QHBoxLayout(file_group)
        self.btn_add = QPushButton("📁 添加图片")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.clicked.connect(self._clear_files)
        fg.addWidget(self.btn_add)
        fg.addWidget(self.btn_clear)
        fg.addStretch()
        layout.addWidget(file_group)

        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)

        # 设置
        cfg_group = QGroupBox("转换设置")
        cg = QGridLayout(cfg_group)
        cg.addWidget(QLabel("目标格式:"), 0, 0)
        self.fmt_combo = QComboBox()
        # 排除 ICO（单一图片才生成 ICO）
        formats = [f for f in SUPPORTED_OUTPUT_FORMATS if f != "ICO"]
        self.fmt_combo.addItems(formats)
        self.fmt_combo.currentTextChanged.connect(self._on_format_changed)
        cg.addWidget(self.fmt_combo, 0, 1)

        cg.addWidget(QLabel("质量 (1-100):"), 1, 0)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        self.quality_label = QLabel("95")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        cg.addWidget(self.quality_slider, 1, 1)
        cg.addWidget(self.quality_label, 1, 2)
        layout.addWidget(cfg_group)

        self.btn_convert = QPushButton("🔄 开始转换")
        self.btn_convert.clicked.connect(self._convert)
        layout.addWidget(self.btn_convert)

        layout.addWidget(self.status_label)

    def _on_format_changed(self, fmt: str):
        # JPEG 和 WEBP 显示质量滑块有效
        enabled = fmt in ("JPEG", "WEBP")
        self.quality_slider.setEnabled(enabled)
        self.quality_label.setEnabled(enabled)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff)"
        )
        self._add_file_paths(files)

    def _add_file_paths(self, paths: list[str]):
        """将文件路径列表加入列表（供按钮和拖拽共用）。"""
        count = 0
        for f in paths:
            if f not in self.file_list:
                self.file_list.append(f)
                info = get_image_info(f)
                item = QListWidgetItem(
                    f"{Path(f).name}  ({info['width']}×{info['height']}, "
                    f"{_format_size(info['file_size'])})"
                )
                item.setToolTip(f)
                self.list_widget.addItem(item)
                count += 1
        self.set_status(f"已添加 {count} 个文件，共 {len(self.file_list)} 个")

    def _clear_files(self):
        self.file_list.clear()
        self.list_widget.clear()
        self.set_status("已清空列表")

    def _convert(self):
        if not self.file_list:
            self.warn_box("提示", "请先添加图片")
            return

        settings = QSettings("PicTools", "图片批量处理")
        last_dir = settings.value("convert/last_output_dir", "")
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出文件夹", last_dir)
        if not out_dir:
            return

        settings.setValue("convert/last_output_dir", out_dir)

        target_fmt = self.fmt_combo.currentText()
        quality = self.quality_slider.value()
        total = len(self.file_list)
        success = 0

        for i, src in enumerate(self.file_list):
            try:
                img = open_image(src)
                ext = OUTPUT_FORMAT_MAP.get(target_fmt.upper(), "png")
                if ext == "jpg" and target_fmt.upper() == "JPEG":
                    ext = "jpg"
                elif target_fmt.upper() == "JPEG":
                    ext = "jpg"
                out_name = f"{Path(src).stem}.{ext}"
                out_path = os.path.join(out_dir, out_name)

                processed_img, save_kw = convert_format(img, target_fmt, quality=quality)
                save_image(processed_img, out_path, save_kw)
                img.close()
                success += 1
                self.set_status(f"进度: {i + 1}/{total} — {out_name}")
                QApplication.processEvents()
            except Exception as e:
                self.set_status(f"❌ 转换失败 {Path(src).name}: {e}", error=True)

        self.set_status(f"✅ 转换完成！成功 {success}/{total} 个文件")
        self.info_box("完成", f"成功转换 {success}/{total} 个文件\n输出目录: {out_dir}")

    # ── 拖拽支持 ────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
                ):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
            ):
                paths.append(path)
        self._add_file_paths(paths)


# ── Tab 3: 图片压缩 ──────────────────────────────────────────────────


class CompressTab(BaseTab):
    """多图压缩"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_list: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.setAcceptDrops(True)

        # 文件选择
        file_group = QGroupBox("选择图片（支持拖拽添加）")
        fg = QHBoxLayout(file_group)
        self.btn_add = QPushButton("📁 添加图片")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.clicked.connect(self._clear_files)
        fg.addWidget(self.btn_add)
        fg.addWidget(self.btn_clear)
        fg.addStretch()
        layout.addWidget(file_group)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)

        # ── 压缩设置 ──
        cfg_group = QGroupBox("压缩设置")
        cg = QGridLayout(cfg_group)

        # 行 0: 质量
        cg.addWidget(QLabel("质量 (1-100):"), 0, 0)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(80)
        self.quality_label = QLabel("80")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        cg.addWidget(self.quality_slider, 0, 1)
        cg.addWidget(self.quality_label, 0, 2)

        # 行 1: 缩放模式
        cg.addWidget(QLabel("缩放模式:"), 1, 0)
        self.resize_mode = QComboBox()
        self.resize_mode.addItem("不缩放", "none")
        self.resize_mode.addItem("按比例缩放（最大边长）", "max_dim")
        self.resize_mode.addItem("自定义宽高", "exact")
        self.resize_mode.addItem("按百分比缩放", "percent")
        self.resize_mode.currentIndexChanged.connect(self._on_resize_mode_changed)
        cg.addWidget(self.resize_mode, 1, 1)

        # 行 2: 缩放参数（QStackedWidget 安全切换）
        self.param_stack = QStackedWidget()

        # -- 面板 0: 无参数（不缩放）--
        self.param_stack.addWidget(QWidget())

        # -- 面板 1: 按比例缩放 --
        p_maxdim = QWidget()
        lay_maxdim = QHBoxLayout(p_maxdim)
        lay_maxdim.setContentsMargins(0, 0, 0, 0)
        lay_maxdim.addWidget(QLabel("最大边长"))
        self.max_dim_spin = QSpinBox()
        self.max_dim_spin.setRange(0, 10000)
        self.max_dim_spin.setValue(0)
        self.max_dim_spin.setSpecialValueText("不限")
        lay_maxdim.addWidget(self.max_dim_spin)
        lay_maxdim.addWidget(QLabel("px"))
        lay_maxdim.addStretch()
        self.param_stack.addWidget(p_maxdim)

        # -- 面板 2: 自定义宽高 --
        p_exact = QWidget()
        lay_exact = QHBoxLayout(p_exact)
        lay_exact.setContentsMargins(0, 0, 0, 0)
        lay_exact.addWidget(QLabel("宽"))
        self.exact_w = QSpinBox()
        self.exact_w.setRange(1, 10000)
        self.exact_w.setValue(800)
        lay_exact.addWidget(self.exact_w)
        lay_exact.addWidget(QLabel("×"))
        self.exact_h = QSpinBox()
        self.exact_h.setRange(1, 10000)
        self.exact_h.setValue(600)
        lay_exact.addWidget(self.exact_h)
        lay_exact.addWidget(QLabel("px"))
        lay_exact.addStretch()
        self.param_stack.addWidget(p_exact)

        # -- 面板 3: 按百分比 --
        p_pct = QWidget()
        lay_pct = QHBoxLayout(p_pct)
        lay_pct.setContentsMargins(0, 0, 0, 0)
        lay_pct.addWidget(QLabel("缩放至"))
        self.scale_pct = QSpinBox()
        self.scale_pct.setRange(1, 100)
        self.scale_pct.setValue(50)
        self.scale_pct.setSuffix(" %")
        lay_pct.addWidget(self.scale_pct)
        lay_pct.addStretch()
        self.param_stack.addWidget(p_pct)

        cg.addWidget(self.param_stack, 2, 1)

        # 行 3: 输出格式
        cg.addWidget(QLabel("输出格式:"), 3, 0)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItem("保持原格式", None)
        for f in ["JPEG", "PNG", "WEBP"]:
            self.fmt_combo.addItem(f, f)
        cg.addWidget(self.fmt_combo, 3, 1)

        # 行 4: 目标文件大小
        self.target_check = QCheckBox("限制文件大小：不超过")
        self.target_check.toggled.connect(self._on_target_toggled)
        cg.addWidget(self.target_check, 4, 0)

        self.target_size = QSpinBox()
        self.target_size.setRange(1, 999999)
        self.target_size.setValue(500)
        self.target_size.setEnabled(False)
        cg.addWidget(self.target_size, 4, 1)

        self.target_unit = QComboBox()
        self.target_unit.addItem("KB", 1024)
        self.target_unit.addItem("MB", 1024 * 1024)
        self.target_unit.setEnabled(False)
        cg.addWidget(self.target_unit, 4, 2)

        layout.addWidget(cfg_group)

        self.btn_compress = QPushButton("📦 开始压缩")
        self.btn_compress.clicked.connect(self._compress)
        layout.addWidget(self.btn_compress)

        layout.addWidget(self.status_label)

        # 初始状态：默认显示"不缩放"
        self._on_resize_mode_changed(0)
        self._on_target_toggled(False)

    # ── 缩放模式切换 ──

    def _on_resize_mode_changed(self, idx: int):
        """根据选中的缩放模式切换参数面板。"""
        # 面板索引与 QComboBox 添加顺序一致:
        # 0=不缩放, 1=最大边长, 2=自定义宽高, 3=百分比
        self.param_stack.setCurrentIndex(idx)

    def _on_target_toggled(self, checked: bool):
        self.target_size.setEnabled(checked)
        self.target_unit.setEnabled(checked)

    # ── 文件列表操作 ──

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff)"
        )
        self._add_file_paths(files)

    def _add_file_paths(self, paths: list[str]):
        """将文件路径列表加入列表（供按钮和拖拽共用）。"""
        count = 0
        for f in paths:
            if f not in self.file_list:
                self.file_list.append(f)
                info = get_image_info(f)
                item = QListWidgetItem(
                    f"{Path(f).name}  ({info['width']}×{info['height']}, "
                    f"{_format_size(info['file_size'])})"
                )
                item.setToolTip(f)
                self.list_widget.addItem(item)
                count += 1
        self.set_status(f"已添加 {count} 个文件，共 {len(self.file_list)} 个")

    def _clear_files(self):
        self.file_list.clear()
        self.list_widget.clear()
        self.set_status("已清空列表")

    # ── 开始压缩 ──

    def _compress(self):
        if not self.file_list:
            self.warn_box("提示", "请先添加图片")
            return

        settings = QSettings("PicTools", "图片批量处理")
        last_dir = settings.value("compress/last_output_dir", "")
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出文件夹", last_dir)
        if not out_dir:
            return

        settings.setValue("compress/last_output_dir", out_dir)

        # 收集参数
        quality = self.quality_slider.value()
        mode = self.resize_mode.currentData()
        out_fmt = self.fmt_combo.currentData()

        # 缩放参数
        max_dim = None
        exact_size = None
        scale_percent = None

        if mode == "max_dim":
            max_dim = self.max_dim_spin.value() or None
        elif mode == "exact":
            exact_size = (self.exact_w.value(), self.exact_h.value())
        elif mode == "percent":
            scale_percent = self.scale_pct.value()

        # 目标文件大小
        target_filesize = None
        if self.target_check.isChecked():
            val = self.target_size.value()
            unit = self.target_unit.currentData()
            target_filesize = val * unit

        total = len(self.file_list)
        success = 0
        details: list[str] = []

        for i, src in enumerate(self.file_list):
            try:
                img = open_image(src)
                processed_img, save_kw = compress_image(
                    img,
                    quality=quality,
                    max_dimension=max_dim,
                    exact_size=exact_size,
                    scale_percent=scale_percent,
                    target_filesize=target_filesize,
                    output_format=out_fmt,
                )

                if out_fmt:
                    ext = OUTPUT_FORMAT_MAP.get(out_fmt.upper(), "jpg")
                    if ext == "jpg" and out_fmt.upper() == "JPEG":
                        ext = "jpg"
                else:
                    ext = Path(src).suffix.lstrip(".")

                out_name = f"{Path(src).stem}_compressed.{ext}"
                out_path = os.path.join(out_dir, out_name)
                save_image(processed_img, out_path, save_kw)
                img.close()

                new_size = os.path.getsize(out_path)
                old_size = os.path.getsize(src)
                ratio = (1 - new_size / old_size) * 100 if old_size else 0

                # 显示目标质量信息
                target_q = save_kw.get("_target_quality", None)
                q_info = f", quality目标={target_q}" if target_q else ""

                line = (
                    f"{out_name}  "
                    f"{_format_size(old_size)} → {_format_size(new_size)} "
                    f"(缩减 {ratio:.0f}%){q_info}"
                )
                details.append(line)
                self.set_status(f"进度: {i + 1}/{total} — {out_name}")
                success += 1
                QApplication.processEvents()
            except Exception as e:
                self.set_status(f"❌ 压缩失败 {Path(src).name}: {e}", error=True)

        # 汇总
        msg = (
            f"压缩完成！成功 {success}/{total} 个文件\n"
            f"输出目录: {out_dir}\n\n" + "\n".join(details)
        )
        self.set_status(f"✅ 压缩完成！成功 {success}/{total} 个文件")
        self.info_box("完成", msg)

    # ── 拖拽支持 ────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
                ):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
            ):
                paths.append(path)
        self._add_file_paths(paths)


# ── Tab 4: 批量处理 ──────────────────────────────────────────────────


class BatchTab(BaseTab):
    """批量处理整个文件夹"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.setAcceptDrops(True)

        # 文件夹选择
        dir_group = QGroupBox("选择输入文件夹（支持拖拽文件夹）")
        dg = QHBoxLayout(dir_group)
        self.btn_select_dir = QPushButton("📁 选择文件夹")
        self.btn_select_dir.clicked.connect(self._select_dir)
        self.dir_label = QLabel("未选择")
        self.dir_label.setWordWrap(True)
        dg.addWidget(self.btn_select_dir)
        dg.addWidget(self.dir_label, 1)
        layout.addWidget(dir_group)

        # 操作类型
        op_group = QGroupBox("操作类型")
        og = QVBoxLayout(op_group)
        self.op_combo = QComboBox()
        self.op_combo.addItem("🎯 生成 ICO", "ico")
        self.op_combo.addItem("🔄 格式转换", "convert")
        self.op_combo.addItem("📦 压缩图片", "compress")
        self.op_combo.currentIndexChanged.connect(self._on_op_changed)
        og.addWidget(self.op_combo)
        layout.addWidget(op_group)

        # 动态设置区域
        self.settings_group = QGroupBox("设置")
        self.settings_layout = QVBoxLayout(self.settings_group)
        self._settings_widget: QWidget | None = None
        layout.addWidget(self.settings_group)

        self._rebuild_settings()

        # 输出文件夹
        out_group = QGroupBox("输出文件夹")
        og2 = QHBoxLayout(out_group)
        self.btn_select_out = QPushButton("选择输出文件夹")
        self.btn_select_out.clicked.connect(self._select_out_dir)
        self.out_dir_label = QLabel("未选择（默认: 输入文件夹下 output/）")
        self.out_dir_label.setWordWrap(True)
        og2.addWidget(self.btn_select_out)
        og2.addWidget(self.out_dir_label, 1)
        layout.addWidget(out_group)

        # 进度 & 操作
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.btn_start = QPushButton("🚀 开始处理")
        self.btn_start.clicked.connect(self._start_batch)
        layout.addWidget(self.btn_start)

        layout.addWidget(self.status_label)
        layout.addStretch()

    def _on_op_changed(self):
        self._rebuild_settings()

    def _rebuild_settings(self):
        """根据操作类型重建设置控件。"""
        if self._settings_widget:
            self.settings_layout.removeWidget(self._settings_widget)
            self._settings_widget.deleteLater()
            self._settings_widget = None

        op = self.op_combo.currentData()

        if op == "ico":
            w = QWidget()
            lay = QGridLayout(w)
            self.ico_sizes: dict[tuple[int, int], QCheckBox] = {}
            default_active = {(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
            for i, s in enumerate(ICO_DEFAULT_SIZES):
                cb = QCheckBox(f"{s[0]}×{s[1]}")
                cb.setChecked(s in default_active)
                self.ico_sizes[s] = cb
                lay.addWidget(cb, i // 3, i % 3)
            self._settings_widget = w

        elif op == "convert":
            w = QWidget()
            lay = QGridLayout(w)
            lay.addWidget(QLabel("目标格式:"), 0, 0)
            self.batch_fmt_combo = QComboBox()
            formats = [f for f in SUPPORTED_OUTPUT_FORMATS if f != "ICO"]
            self.batch_fmt_combo.addItems(formats)
            lay.addWidget(self.batch_fmt_combo, 0, 1)
            lay.addWidget(QLabel("质量:"), 1, 0)
            self.batch_quality = QSlider(Qt.Orientation.Horizontal)
            self.batch_quality.setRange(1, 100)
            self.batch_quality.setValue(95)
            self.batch_quality_label = QLabel("95")
            self.batch_quality.valueChanged.connect(lambda v: self.batch_quality_label.setText(str(v)))
            lay.addWidget(self.batch_quality, 1, 1)
            lay.addWidget(self.batch_quality_label, 1, 2)
            self._settings_widget = w

        elif op == "compress":
            w = QWidget()
            lay = QGridLayout(w)
            lay.addWidget(QLabel("质量:"), 0, 0)
            self.batch_comp_quality = QSlider(Qt.Orientation.Horizontal)
            self.batch_comp_quality.setRange(1, 100)
            self.batch_comp_quality.setValue(80)
            self.batch_comp_qlabel = QLabel("80")
            self.batch_comp_quality.valueChanged.connect(lambda v: self.batch_comp_qlabel.setText(str(v)))
            lay.addWidget(self.batch_comp_quality, 0, 1)
            lay.addWidget(self.batch_comp_qlabel, 0, 2)
            lay.addWidget(QLabel("最大边长:"), 1, 0)
            self.batch_max_dim = QSpinBox()
            self.batch_max_dim.setRange(0, 10000)
            self.batch_max_dim.setValue(0)
            self.batch_max_dim.setSpecialValueText("不限")
            lay.addWidget(self.batch_max_dim, 1, 1)
            lay.addWidget(QLabel("输出格式:"), 2, 0)
            self.batch_out_fmt = QComboBox()
            self.batch_out_fmt.addItem("保持原格式", None)
            for f in ["JPEG", "PNG", "WEBP"]:
                self.batch_out_fmt.addItem(f, f)
            lay.addWidget(self.batch_out_fmt, 2, 1)
            self._settings_widget = w

        if self._settings_widget:
            self.settings_layout.addWidget(self._settings_widget)

    def _select_dir(self):
        settings = QSettings("PicTools", "图片批量处理")
        last_dir = settings.value("batch/last_input_dir", "")
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹", last_dir)
        if d:
            settings.setValue("batch/last_input_dir", d)
            self.dir_label.setText(d)
            self.input_dir = d
            self.set_status(f"已选择文件夹: {d}")

    def _select_out_dir(self):
        settings = QSettings("PicTools", "图片批量处理")
        last_dir = settings.value("batch/last_output_dir", "")
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹", last_dir)
        if d:
            settings.setValue("batch/last_output_dir", d)
            self.out_dir_label.setText(d)
            self.output_dir = d

    def _start_batch(self):
        if self._running:
            return

        input_dir = getattr(self, "input_dir", None)
        if not input_dir:
            self.warn_box("提示", "请先选择输入文件夹")
            return

        # 收集图片文件
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
        files = []
        for ext in exts:
            files.extend(Path(input_dir).glob(f"*{ext}"))
            files.extend(Path(input_dir).glob(f"*{ext.upper()}"))
        files = sorted(set(f.name for f in files))  # dedup
        files = [str(Path(input_dir) / f) for f in files]

        if not files:
            self.warn_box("提示", "文件夹内没有找到支持的图片文件")
            return

        # 输出目录
        out_dir = getattr(self, "output_dir", None) or os.path.join(input_dir, "output")

        op = self.op_combo.currentData()
        kwargs = {}

        if op == "ico":
            sizes = [s for s, cb in self.ico_sizes.items() if cb.isChecked()]
            if not sizes:
                self.warn_box("提示", "请至少选择一个 ICO 尺寸")
                return
            kwargs["sizes"] = sizes

        elif op == "convert":
            kwargs["target_format"] = self.batch_fmt_combo.currentText()
            kwargs["quality"] = self.batch_quality.value()

        elif op == "compress":
            kwargs["quality"] = self.batch_comp_quality.value()
            kwargs["max_dimension"] = self.batch_max_dim.value() or None
            kwargs["output_format"] = self.batch_out_fmt.currentData()

        # 在后台线程运行
        self._running = True
        self.btn_start.setEnabled(False)
        self.progress.setValue(0)
        self.set_status(f"正在处理 {len(files)} 个文件…")

        self._batch_files = files
        self._batch_out_dir = out_dir
        self._batch_op = op
        self._batch_kwargs = kwargs

        self._worker = threading.Thread(target=self._batch_worker, daemon=True)
        self._worker.start()

        # 轮询进度
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_worker)
        self._timer.start(200)

    def _batch_worker(self):
        """批量处理工作线程。"""
        try:
            batch_process_images(
                self._batch_files,
                self._batch_out_dir,
                self._batch_op,
                **self._batch_kwargs,
            )
            self._worker_result = "ok"
        except Exception as e:
            self._worker_result = str(e)

    def _check_worker(self):
        if not self._worker.is_alive():
            self._timer.stop()

            result = getattr(self, "_worker_result", "unknown")
            if result == "ok":
                count = len(self._batch_files)
                self.progress.setValue(100)
                self.set_status(f"✅ 批量处理完成！共处理 {count} 个文件")
                self.info_box(
                    "完成",
                    f"批量处理完成！\n"
                    f"处理文件数: {count}\n"
                    f"输出目录: {self._batch_out_dir}"
                )
            else:
                self.set_status(f"❌ 处理失败: {result}", error=True)

            self._running = False
            self.btn_start.setEnabled(True)
        else:
            # 模拟进度（无法精确进度时使用）
            self.progress.setValue(
                self.progress.value() + 1
                if self.progress.value() < 90
                else 90
            )

    # ── 拖拽支持 ────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    event.acceptProposedAction()
                    return
                # 也接受单个图片文件拖入
                if path.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
                ):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.input_dir = path
                self.dir_label.setText(path)
                self.set_status(f"已选择文件夹: {path}")
                return
            # 如果是单个文件，取其所在目录
            if path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
            ):
                self.input_dir = str(Path(path).parent)
                self.dir_label.setText(self.input_dir)
                self.set_status(f"已选择文件夹: {self.input_dir}")
                return


# ── 复选框指示器 ────────────────────────────────────────────────────────


def _setup_checkbox_indicators(parent: QWidget):
    """为所有 QCheckBox 生成绿色背景 + 白色对勾的指示器图片。

    将两张 PNG 写入临时目录，通过 QSS 应用到 parent 后代中的所有复选框。
    返回临时目录路径（用于资源释放）。
    """
    checked_pix, unchecked_pix = _create_check_pixmaps(16)
    tmp_dir = tempfile.mkdtemp(prefix="pictools_cb_")
    checked_path = os.path.join(tmp_dir, "on.png").replace("\\", "/")
    unchecked_path = os.path.join(tmp_dir, "off.png").replace("\\", "/")
    checked_pix.save(checked_path, "PNG")
    unchecked_pix.save(unchecked_path, "PNG")

    parent.setStyleSheet(
        parent.styleSheet()
        + f"""
        QCheckBox::indicator:checked {{
            image: url({checked_path});
        }}
        QCheckBox::indicator:unchecked {{
            image: url({unchecked_path});
        }}
        """
    )

    # 程序退出时清理
    import atexit
    atexit.register(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
    return tmp_dir


# ── 主窗口 ───────────────────────────────────────────────────────────


class MainWindow(QWidget):
    """图片批量处理工具主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicTools — 图片批量处理工具")
        self.setMinimumSize(780, 580)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🖼️  PicTools 图片批量处理工具")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 8px 0;"
        )
        layout.addWidget(title)

        # 生成绿色复选框指示器（绿色背景 + 白色对勾）
        self._tmp_indicators = _setup_checkbox_indicators(self)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(IcoTab(), "🎯 ICO 生成")
        self.tabs.addTab(ConvertTab(), "🔄 格式转换")
        self.tabs.addTab(CompressTab(), "📦 图片压缩")
        self.tabs.addTab(BatchTab(), "📁 批量处理")
        layout.addWidget(self.tabs)

        # 底部信息
        footer = QLabel(
            "支持格式: PNG / JPG / BMP / GIF / WEBP / TIFF → ICO / PNG / JPG / BMP / GIF / WEBP"
        )
        footer.setStyleSheet("color: #888; font-size: 12px; padding: 4px 0;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)