# 🖼️ PicTools 图片批量处理工具

一个基于 PyQt6 + Pillow 的桌面图片处理工具，支持 **ICO 生成、格式互转、图片压缩、批量处理** 四大功能，操作简单，开箱即用。

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)
![Pillow](https://img.shields.io/badge/Pillow-latest-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## ✨ 功能特性

### 🎯 ICO 生成
- 导入 PNG / JPG / BMP / GIF / WEBP / TIFF 单张图片
- 勾选需要的尺寸（16/32/48/64/128/256 + 自定义任意尺寸）
- **每个尺寸生成独立的 ICO 文件**，命名格式：`{原名}_{宽}x{高}.ico`
- 支持拖拽图片到界面直接加载

### 🔄 格式互转
- 多图批量转换：PNG ↔ JPG ↔ BMP ↔ GIF ↔ WEBP ↔ TIFF
- 可调节质量参数（JPEG / WEBP）
- 自动处理透明通道（RGBA → JPEG 时合成白底）
- 拖拽多图批量添加

### 📦 图片压缩
- 调整质量（1-100）压缩文件体积
- 限制最大边长，等比例缩小
- 实时显示压缩前后大小对比和缩减比例
- 可指定输出格式或保持原格式

### 📁 批量处理
- 选整个文件夹批量处理（ICO / 转换 / 压缩）
- 后台线程处理 + 进度条，不阻塞界面
- 支持拖拽文件夹直接加载

### 🎨 用户体验
- **绿色复选框**（白色 √ 对勾，QPainterPath 绘制）
- **记住上次目录**（QSettings 持久化所有保存/输出路径）
- **拖拽支持**（图片 + 文件夹）
- 标签页布局，功能清晰分区

---

## 📦 项目结构

```
图片批量处理/
├── main.py                  # 程序入口
├── pictools/
│   ├── __init__.py          # 包初始化
│   ├── core.py              # 图片处理核心逻辑（Pillow）
│   └── ui.py                # PyQt6 图形界面
├── venv/                    # 虚拟环境（已配置，未提交）
├── Plan.md                  # 开发计划
├── Agents.md                # 开发规范
├── README.md
└── .gitignore
```

---

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Windows 10/11（推荐，亦支持 Linux/macOS）

### 方式一：使用现有虚拟环境

项目已自带 `venv` 虚拟环境（已安装 PyQt6 + Pillow），直接运行：

```bash
# Windows
.\venv\Scripts\python.exe main.py

# 或先激活虚拟环境
.\venv\Scripts\activate
python main.py
```

### 方式二：自己搭建环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 安装依赖
pip install PyQt6 pillow
```

### 运行程序

```bash
python main.py
```

---

## 📖 使用说明

### 1. ICO 生成
1. 切换到 **🎯 ICO 生成** 标签页
2. 点击 **📁 选择图片** 或直接拖拽图片到预览区
3. 勾选需要的尺寸（可输入自定义尺寸）
4. 点击 **🎯 生成 ICO**
5. 选择输出文件夹 → 自动生成每个尺寸的独立 ICO 文件

### 2. 格式转换
1. 切换到 **🔄 格式转换** 标签页
2. 点击 **📁 添加图片** 或拖拽多张图片
3. 选择目标格式（PNG / JPG / BMP / GIF / WEBP / TIFF）
4. 调整质量（JPEG / WEBP 有效）
5. 点击 **🔄 开始转换** → 选输出文件夹

### 3. 图片压缩
1. 切换到 **📦 图片压缩** 标签页
2. 添加图片（按钮或拖拽）
3. 设置压缩质量、最大边长、输出格式
4. 点击 **📦 开始压缩** → 实时显示压缩效果

### 4. 批量处理
1. 切换到 **📁 批量处理** 标签页
2. 选择输入文件夹（按钮或拖拽文件夹）
3. 选择操作类型（ICO / 转换 / 压缩）和参数
4. 选择输出文件夹（默认输入文件夹下的 `output/`）
5. 点击 **🚀 开始处理** → 后台处理 + 进度条

---

## 🔧 技术栈

| 组件 | 用途 |
|------|------|
| **Python 3.11** | 运行环境 |
| **PyQt6** | 图形界面框架 |
| **Pillow (PIL)** | 图片处理（格式转换、压缩、ICO 生成） |
| **QSettings** | 持久化保存用户上次操作目录 |
| **QPainterPath** | 绘制自定义复选框对勾 |

---

## 🛠️ 核心模块说明

### `pictools/core.py` — 图片处理核心
| 函数 | 功能 |
|------|------|
| `open_image()` | 打开图片文件 |
| `get_image_info()` | 获取图片信息（尺寸、格式、大小） |
| `save_as_ico()` | 生成 ICO 文件（手动构建，保证多尺寸可靠） |
| `convert_format()` | 准备图片用于格式转换 |
| `compress_image()` | 压缩图片（质量 + 尺寸） |
| `save_image()` | 保存图片到文件 |
| `verify_ico()` | 验证 ICO 文件实际嵌入的尺寸 |
| `batch_process_images()` | 批量处理图片 |

### `pictools/ui.py` — PyQt6 界面
| 类 | 功能 |
|----|------|
| `MainWindow` | 主窗口（4 个标签页） |
| `IcoTab` | ICO 生成标签页（单图 → 多 ICO） |
| `ConvertTab` | 格式转换标签页（多图互转） |
| `CompressTab` | 图片压缩标签页 |
| `BatchTab` | 批量处理标签页（文件夹批量） |

---

## 📦 打包成 EXE（可选）

使用 PyInstaller 打包为单个可执行文件：

```bash
pip install pyinstaller

# 打包（无控制台窗口）  PicTools.exe
pyinstaller -F -w --name PicTools --icon logo.ico main.py

# 输出在 dist/main.exe
```

---

## 📝 开发规范

项目遵循 `Agents.md` 中的开发规范：
- 修改代码前先说明计划
- 改完之后要跑测试
- 不改生产配置
- 易维护，避免过度设计
- 遵守项目现有代码风格

---

## 📄 许可证

本项目仅供学习交流使用。
