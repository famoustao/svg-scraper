#!/usr/bin/env python3
"""
SVG 图像爬取工具
从用户指定的网站爬取所有 SVG 图像，包括：
  - 内联 <svg> 标签
  - 外部 SVG 文件（<img src>, <object data>, <embed src>）
  - SVG 精灵引用（<use href>, <use xlink:href>）
  - CSS 中的 url(*.svg) 引用（<style> 标签和 style 属性）

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

# 用于匹配 CSS 中的 url(*.svg)
CSS_SVG_PATTERN = re.compile(
    r"""url\(\s*['"]?([^'")]+\.svg)(?:#[^'")]*)?['"]?\s*\)""",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 核心爬虫类
# ---------------------------------------------------------------------------

class SVGScraper:
    """SVG 图像爬取器"""

    def __init__(
        self,
        output_dir: str = "./svgs_output",
        delay_range: tuple = (1.0, 3.0),
        max_retries: int = 3,
        timeout: int = 30,
        respect_robots: bool = True,
        same_domain_only: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
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
        # robots.txt 缓存: domain -> RobotFileParser
        self._robots_cache: dict[str, RobotFileParser] = {}
        # 统计
        self.stats = {"inline": 0, "external": 0, "skipped": 0, "failed": 0}

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        """输出日志，支持回调"""
        if self._log_callback:
            self._log_callback(msg)
        else:
            print(msg)

    # ------------------------------------------------------------------
    # 反爬相关
    # ------------------------------------------------------------------

    def _random_headers(self, referer: str | None = None) -> dict:
        """生成随机请求头"""
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        if referer:
            headers["Referer"] = referer
        return headers

    def _polite_delay(self):
        """随机延迟，避免请求过快"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def _check_robots(self, url: str) -> bool:
        """检查 robots.txt 是否允许抓取"""
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
        """判断 URL 是否与基础 URL 同域"""
        return urlparse(url).netloc == urlparse(base_url).netloc

    # ------------------------------------------------------------------
    # HTTP 请求（带重试）
    # ------------------------------------------------------------------

    def fetch(self, url: str, referer: str | None = None) -> requests.Response | None:
        """发起 HTTP 请求，带指数退避重试"""
        if not self._check_robots(url):
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
    # SVG 提取
    # ------------------------------------------------------------------

    def extract_inline_svgs(self, soup: BeautifulSoup) -> list[str]:
        """提取页面中所有内联 <svg> 标签的内容"""
        svgs = []
        for svg_tag in soup.find_all("svg"):
            svg_content = str(svg_tag)
            if svg_content.strip():
                svgs.append(svg_content)
        return svgs

    def extract_external_svg_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        """提取所有外部 SVG 文件的 URL"""
        urls = []

        for img in soup.find_all("img", src=True):
            src = img["src"]
            if src.lower().endswith(".svg") or ".svg#" in src.lower():
                urls.append(urljoin(base_url, src))

        for obj in soup.find_all("object", data=True):
            data = obj["data"]
            if data.lower().endswith(".svg") or ".svg#" in data.lower():
                urls.append(urljoin(base_url, data))

        for emb in soup.find_all("embed", src=True):
            src = emb["src"]
            if src.lower().endswith(".svg") or ".svg#" in src.lower():
                urls.append(urljoin(base_url, src))

        for use_tag in soup.find_all("use"):
            href = use_tag.get("href") or use_tag.get("xlink:href") or ""
            if href and ".svg" in href.lower():
                clean_url = urldefrag(urljoin(base_url, href))[0]
                urls.append(clean_url)

        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def extract_css_svg_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        """从 <style> 标签和 style 属性中提取 url(*.svg) 引用"""
        urls = []

        for style_tag in soup.find_all("style"):
            if style_tag.string:
                urls.extend(CSS_SVG_PATTERN.findall(style_tag.string))

        for tag in soup.find_all(style=True):
            matches = CSS_SVG_PATTERN.findall(tag["style"])
            urls.extend(matches)

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
        """根据 URL 生成安全的文件名"""
        parsed = urlparse(url)
        path = parsed.path
        name = os.path.basename(path)
        name = name.split("?")[0]

        if not name or not name.endswith(".svg"):
            name = f"svg_{index:04d}.svg"

        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        return name

    def save_inline_svg(self, content: str, index: int):
        """保存内联 SVG"""
        filename = f"inline_svg_{index:04d}.svg"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self._log(f"  [保存] 内联 SVG -> {filepath.name}")
        self.stats["inline"] += 1

    def save_external_svg(self, url: str, index: int, referer: str):
        """下载并保存外部 SVG 文件"""
        if url in self._seen_urls:
            return
        self._seen_urls.add(url)

        if self.same_domain_only and not self._is_same_domain(url, referer):
            self._log(f"  [跳过] 跨域 SVG: {url}")
            self.stats["skipped"] += 1
            return

        response = self.fetch(url, referer=referer)
        if response is None:
            return

        content_type = response.headers.get("Content-Type", "")
        if "svg" not in content_type and "xml" not in content_type and "text" not in content_type:
            if not response.text.strip().startswith("<"):
                self._log(f"  [跳过] 非 SVG 内容: {url} (Content-Type: {content_type})")
                self.stats["skipped"] += 1
                return

        filename = self._safe_filename(url, index)
        filepath = self.output_dir / filename

        counter = 1
        while filepath.exists():
            stem = filepath.stem
            filepath = self.output_dir / f"{stem}_{counter}.svg"
            counter += 1

        with open(filepath, "wb") as f:
            f.write(response.content)
        self._log(f"  [保存] {url} -> {filepath.name}")
        self.stats["external"] += 1

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def scrape(self, url: str):
        """爬取指定 URL 的所有 SVG 图像"""
        self._log("=" * 60)
        self._log(f"目标 URL: {url}")
        self._log(f"输出目录: {self.output_dir.resolve()}")
        self._log(f"延迟范围: {self.delay_range[0]}-{self.delay_range[1]}s")
        self._log(f"最大重试: {self.max_retries}")
        self._log(f"robots.txt 检查: {'开启' if self.respect_robots else '关闭'}")
        self._log(f"仅同域: {'是' if self.same_domain_only else '否'}")
        self._log("=" * 60)

        self._log("\n[1/4] 正在获取页面...")
        response = self.fetch(url)
        if response is None:
            self._log("无法获取页面，退出。")
            return

        if response.encoding is None or response.encoding == "ISO-8859-1":
            response.encoding = response.apparent_encoding

        html = response.text
        final_url = response.url
        soup = BeautifulSoup(html, "html.parser")

        self._log("\n[2/4] 提取内联 SVG...")
        inline_svgs = self.extract_inline_svgs(soup)
        self._log(f"  找到 {len(inline_svgs)} 个内联 SVG")
        for i, svg in enumerate(inline_svgs):
            self.save_inline_svg(svg, i)
            self._polite_delay()

        self._log("\n[3/4] 提取外部 SVG 文件...")
        external_urls = self.extract_external_svg_urls(soup, final_url)
        self._log(f"  找到 {len(external_urls)} 个外部 SVG 链接")

        css_urls = self.extract_css_svg_urls(soup, final_url)
        if css_urls:
            self._log(f"  在 CSS 中找到 {len(css_urls)} 个 SVG 引用")
            external_urls.extend(css_urls)

        for i, svg_url in enumerate(external_urls):
            self.save_external_svg(svg_url, i, referer=final_url)
            self._polite_delay()

        self._log("\n[4/4] 完成！")
        self._log("-" * 40)
        self._log(f"  内联 SVG 保存: {self.stats['inline']}")
        self._log(f"  外部 SVG 保存: {self.stats['external']}")
        self._log(f"  跳过:          {self.stats['skipped']}")
        self._log(f"  失败:          {self.stats['failed']}")
        self._log(f"  输出目录: {self.output_dir.resolve()}")
        self._log("=" * 60)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="从指定网站爬取所有 SVG 图像",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python svg_scraper.py https://example.com
  python svg_scraper.py https://example.com -o ./my_svgs
  python svg_scraper.py https://example.com --delay 2 5 --no-robots
        """,
    )
    parser.add_argument("url", help="目标网站 URL")
    parser.add_argument(
        "-o", "--output",
        default="./svgs_output",
        help="SVG 保存目录 (默认: ./svgs_output)",
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
        help="允许抓取跨域 SVG (默认仅同域)",
    )

    args = parser.parse_args()

    scraper = SVGScraper(
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
