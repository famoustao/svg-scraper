#!/usr/bin/env python3
"""
通用网站文件爬取工具
支持从用户指定的网站爬取任意类型的文件，包括：
  - 预设文件分类：图片、视频、音频、文档、字体、脚本、样式表、数据等
  - 内联 <svg> 标签（仅 SVG 模式）
  - 外部文件（<img>, <object>, <embed>, <video>, <audio>, <source>, <link>, <script>）
  - SVG 精灵引用（<use href>, <use xlink:href>）
  - CSS 中的 url() 引用（<style> 标签和 style 属性）
  - <a> 链接中指向目标扩展名的文件

反爬应对策略：
  - User-Agent 轮换
  - 随机请求延迟
  - 指数退避重试
  - Session / Cookie 持久化
  - robots.txt 检查
  - Referer 伪装
  - 自定义请求头
"""

import os
import re
import time
import random
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ---------------------------------------------------------------------------
# 文件类型分类定义
# ---------------------------------------------------------------------------

FILE_CATEGORIES = {
    "SVG 矢量图": {
        "extensions": [".svg"],
        "icon": "fa-bezier-curve",
    },
    "光栅图像": {
        "extensions": [
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
            ".webp", ".ico", ".avif", ".jfif", ".pjpeg", ".ppm", ".pgm",
            ".pbm", ".xpm", ".xbm",
        ],
        "icon": "fa-image",
    },
    "视频": {
        "extensions": [
            ".mp4", ".webm", ".avi", ".mov", ".mkv", ".flv", ".wmv",
            ".m4v", ".ogv", ".3gp", ".mpeg", ".mpg", ".ts", ".m2ts",
        ],
        "icon": "fa-video",
    },
    "音频": {
        "extensions": [
            ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma",
            ".opus", ".mid", ".midi", ".amr", ".aiff",
        ],
        "icon": "fa-music",
    },
    "文档": {
        "extensions": [
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv", ".md",
            ".epub", ".mobi", ".tex",
        ],
        "icon": "fa-file-alt",
    },
    "字体": {
        "extensions": [
            ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ],
        "icon": "fa-font",
    },
    "脚本": {
        "extensions": [".js", ".mjs", ".cjs"],
        "icon": "fa-code",
    },
    "样式表": {
        "extensions": [".css", ".scss", ".sass", ".less"],
        "icon": "fa-palette",
    },
    "数据 / 配置": {
        "extensions": [
            ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".conf",
            ".cfg", ".env", ".properties",
        ],
        "icon": "fa-database",
    },
    "压缩包": {
        "extensions": [
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
            ".zst", ".lzma", ".cab", ".iso", ".dmg",
        ],
        "icon": "fa-file-archive",
    },
    "可执行文件": {
        "extensions": [
            ".exe", ".msi", ".dmg", ".app", ".deb", ".rpm", ".apk",
            ".bin", ".sh", ".bat", ".cmd", ".ps1",
        ],
        "icon": "fa-cog",
    },
}

# 快捷函数：获取所有扩展名
def get_all_extensions() -> list[str]:
    """获取所有预设扩展名"""
    exts = set()
    for cat in FILE_CATEGORIES.values():
        exts.update(cat["extensions"])
    return sorted(exts)

def get_category_extensions(category_name: str) -> list[str]:
    """获取指定分类的扩展名列表"""
    cat = FILE_CATEGORIES.get(category_name)
    return list(cat["extensions"]) if cat else []

def get_category_by_extension(ext: str) -> str | None:
    """根据扩展名查找所属分类"""
    ext_lower = ext.lower()
    for name, cat in FILE_CATEGORIES.items():
        if ext_lower in cat["extensions"]:
            return name
    return None

# 用于匹配 CSS 中的 url()
CSS_URL_PATTERN = re.compile(
    r"""url\(\s*['"]?([^'")]+)(?:#[^'")]*)?['"]?\s*\)""",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 核心爬虫类
# ---------------------------------------------------------------------------

class FileScraper:
    """通用文件爬取器"""

    def __init__(
        self,
        target_extensions: list[str],
        output_dir: str = "./output",
        delay_range: tuple = (1.0, 3.0),
        max_retries: int = 3,
        timeout: int = 30,
        respect_robots: bool = True,
        same_domain_only: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.target_extensions = [e.lower() for e in target_extensions]
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.delay_range = delay_range
        self.max_retries = max_retries
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.same_domain_only = same_domain_only
        self._log_callback = log_callback

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        # 已下载 URL 去重
        self._seen_urls: set[str] = set()
        # robots.txt 缓存
        self._robots_cache: dict[str, RobotFileParser] = {}
        # 统计
        self.stats = {"inline": 0, "external": 0, "skipped": 0, "failed": 0}

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        if self._log_callback:
            self._log_callback(msg)
        else:
            print(msg)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _match_extension(self, url_or_path: str) -> bool:
        """判断 URL/路径是否匹配目标扩展名（含 #fragment）"""
        lower = url_or_path.lower().split("?")[0]
        for ext in self.target_extensions:
            if lower.endswith(ext) or f"{ext}#" in lower:
                return True
        return False

    # ------------------------------------------------------------------
    # 反爬相关
    # ------------------------------------------------------------------

    def _random_headers(self, referer: str | None = None) -> dict:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        if referer:
            headers["Referer"] = referer
        return headers

    def _polite_delay(self):
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def _check_robots(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            rp = RobotFileParser()
            rp.set_url(urljoin(base, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                rp = None
            self._robots_cache[base] = rp
        rp = self._robots_cache[base]
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENTS[0], url)

    def _is_same_domain(self, url: str, base_url: str) -> bool:
        return urlparse(url).netloc == urlparse(base_url).netloc

    # ------------------------------------------------------------------
    # HTTP 请求（带重试）
    # ------------------------------------------------------------------

    def fetch(self, url: str, referer: str | None = None, skip_robots: bool = False) -> requests.Response | None:
        if not skip_robots and not self._check_robots(url):
            self._log(f"  [跳过] robots.txt 禁止抓取: {url}")
            self.stats["skipped"] += 1
            return None

        headers = self._random_headers(referer=referer)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    url, headers=headers, timeout=self.timeout, allow_redirects=True
                )
                if response.status_code == 200:
                    return response

                if response.status_code in (429, 503):
                    wait = 2 ** attempt + random.uniform(0, 1)
                    self._log(f"  [限流] HTTP {response.status_code}，"
                              f"等待 {wait:.1f}s 后重试 ({attempt}/{self.max_retries})")
                    time.sleep(wait)
                    continue

                self._log(f"  [警告] HTTP {response.status_code}: {url}")
                if response.status_code in (403, 401):
                    headers = self._random_headers(referer=referer)
                    time.sleep(2 ** attempt)
                    continue
                return response

            except requests.exceptions.RequestException as e:
                wait = 2 ** attempt + random.uniform(0, 1)
                self._log(f"  [错误] {e}，{wait:.1f}s 后重试 ({attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(wait)
        self._log(f"  [失败] 超过最大重试次数: {url}")
        self.stats["failed"] += 1
        return None

    # ------------------------------------------------------------------
    # 文件 URL 提取
    # ------------------------------------------------------------------

    def extract_inline_svgs(self, soup: BeautifulSoup) -> list[str]:
        """提取页面中所有内联 <svg> 标签（仅当目标含 .svg 时）"""
        if ".svg" not in self.target_extensions:
            return []
        svgs = []
        for svg_tag in soup.find_all("svg"):
            svg_content = str(svg_tag)
            if svg_content.strip():
                svgs.append(svg_content)
        return svgs

    def extract_external_file_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        """从 HTML 标签中提取匹配目标扩展名的外部文件 URL"""
        urls = []

        # <img src>
        for tag in soup.find_all("img", src=True):
            if self._match_extension(tag["src"]):
                urls.append(urljoin(base_url, tag["src"]))

        # <source src> (video/audio)
        for tag in soup.find_all("source", src=True):
            if self._match_extension(tag["src"]):
                urls.append(urljoin(base_url, tag["src"]))

        # <video src / poster>
        for tag in soup.find_all("video"):
            for attr in ("src", "poster"):
                val = tag.get(attr)
                if val and self._match_extension(val):
                    urls.append(urljoin(base_url, val))

        # <audio src>
        for tag in soup.find_all("audio", src=True):
            if self._match_extension(tag["src"]):
                urls.append(urljoin(base_url, tag["src"]))

        # <object data>
        for tag in soup.find_all("object", data=True):
            if self._match_extension(tag["data"]):
                urls.append(urljoin(base_url, tag["data"]))

        # <embed src>
        for tag in soup.find_all("embed", src=True):
            if self._match_extension(tag["src"]):
                urls.append(urljoin(base_url, tag["src"]))

        # <link href> (样式表、字体、图标等)
        for tag in soup.find_all("link", href=True):
            if self._match_extension(tag["href"]):
                urls.append(urljoin(base_url, tag["href"]))

        # <script src>
        for tag in soup.find_all("script", src=True):
            if self._match_extension(tag["src"]):
                urls.append(urljoin(base_url, tag["src"]))

        # <use href / xlink:href> (SVG 精灵)
        for tag in soup.find_all("use"):
            href = tag.get("href") or tag.get("xlink:href") or ""
            if href and self._match_extension(href):
                clean_url = urldefrag(urljoin(base_url, href))[0]
                urls.append(clean_url)

        # <a href> 下载链接
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if self._match_extension(href):
                urls.append(urljoin(base_url, href))

        # 去重
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def extract_css_file_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        """从 <style> 标签和 style 属性中提取 url() 引用"""
        urls = []

        for style_tag in soup.find_all("style"):
            if style_tag.string:
                for match in CSS_URL_PATTERN.findall(style_tag.string):
                    if self._match_extension(match):
                        urls.append(match)

        for tag in soup.find_all(style=True):
            for match in CSS_URL_PATTERN.findall(tag["style"]):
                if self._match_extension(match):
                    urls.append(match)

        # 转为绝对 URL 并去重
        seen = set()
        unique = []
        for u in urls:
            absolute = urljoin(base_url, u.strip())
            if absolute not in seen:
                seen.add(absolute)
                unique.append(absolute)
        return unique

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _safe_filename(self, url: str, index: int) -> str:
        parsed = urlparse(url)
        name = os.path.basename(parsed.path).split("?")[0]
        if not name:
            name = f"file_{index:04d}"
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        return name

    def save_inline_svg(self, content: str, index: int):
        filename = f"inline_svg_{index:04d}.svg"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self._log(f"  [保存] 内联 SVG -> {filepath.name}")
        self.stats["inline"] += 1

    def save_external_file(self, url: str, index: int, referer: str):
        if url in self._seen_urls:
            return
        self._seen_urls.add(url)

        if self.same_domain_only and not self._is_same_domain(url, referer):
            self._log(f"  [跳过] 跨域文件: {url}")
            self.stats["skipped"] += 1
            return

        response = self.fetch(url, referer=referer)
        if response is None:
            return

        # Content-Type 基本验证
        ct = response.headers.get("Content-Type", "").lower()
        # 如果响应明显不是文件（HTML 页面），跳过
        if "text/html" in ct and not any(url.lower().split("?")[0].endswith(e) for e in self.target_extensions):
            self._log(f"  [跳过] HTML 页面非目标文件: {url}")
            self.stats["skipped"] += 1
            return

        filename = self._safe_filename(url, index)
        filepath = self.output_dir / filename

        counter = 1
        while filepath.exists():
            stem = filepath.stem
            suffix = filepath.suffix
            filepath = self.output_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        with open(filepath, "wb") as f:
            f.write(response.content)
        size_kb = len(response.content) / 1024
        self._log(f"  [保存] {url} -> {filepath.name} ({size_kb:.1f} KB)")
        self.stats["external"] += 1

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def scrape(self, url: str):
        ext_str = ", ".join(self.target_extensions)
        self._log("=" * 60)
        self._log(f"目标 URL: {url}")
        self._log(f"目标文件类型: {ext_str}")
        self._log(f"输出目录: {self.output_dir.resolve()}")
        self._log(f"延迟范围: {self.delay_range[0]}-{self.delay_range[1]}s")
        self._log(f"最大重试: {self.max_retries}")
        self._log(f"robots.txt 检查: {'开启' if self.respect_robots else '关闭'}")
        self._log(f"仅同域: {'是' if self.same_domain_only else '否'}")
        self._log("=" * 60)

        # 1. 获取页面（用户直接请求的主页面，跳过 robots.txt 检查）
        self._log("\n[1/4] 正在获取页面...")
        response = self.fetch(url, skip_robots=True)
        if response is None:
            self._log("无法获取页面，退出。")
            return

        if response.encoding is None or response.encoding == "ISO-8859-1":
            response.encoding = response.apparent_encoding

        html = response.text
        final_url = response.url
        soup = BeautifulSoup(html, "html.parser")

        # 2. 提取内联 SVG（仅 .svg 模式）
        self._log("\n[2/4] 提取内联内容...")
        inline_svgs = self.extract_inline_svgs(soup)
        if inline_svgs:
            self._log(f"  找到 {len(inline_svgs)} 个内联 SVG")
            for i, svg in enumerate(inline_svgs):
                self.save_inline_svg(svg, i)
                self._polite_delay()
        else:
            self._log("  无内联内容")

        # 3. 提取外部文件
        self._log("\n[3/4] 提取外部文件...")
        external_urls = self.extract_external_file_urls(soup, final_url)
        self._log(f"  在 HTML 标签中找到 {len(external_urls)} 个匹配文件链接")

        css_urls = self.extract_css_file_urls(soup, final_url)
        if css_urls:
            self._log(f"  在 CSS 中找到 {len(css_urls)} 个匹配文件引用")
            external_urls.extend(css_urls)

        if not external_urls:
            self._log("  未找到匹配的外部文件")

        for i, file_url in enumerate(external_urls):
            self.save_external_file(file_url, i, referer=final_url)
            self._polite_delay()

        # 4. 统计
        self._log("\n[4/4] 完成！")
        self._log("-" * 40)
        self._log(f"  内联保存: {self.stats['inline']}")
        self._log(f"  外部保存: {self.stats['external']}")
        self._log(f"  跳过:     {self.stats['skipped']}")
        self._log(f"  失败:     {self.stats['failed']}")
        self._log(f"  输出目录: {self.output_dir.resolve()}")
        self._log("=" * 60)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def _build_ext_list(args):
    """从命令行参数构建扩展名列表"""
    extensions = []
    if args.category:
        for cat_name in args.category:
            cat = FILE_CATEGORIES.get(cat_name)
            if cat:
                extensions.extend(cat["extensions"])
            else:
                print(f"警告: 未知分类 '{cat_name}'，可用分类: {', '.join(FILE_CATEGORIES.keys())}")
    if args.extensions:
        for ext in args.extensions:
            ext = ext if ext.startswith(".") else f".{ext}"
            if ext.lower() not in [e.lower() for e in extensions]:
                extensions.append(ext.lower())
    if not extensions:
        extensions = [".svg"]
        print("未指定文件类型，默认使用 .svg")
    return extensions


def main():
    parser = argparse.ArgumentParser(
        description="从指定网站爬取文件（支持任意扩展名）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
预设文件分类:
{chr(10).join(f'  {name}: {", ".join(cat["extensions"])}' for name, cat in FILE_CATEGORIES.items())}

示例:
  python svg_scraper.py https://example.com
  python svg_scraper.py https://example.com --category "SVG 矢量图" "光栅图像"
  python svg_scraper.py https://example.com --extensions jpg png gif
  python svg_scraper.py https://example.com --category "光栅图像" --extensions .webp
  python svg_scraper.py https://example.com --extensions pdf docx
        """,
    )
    parser.add_argument("url", help="目标网站 URL")
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="文件保存目录 (默认: ./output)",
    )
    parser.add_argument(
        "--category", "-c",
        nargs="+",
        metavar="NAME",
        help="预设文件分类名称（可多选）",
    )
    parser.add_argument(
        "--extensions", "-e",
        nargs="+",
        metavar="EXT",
        help="自定义文件扩展名，如 jpg png gif（可多选）",
    )
    parser.add_argument(
        "--delay",
        nargs=2,
        type=float,
        default=(1.0, 3.0),
        metavar=("MIN", "MAX"),
        help="请求间隔秒数范围 (默认: 1.0 3.0)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="最大重试次数 (默认: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="请求超时秒数 (默认: 30)",
    )
    parser.add_argument(
        "--no-robots",
        action="store_true",
        help="忽略 robots.txt (默认检查)",
    )
    parser.add_argument(
        "--cross-domain",
        action="store_true",
        help="允许抓取跨域文件 (默认仅同域)",
    )

    args = parser.parse_args()
    extensions = _build_ext_list(args)

    scraper = FileScraper(
        target_extensions=extensions,
        output_dir=args.output,
        delay_range=tuple(args.delay),
        max_retries=args.retries,
        timeout=args.timeout,
        respect_robots=not args.no_robots,
        same_domain_only=not args.cross_domain,
    )
    scraper.scrape(args.url)


if __name__ == "__main__":
    main()
