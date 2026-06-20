"""广佛活动雷达 · 本地开发服务器

特性：
  - 端口冲突自动 +1（默认 8000 → 8001 → ...）
  - 静态文件服务 public/ 目录
  - 自动打开浏览器
  - 优雅关闭

用法：python serve.py [--port 8000] [--no-open]
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import socket
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
PUBLIC_DIR = ROOT / "public"


class Handler(http.server.SimpleHTTPRequestHandler):
    """静态文件 handler，root 指向 public/。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def end_headers(self):
        # 允许 fetch 本地 json
        self.send_header("Access-Control-Allow-Origin", "*")
        # 不缓存 json，方便开发
        if self.path.endswith(".json"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 简化日志
        sys.stderr.write(f"  {self.address_string()} - {fmt % args}\n")


def find_free_port(start: int, end: int = 65535) -> int:
    """从 start 开始找空闲端口，冲突就 +1。"""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"没有可用端口 ({start}-{end})")


def main():
    ap = argparse.ArgumentParser(description="广佛活动雷达 本地服务器")
    ap.add_argument("--port", type=int, default=8000, help="起始端口（冲突自动+1）")
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()

    if not PUBLIC_DIR.exists():
        print(f"❌ 目录不存在: {PUBLIC_DIR}")
        sys.exit(1)

    port = find_free_port(args.port)
    if port != args.port:
        print(f"⚠️  端口 {args.port} 被占用，改用 {port}")

    url = f"http://localhost:{port}/"
    print(f"""
╔══════════════════════════════════════════╗
║   🛰️  广佛活动雷达 · 本地服务器已启动   ║
╠══════════════════════════════════════════╣
║  地址: {url:<33s}║
║  目录: {str(PUBLIC_DIR):<33s}║
║  按 Ctrl+C 停止                          ║
╚══════════════════════════════════════════╝
""")

    if not args.no_open:
        webbrowser.open(url)

    try:
        with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
            httpd.allow_reuse_address = True
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except OSError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
