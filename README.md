# SVG 爬虫工具

从网站批量提取 SVG 图像的 Python 工具，支持 GUI 界面和命令行两种模式。

## 功能特性

- 支持 4 种 SVG 提取方式：内联 `<svg>`、`<img>/<object>/<embed>` 外部引用、`<use>` 精灵、CSS `url(*.svg)`
- 反爬应对：UA 轮换、随机延迟、指数退避重试、Session 持久化、robots.txt 检查、Referer 伪装
- 深色主题 GUI 界面（tkinter），实时日志输出
- 跨平台支持 Windows / Linux / macOS

## 快速开始

### 方式一：直接运行（需要 Python 3.10+）

```bash
pip install -r requirements.txt
python svg_scraper_gui.py      # GUI 界面
python svg_scraper.py URL      # 命令行
```

### 方式二：下载预编译可执行文件

前往 [Releases](../../releases) 页面下载对应平台的可执行文件，双击即可运行。

## 自动编译

推送代码到 `main` 分支后，GitHub Actions 会自动为 Windows、Linux、macOS 三个平台编译可执行文件，并在 Actions 页面生成可下载的构建产物。

打 tag 发布 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 命令行参数

```
python svg_scraper.py URL [选项]

选项:
  -o, --output DIR      SVG 保存目录（默认: ./svgs_output）
  --delay MIN MAX       请求间隔秒数范围（默认: 1.0 3.0）
  --retries N           最大重试次数（默认: 3）
  --timeout N           请求超时秒数（默认: 30）
  --no-robots           忽略 robots.txt
  --cross-domain        允许跨域抓取
```

## 项目结构

```
svg-scraper/
├── svg_scraper.py            # 核心爬虫逻辑（命令行入口）
├── svg_scraper_gui.py        # GUI 界面入口
├── requirements.txt          # Python 依赖
└── .github/workflows/build.yml  # GitHub Actions 自动编译
```
