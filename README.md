# 鼠标拖尾

https://blog.xzt.plus/project/10019445-8829-4592-a3d2-34c340adf54b

功能

- 鼠标移动时，在鼠标位置绘制拖尾效果
- 鼠标点击时，在鼠标位置绘制点击效果
- 可以配置拖尾效果的样式、颜色、大小、透明度等


依赖

```bash
pip install pywin32 pynput
```

运行

```bash
pythonw mouse_trail.pyw
```

构建

```bash
pyinstaller ./mouse_trail.spec
```

产出

`dist` 目录下 `mouse_trail.exe` 文件