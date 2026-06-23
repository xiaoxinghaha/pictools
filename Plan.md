# 一、整体架构（你这个工具最终长这样）

功能：

- 导入 JPG / PNG
- 设置尺寸（如 256x256）
- 一键生成 ICO（多尺寸）
- 可选：导出 PNG/JPG
- 批量处理

技术栈：

- Python 3.11
- PyQt6（界面）
- Pillow（图片处理）
- PyInstaller（打包 exe）

------

# 二、第一步：环境准备

## 1️⃣ 确认 Python 版本

```bash
python --version
```

必须：

```
Python 3.11.x
```

------

## 2️⃣ 建议创建虚拟环境（强烈推荐）

```bash
python -m venv ico_env
```

进入环境：

### Windows：

```bash
ico_env\Scripts\activate
```

------

# 三、安装必须依赖（核心）

## 1️⃣ 安装 PyQt6（界面）

```bash
pip install PyQt6
```

------

## 2️⃣ 安装图片处理库（核心）

```bash
pip install pillow
```

------

## 3️⃣ 安装工具类库（可选但推荐）

```bash
pip install pyinstaller
```

------

## 4️⃣ 一次性安装（推荐）

```bash
pip install PyQt6 pillow pyinstaller
```

------

# 四、验证环境是否OK

运行：

```bash
python -c "from PIL import Image; print('Pillow OK')"
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt OK')"
```

------

# 五、核心功能代码（可直接运行）

## 📌 main.py（完整最小可用版本）

```python
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel
)
from PIL import Image


class ICOConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICO 生成工具")
        self.setGeometry(300, 200, 400, 200)

        layout = QVBoxLayout()

        self.label = QLabel("请选择图片（PNG/JPG）")
        layout.addWidget(self.label)

        self.btn_open = QPushButton("选择图片")
        self.btn_open.clicked.connect(self.open_file)
        layout.addWidget(self.btn_open)

        self.btn_convert = QPushButton("生成 ICO")
        self.btn_convert.clicked.connect(self.convert_to_ico)
        layout.addWidget(self.btn_convert)

        self.setLayout(layout)

        self.file_path = None

    def open_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )
        if file:
            self.file_path = file
            self.label.setText(f"已选择：{file}")

    def convert_to_ico(self):
        if not self.file_path:
            self.label.setText("请先选择图片")
            return

        img = Image.open(self.file_path).convert("RGBA")

        sizes = [
            (16, 16),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256)
        ]

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 ICO",
            "output.ico",
            "ICO Files (*.ico)"
        )

        if save_path:
            img.save(save_path, format="ICO", sizes=sizes)
            self.label.setText("ICO 生成成功！")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ICOConverter()
    window.show()
    sys.exit(app.exec())
```

------

# 六、运行程序

```bash
python main.py
```

你会看到一个窗口：

- 选择图片
- 点击生成 ICO
- 保存 ico 文件

------

# 七、升级功能（建议你下一步做）

## 1️⃣ 加“自定义尺寸”

比如输入框：

- 16
- 32
- 64
- 128

------

## 2️⃣ 加“压缩功能”

```python
img = img.resize((256, 256), Image.LANCZOS)
```

------

## 3️⃣ 加“格式转换”

```python
img.save("out.png")
img.save("out.jpg", quality=90)
```

------

## 4️⃣ 批量处理文件夹

```python
QFileDialog.getExistingDirectory()
```

------

## 5️⃣ 拖拽导入（高级）

PyQt 支持：

- dragEnterEvent
- dropEvent

------

# 八、打包成 exe（关键）

安装完成后：

```bash
pip install pyinstaller
```

------

## 打包命令：

```bash
pyinstaller -F -w main.py
```

参数说明：

- `-F` 单文件
- `-w` 无黑窗口（GUI程序）

------

## 输出路径：

```
dist/main.exe
```

------

# 九、常见坑（重点）

## ❌ 1. Pillow 不能写 ico

✔ 解决：

```bash
pip install pillow --upgrade
```

------

## ❌ 2. PyQt 报错 DLL

✔ 解决：

```bash
pip install PyQt6-tools
```

------

## ❌ 3. ico 不清晰

✔ 解决：
必须包含多尺寸：

```
16 / 32 / 48 / 128 / 256
```

------

# 十、推荐升级路线（很重要）

如果你要做“工具产品化”，建议这样升级：

### 第一阶段（你现在）

✔ 单图 ICO 转换

### 第二阶段

✔ 批量处理
✔ 多格式互相转换   压缩图片

### 第三阶段

✔ 拖拽 UI
✔ 历史记录

### 第四阶段（产品级）

✔ 主题UI
✔ 右键菜单集成（Windows Explorer）
✔ 安装包

------

