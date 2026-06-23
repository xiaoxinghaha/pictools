"""
pictools/core.py — 图片处理核心逻辑

提供 ICO 生成、格式互转、压缩、resize 等功能。
底层使用 Pillow。
"""

from __future__ import annotations

import io
import os
import struct
from pathlib import Path
from typing import Optional

from PIL import Image

# ── 常量 ─────────────────────────────────────────────────────────────

ICO_DEFAULT_SIZES = [
    (16, 16),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]

OUTPUT_FORMAT_MAP = {
    "PNG": "png",
    "JPEG": "jpg",
    "JPG": "jpg",
    "BMP": "bmp",
    "GIF": "gif",
    "WEBP": "webp",
    "TIFF": "tiff",
    "ICO": "ico",
}

SUPPORTED_INPUT_FORMATS = ["PNG", "JPEG", "JPG", "BMP", "GIF", "WEBP", "TIFF"]
SUPPORTED_OUTPUT_FORMATS = list(OUTPUT_FORMAT_MAP.keys())


# ── 辅助函数 ─────────────────────────────────────────────────────────


def _to_rgb(img: Image.Image, bg_color=(255, 255, 255)) -> Image.Image:
    """将图片转为 RGB（处理透明通道），适合 JPEG 输出。"""
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, bg_color)
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _ensure_dir(filepath: str | Path) -> None:
    """确保输出目录存在。"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)


# ── 核心 API ─────────────────────────────────────────────────────────


def open_image(filepath: str | Path) -> Image.Image:
    """打开图片文件。"""
    return Image.open(filepath)


def get_image_info(filepath: str | Path) -> dict:
    """获取图片基本信息。"""
    img = Image.open(filepath)
    info = {
        "format": img.format,
        "size": img.size,
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "file_size": os.path.getsize(filepath),
    }
    img.close()
    return info


def resize_image(
    image: Image.Image,
    size: tuple[int, int],
    keep_ratio: bool = False,
) -> Image.Image:
    """缩放图片到指定尺寸。"""
    if keep_ratio:
        img_copy = image.copy()
        img_copy.thumbnail(size, Image.LANCZOS)
        return img_copy
    return image.resize(size, Image.LANCZOS)


def save_as_ico(
    image: Image.Image,
    filepath: str | Path,
    sizes: Optional[list[tuple[int, int]]] = None,
) -> str:
    """保存为 ICO 文件，手动构建以保证多尺寸全部正确嵌入。

    内部使用 PNG 格式存储各尺寸图像（现代 ICO 标准方法，
    Pillow / Windows Vista+ 均支持）。

    Args:
        image: Pillow Image 对象。
        filepath: 输出路径。
        sizes: ICO 内含尺寸列表，默认 ICO_DEFAULT_SIZES。

    Returns:
        保存后的文件路径。
    """
    if sizes is None:
        sizes = ICO_DEFAULT_SIZES

    src = image.convert("RGBA")
    _ensure_dir(filepath)

    # 去重排序
    sorted_sizes = _deduplicate_sorted_sizes(sizes)

    # ── 1. 为每个尺寸生成 PNG 数据 ──
    icon_data: list[bytes] = []

    for w, h in sorted_sizes:
        resized = src.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        icon_data.append(buf.getvalue())

    # ── 2. 写 ICO 文件 ──
    count = len(icon_data)
    with open(filepath, "wb") as f:
        # ICO 文件头
        f.write(struct.pack("<HHH", 0, 1, count))

        # 目录条目 (16 字节/个)
        offset = 6 + 16 * count
        for i, png_data in enumerate(icon_data):
            w, h = sorted_sizes[i]
            ico_w = 0 if w >= 256 else w
            ico_h = 0 if h >= 256 else h
            f.write(struct.pack(
                "<BBBBHHII",
                ico_w,
                ico_h,
                0,            # colors
                0,            # reserved
                1,            # planes
                32,           # bpp
                len(png_data),
                offset,
            ))
            offset += len(png_data)

        # 图像数据 (PNG)
        for png_data in icon_data:
            f.write(png_data)

    return str(filepath)


def verify_ico(filepath: str | Path) -> list[dict]:
    """读取 ICO 文件，返回各嵌入尺寸的信息。

    Returns:
        [{ 'width': int, 'height': int, 'size': int, 'valid': bool }, ...]
        空列表表示文件不是有效 ICO。
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        if len(data) < 6:
            return []
        reserved, typ, count = struct.unpack_from("<HHH", data, 0)
        if reserved != 0 or typ != 1 or count == 0:
            return []
        result = []
        for i in range(count):
            off = 6 + i * 16
            entry = data[off : off + 16]
            w = 256 if entry[0] == 0 else entry[0]
            h = 256 if entry[1] == 0 else entry[1]
            img_size = struct.unpack_from("<I", entry, 8)[0]
            img_off = struct.unpack_from("<I", entry, 12)[0]
            valid = (img_off + img_size <= len(data))
            result.append({
                "width": w,
                "height": h,
                "size": img_size,
                "offset": img_off,
                "valid": valid,
            })
        return result
    except Exception:
        return []


def _deduplicate_sorted_sizes(
    sizes: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """去重并从小到大排序（先按面积，再按宽）。"""
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    for s in sorted(sizes, key=lambda x: (x[0] * x[1], x[0])):
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def convert_format(
    image: Image.Image,
    target_format: str,
    **kwargs,
) -> tuple[Image.Image, dict]:
    """准备图片用于格式转换。

    返回 (处理好的 image, 保存参数字典)，因为不同格式需要不同的
    颜色模式和保存参数。

    Args:
        image: 原始 Pillow Image。
        target_format: 目标格式（如 'JPEG', 'PNG'）。
        **kwargs: 可包含 quality, optimize 等。

    Returns:
        (image, save_kwargs)
    """
    fmt = target_format.upper()
    save_kwargs = {}

    if fmt == "JPEG":
        img = _to_rgb(image)
        save_kwargs["quality"] = kwargs.get("quality", 95)
        save_kwargs["optimize"] = True
    elif fmt == "PNG":
        img = image.convert("RGBA") if image.mode != "RGBA" else image.copy()
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        img = image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image.copy()
        save_kwargs["quality"] = kwargs.get("quality", 90)
        save_kwargs["lossless"] = kwargs.get("lossless", False)
    elif fmt == "GIF":
        img = image.convert("P" if image.mode != "P" else image.copy())
        save_kwargs["optimize"] = True
    else:
        img = image.copy()

    # 通用参数
    if "quality" in kwargs and fmt not in ("PNG", "GIF"):
        save_kwargs["quality"] = kwargs["quality"]

    return img, save_kwargs


def compress_image(
    image: Image.Image,
    quality: int = 85,
    max_dimension: Optional[int] = None,
    output_format: Optional[str] = None,
) -> tuple[Image.Image, dict]:
    """压缩图片。

    通过降低质量 + 限制最大尺寸来压缩。

    Args:
        image: Pillow Image 对象。
        quality: JPEG/WEBP 质量 (1-100)。
        max_dimension: 最大边长（像素），超过则等比例缩小。
        output_format: 输出格式，影响保存参数。

    Returns:
        (处理后的 image, 保存参数字典)
    """
    img = image.copy()

    # 1) 按最大边长缩小
    if max_dimension:
        max_side = max(img.size)
        if max_side > max_dimension:
            ratio = max_dimension / max_side
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)

    # 2) 准备保存参数
    fmt = (output_format or img.format or "JPEG").upper()
    save_kwargs = {"optimize": True}

    if fmt == "JPEG":
        img = _to_rgb(img)
        save_kwargs["quality"] = max(1, min(100, quality))
    elif fmt == "PNG":
        img = img.convert("RGBA") if img.mode != "RGBA" else img
        # PNG 用 optimize，quality 不适用
    elif fmt == "WEBP":
        img = img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
        save_kwargs["quality"] = max(1, min(100, quality))
    else:
        save_kwargs["quality"] = max(1, min(100, quality))

    return img, save_kwargs


def save_image(
    image: Image.Image,
    filepath: str | Path,
    save_kwargs: Optional[dict] = None,
) -> str:
    """保存图片到文件。

    Args:
        image: Pillow Image 对象。
        filepath: 输出路径。
        save_kwargs: 传给 image.save() 的额外参数。

    Returns:
        保存后的文件路径。
    """
    _ensure_dir(filepath)
    ext = Path(filepath).suffix.lower()

    if save_kwargs is None:
        save_kwargs = {}

    # ICO 特殊处理 — 始终走手动构建，确保多尺寸可靠
    if ext == ".ico":
        sizes = save_kwargs.pop("sizes", None) if save_kwargs else None
        return save_as_ico(image, filepath, sizes=sizes)

    image.save(filepath, **save_kwargs)
    return str(filepath)


def batch_process_images(
    input_paths: list[str | Path],
    output_dir: str | Path,
    operation: str,
    **kwargs,
) -> list[str]:
    """批量处理图片。

    Args:
        input_paths: 输入图片路径列表。
        output_dir: 输出目录。
        operation: 操作类型 — 'ico', 'convert', 'compress'。
        **kwargs:
            - ico: sizes
            - convert: target_format, quality
            - compress: quality, max_dimension

    Returns:
        输出文件路径列表。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for src_path in input_paths:
        src = Path(src_path)
        image = open_image(src)

        if operation == "ico":
            sizes = kwargs.get("sizes", ICO_DEFAULT_SIZES)
            out_path = output_dir / f"{src.stem}.ico"
            save_as_ico(image, out_path, sizes=sizes)
            results.append(str(out_path))

        elif operation == "convert":
            target_fmt = kwargs.get("target_format", "PNG")
            quality = kwargs.get("quality", 95)
            ext = OUTPUT_FORMAT_MAP.get(target_fmt.upper(), "png")

            # 特殊处理 JPEG -> jpg 扩展名
            if ext == "jpg" and target_fmt.upper() == "JPEG":
                ext = "jpg"
            elif target_fmt.upper() == "JPEG":
                ext = "jpg"

            out_path = output_dir / f"{src.stem}.{ext}"
            img, save_kw = convert_format(image, target_fmt, quality=quality)
            save_image(img, out_path, save_kw)
            results.append(str(out_path))

        elif operation == "compress":
            quality = kwargs.get("quality", 85)
            max_dim = kwargs.get("max_dimension", None)
            fmt = kwargs.get("output_format", None)

            out_ext = OUTPUT_FORMAT_MAP.get(fmt.upper(), src.suffix.lstrip(".")) if fmt else src.suffix.lstrip(".")
            if out_ext == "jpg" and fmt and fmt.upper() == "JPEG":
                out_ext = "jpg"

            out_path = output_dir / f"{src.stem}_compressed.{out_ext}"
            img, save_kw = compress_image(image, quality=quality, max_dimension=max_dim, output_format=fmt)
            save_image(img, out_path, save_kw)
            results.append(str(out_path))

        image.close()

    return results