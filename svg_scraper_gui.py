#!/usr/bin/env python3
"""
SVG 图像爬取工具 - GUI 界面
基于 tkinter，提供图形化操作界面。
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 确保能导入同目录下的 svg_scraper 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_scraper import SVGScraper


class SVGScraperGUI:
    """SVG 爬虫图形界面"""

    # 主题配色
    COLORS = {
        "bg": "#1e1e2e",
        "surface": "#2d2d44",
        "surface_light": "#3d3d5c",
        "primary": "#7c3aed",
        "primary_hover": "#6d28d9",
        "accent": "#06b6d4",
        "text": "#e2e8f0",
        "text_dim": "#94a3b8",
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "border": "#4a4a6a",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SVG 爬虫工具")
        self.root.geometry("800x680")
        self.root.minsize(700, 600)
        self.root.configure(bg=self.COLORS["bg"])

        self._is_running = False
        self._worker_thread: threading.Thread | None = None

        self._setup_styles()
        self._build_ui()

    # ------------------------------------------------------------------
    # 样式
    # ------------------------------------------------------------------

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # 通用样式
        style.configure(".", background=self.COLORS["bg"], foreground=self.COLORS["text"])

        # Frame
        style.configure("TFrame", background=self.COLORS["bg"])

        # Label
        style.configure("TLabel", background=self.COLORS["bg"], foreground=self.COLORS["text"], font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), foreground=self.COLORS["primary"])
        style.configure("Dim.TLabel", foreground=self.COLORS["text_dim"], font=("Microsoft YaHei UI", 9))

        # Entry
        style.configure("TEntry",
                        fieldbackground=self.COLORS["surface"],
                        foreground=self.COLORS["text"],
                        bordercolor=self.COLORS["border"],
                        borderwidth=1,
                        padding=6)

        # Button
        style.configure("TButton",
                        background=self.COLORS["surface_light"],
                        foreground=self.COLORS["text"],
                        bordercolor=self.COLORS["border"],
                        padding=(12, 8),
                        font=("Microsoft YaHei UI", 10))
        style.map("TButton",
                  background=[("active", self.COLORS["border"])])

        # Primary Button
        style.configure("Primary.TButton",
                        background=self.COLORS["primary"],
                        foreground="#ffffff",
                        padding=(20, 10),
                        font=("Microsoft YaHei UI", 11, "bold"))
        style.map("Primary.TButton",
                  background=[("active", self.COLORS["primary_hover"]),
                              ("disabled", self.COLORS["surface"])])

        # Success Button
        style.configure("Success.TButton",
                        background=self.COLORS["success"],
                        foreground="#ffffff",
                        padding=(12, 8),
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Success.TButton",
                  background=[("active", "#059669")])

        # Checkbutton
        style.configure("TCheckbutton",
                        background=self.COLORS["bg"],
                        foreground=self.COLORS["text"],
                        font=("Microsoft YaHei UI", 10))
        style.map("TCheckbutton",
                  background=[("active", self.COLORS["bg"])])

        # LabelFrame
        style.configure("TLabelframe",
                        background=self.COLORS["surface"],
                        foreground=self.COLORS["accent"],
                        bordercolor=self.COLORS["border"],
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabelframe.Label",
                        background=self.COLORS["surface"],
                        foreground=self.COLORS["accent"])

        # Spinbox
        style.configure("TSpinbox",
                        fieldbackground=self.COLORS["surface"],
                        foreground=self.COLORS["text"],
                        arrowcolor=self.COLORS["text"])

    # ------------------------------------------------------------------
    # 构建 UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(title_frame, text="SVG 爬虫工具", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(title_frame, text="从网站批量提取 SVG 图像", style="Dim.TLabel").pack(side=tk.LEFT, padx=(12, 0), pady=(6, 0))

        # ---- 配置区 ----
        config_frame = ttk.LabelFrame(main_frame, text=" 爬取配置 ", padding=15)
        config_frame.pack(fill=tk.X, pady=(0, 12))

        # URL 输入
        url_row = ttk.Frame(config_frame)
        url_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(url_row, text="目标 URL:", width=10).pack(side=tk.LEFT)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(url_row, textvariable=self.url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 输出目录
        dir_row = ttk.Frame(config_frame)
        dir_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(dir_row, text="保存目录:", width=10).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "svgs_output"))
        dir_entry = ttk.Entry(dir_row, textvariable=self.dir_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        browse_btn = ttk.Button(dir_row, text="浏览...", command=self._browse_dir)
        browse_btn.pack(side=tk.LEFT)

        # 参数行
        params_row = ttk.Frame(config_frame)
        params_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(params_row, text="延迟(秒):", width=10).pack(side=tk.LEFT)
        self.delay_min_var = tk.StringVar(value="1.0")
        ttk.Entry(params_row, textvariable=self.delay_min_var, width=6).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(params_row, text="~").pack(side=tk.LEFT)
        self.delay_max_var = tk.StringVar(value="3.0")
        ttk.Entry(params_row, textvariable=self.delay_max_var, width=6).pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(params_row, text="重试次数:").pack(side=tk.LEFT)
        self.retries_var = tk.StringVar(value="3")
        ttk.Entry(params_row, textvariable=self.retries_var, width=6).pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(params_row, text="超时(秒):").pack(side=tk.LEFT)
        self.timeout_var = tk.StringVar(value="30")
        ttk.Entry(params_row, textvariable=self.timeout_var, width=6).pack(side=tk.LEFT, padx=(4, 0))

        # 复选框行
        check_row = ttk.Frame(config_frame)
        check_row.pack(fill=tk.X)
        self.robots_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(check_row, text="遵守 robots.txt", variable=self.robots_var).pack(side=tk.LEFT, padx=(0, 20))
        self.cross_domain_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(check_row, text="允许跨域抓取", variable=self.cross_domain_var).pack(side=tk.LEFT)

        # ---- 按钮区 ----
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.start_btn = ttk.Button(btn_frame, text="开始爬取", style="Primary.TButton", command=self._start_scraping)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop_scraping, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.clear_btn = ttk.Button(btn_frame, text="清空日志", command=self._clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.open_dir_btn = ttk.Button(btn_frame, text="打开输出目录", style="Success.TButton", command=self._open_output_dir)
        self.open_dir_btn.pack(side=tk.RIGHT)

        # ---- 日志区 ----
        log_frame = ttk.LabelFrame(main_frame, text=" 运行日志 ", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg=self.COLORS["surface"],
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            selectbackground=self.COLORS["primary"],
            font=("Consolas", 9),
            relief=tk.FLAT,
            padx=10,
            pady=8,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

        # 配置日志颜色标签
        self.log_text.tag_configure("info", foreground=self.COLORS["text"])
        self.log_text.tag_configure("success", foreground=self.COLORS["success"])
        self.log_text.tag_configure("warning", foreground=self.COLORS["warning"])
        self.log_text.tag_configure("error", foreground=self.COLORS["error"])
        self.log_text.tag_configure("dim", foreground=self.COLORS["text_dim"])

        # ---- 状态栏 ----
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, style="Dim.TLabel").pack(side=tk.LEFT)

        self.count_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.count_var, style="Dim.TLabel").pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _browse_dir(self):
        selected = filedialog.askdirectory(initialdir=self.dir_var.get(), title="选择 SVG 保存目录")
        if selected:
            self.dir_var.set(selected)

    def _log(self, msg: str, tag: str = "info"):
        """线程安全的日志写入"""
        def _append():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _append)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_running(self, running: bool):
        self._is_running = running
        if running:
            self.start_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.NORMAL)
            self.status_var.set("正在爬取...")
        else:
            self.start_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            self.status_var.set("就绪")

    def _validate_inputs(self) -> bool:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入目标 URL")
            return False
        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("提示", "URL 必须以 http:// 或 https:// 开头")
            return False

        out_dir = self.dir_var.get().strip()
        if not out_dir:
            messagebox.showwarning("提示", "请选择保存目录")
            return False

        try:
            dmin = float(self.delay_min_var.get())
            dmax = float(self.delay_max_var.get())
            if dmin < 0 or dmax < dmin:
                raise ValueError("延迟范围无效")
            int(self.retries_var.get())
            int(self.timeout_var.get())
        except ValueError as e:
            messagebox.showwarning("参数错误", f"参数输入有误: {e}")
            return False

        return True

    def _start_scraping(self):
        if not self._validate_inputs():
            return

        url = self.url_var.get().strip()
        output_dir = self.dir_var.get().strip()
        delay_range = (float(self.delay_min_var.get()), float(self.delay_max_var.get()))
        max_retries = int(self.retries_var.get())
        timeout = int(self.timeout_var.get())
        respect_robots = self.robots_var.get()
        same_domain = not self.cross_domain_var.get()

        self._set_running(True)
        self._log("=" * 55, "dim")
        self._log(f"启动爬取任务: {url}", "info")
        self._log("=" * 55, "dim")

        def log_callback(msg: str):
            # 根据内容自动着色
            if "[保存]" in msg:
                self._log(msg, "success")
            elif "[跳过]" in msg or "[警告]" in msg:
                self._log(msg, "warning")
            elif "[错误]" in msg or "[失败]" in msg or "[限流]" in msg:
                self._log(msg, "error")
            elif msg.startswith("=") or msg.startswith("-"):
                self._log(msg, "dim")
            else:
                self._log(msg, "info")
            # 更新计数
            self.root.after(0, self._update_count, msg)

        self._worker_thread = threading.Thread(
            target=self._run_scraper,
            args=(url, output_dir, delay_range, max_retries, timeout, respect_robots, same_domain, log_callback),
            daemon=True,
        )
        self._worker_thread.start()

    def _run_scraper(self, url, output_dir, delay_range, max_retries, timeout, respect_robots, same_domain, log_callback):
        try:
            scraper = SVGScraper(
                output_dir=output_dir,
                delay_range=delay_range,
                max_retries=max_retries,
                timeout=timeout,
                respect_robots=respect_robots,
                same_domain_only=same_domain,
                log_callback=log_callback,
            )
            scraper.scrape(url)

            def on_done():
                self._set_running(False)
                self.status_var.set("完成")
                messagebox.showinfo("完成", f"爬取完成！\n\n输出目录: {output_dir}")
            self.root.after(0, on_done)

        except Exception as e:
            def on_error(err=str(e)):
                self._set_running(False)
                self._log(f"[致命错误] {err}", "error")
                self.status_var.set("出错")
                messagebox.showerror("错误", f"运行出错:\n{err}")
            self.root.after(0, on_error)

    def _stop_scraping(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self._log("正在停止... (当前请求完成后退出)", "warning")
            self.status_var.set("停止中...")
            # daemon 线程无法强制终止，标记状态让 UI 恢复
            self._set_running(False)

    def _update_count(self, msg: str):
        """从日志中提取计数信息"""
        if "内联 SVG 保存:" in msg:
            pass  # 最终统计由完成日志显示
        if "完成！" in msg:
            self.count_var.set("任务完成")

    def _open_output_dir(self):
        out_dir = self.dir_var.get().strip()
        if not out_dir or not os.path.isdir(out_dir):
            messagebox.showwarning("提示", "输出目录不存在，请先运行爬取任务")
            return
        import subprocess
        import platform
        sys_name = platform.system()
        if sys_name == "Windows":
            os.startfile(out_dir)
        elif sys_name == "Darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    app = SVGScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
