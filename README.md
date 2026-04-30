# 本地文件浏览器 - Android APK

基于 **Kivy** 开发的 Android 本地文件浏览器，支持文件夹导航、视频播放（多后端可选）和 HEIC/HEIF 图片。

## 功能特性

| 功能 | 说明 |
|------|------|
| 📁 文件夹浏览 | 文件夹与文件混合网格展示，点进/返回，面包屑导航 |
| 🎬 视频播放 | 支持 mp4/avi/mkv/mov/flv/webm 等主流格式 |
| 🖼️ 图片查看 | 支持 jpg/png/gif/webp 以及 **iPhone HEIC/HEIF** |
| ⚙ 多播放器后端 | 可切换 Kivy 内置 / FFmpeg (ffpyplayer) 播放器 |
| 🔍 按类型过滤 | 文件夹/视频/图片/其他 快速筛选 |
| 🧭 路径导航 | 面包屑点击直达、返回上级、历史后退 |

## 截图（待补充）

## 编译 APK

### 方式一：GitHub Actions（推荐）

1. Fork / 创建仓库并 push 代码
2. 进入 Actions 页面，workflow 自动运行
3. 完成后在 Artifacts 下载 APK

### 方式二：本地 Buildozer（需要 Linux / WSL）

```bash
buildozer android debug
```

APK 生成在 `bin/` 目录下。

## 开发

```bash
# 本地运行（Windows/macOS/Linux）
python android-player.py
```

需要 Python 3.10+，安装依赖：

```bash
pip install kivy==2.3.1 Pillow pillow-heif ffpyplayer
```

## 依赖

- **Kivy 2.3.1** — Python GUI 框架
- **Pillow** — 图片处理
- **pillow-heif** — iPhone HEIC/HEIF 格式支持
- **ffpyplayer** — FFmpeg 视频解码（可选后端）
