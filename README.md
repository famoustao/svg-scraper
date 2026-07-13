# 网站文件爬取工具

从网站批量提取任意类型文件的 Python 工具，支持 GUI 界面和命令行两种模式。

## 功能特性

- **11 种预设文件分类**：SVG 矢量图、光栅图像、视频、音频、文档、字体、脚本、样式表、数据/配置、压缩包、可执行文件
- **自定义扩展名**：支持用户输入任意文件扩展名
- **多源提取**：HTML 标签（img/video/audio/source/object/embed/link/script/a）、内联 SVG、CSS url() 引用
- **反爬应对**：UA 轮换、随机延迟、指数退避重试、Session 持久化、robots.txt 检查、Referer 伪装
- **深色主题 GUI**：tkinter 界面，彩色标签按钮选择文件类型，实时日志
- **跨平台**：Windows / Linux / macOS

## 预设文件分类

| 分类 | 扩展名 |
|------|--------|
| SVG 矢量图 | `.svg` |
| 光栅图像 | `.jpg .jpeg .png .gif .bmp .tiff .webp .ico .avif` 等 |
| 视频 | `.mp4 .webm .avi .mov .mkv .flv .wmv .ogv` 等 |
| 音频 | `.mp3 .wav .ogg .flac .aac .m4a .wma .opus` 等 |
| 文档 | `.pdf .doc .docx .xls .xlsx .ppt .pptx .csv .md` 等 |
| 字体 | `.woff .woff2 .ttf .otf .eot` |
| 脚本 | `.js .mjs .cjs` |
| 样式表 | `.css .scss .sass .less` |
| 数据/配置 | `.json .xml .yaml .yml .toml .ini .env` 等 |
| 压缩包 | `.zip .rar .7z .tar .gz .bz2 .xz .iso` 等 |
| 可执行文件 | `.exe .msi .dmg .deb .rpm .apk .sh .bat` 等 |

## 快速开始

### 方式一：直接运行（需要 Python 3.10+）

```bash
pip install -r requirements.txt
python svg_scraper_gui.py      # GUI 界面
python svg_scraper.py URL      # 命令行
```

### 方式二：下载预编译可执行文件

前往 [Releases](../../releases) 或 [Actions](../../actions) 页面下载。

## 命令行用法

```bash
# 默认爬取 SVG
python svg_scraper.py https://example.com

# 按预设分类爬取
python svg_scraper.py https://example.com --category "光栅图像" "文档"

# 自定义扩展名
python svg_scraper.py https://example.com --extensions jpg png webp

# 分类 + 自定义扩展名组合
python svg_scraper.py https://example.com --category "SVG 矢量图" --extensions .webp

# 完整参数
python svg_scraper.py URL -o ./output --category "光栅图像" --delay 1 3 --retries 5 --cross-domain
```

## GitHub Actions 自动编译

推送代码到 `main` 分支自动触发编译。打 tag 发布 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```
