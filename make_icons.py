"""生成广佛活动雷达的桌面图标 (.ico) 和桌面快捷方式。

生成两个图标：
  - icon-crawler.ico  🛰️ 雷达风格（爬虫快捷方式）
  - icon-website.ico  🌐 地球风格（网站快捷方式）

并在桌面创建两个 .lnk 快捷方式。
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
ICON_DIR = ROOT / "public" / "assets" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_bg(size, c1, c2, c3=None):
    """135° 对角渐变背景。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            if c3 and t > 0.5:
                t2 = (t - 0.5) * 2
                px[x, y] = lerp(c2, c3, t2) + (255,)
            else:
                t2 = t * 2 if c3 else t
                px[x, y] = lerp(c1, c2, t2) + (255,)
    return img


def rounded_mask(size, radius):
    """圆角矩形 mask。"""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def get_font(size):
    """找一个支持中文/emoji 的字体。"""
    candidates = [
        "C:/Windows/Fonts/seguisym.ttf",   # Segoe UI Symbol (emoji)
        "C:/Windows/Fonts/msyh.ttc",        # Microsoft YaHei
        "C:/Windows/Fonts/simhei.ttf",      # SimHei
        "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_radar(img, size):
    """在 img 上画雷达图案。"""
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = int(size * 0.32)
    # 同心圆
    for i in range(3):
        rr = r - i * r // 3
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=(255, 255, 255, 200), width=max(2, size // 80))
    # 十字线
    d.line([cx - r, cy, cx + r, cy], fill=(255, 255, 255, 150), width=max(2, size // 100))
    d.line([cx, cy - r, cx, cy + r], fill=(255, 255, 255, 150), width=max(2, size // 100))
    # 扫描扇形
    for i in range(20):
        angle = math.radians(-90 + i * 4)
        x2 = cx + int(r * math.cos(angle))
        y2 = cy + int(r * math.sin(angle))
        alpha = int(180 * (1 - i / 20))
        d.line([cx, cy, x2, y2], fill=(255, 255, 255, alpha), width=max(2, size // 80))
    # 中心点
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255, 255))


def draw_globe(img, size):
    """在 img 上画地球图案。"""
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = int(size * 0.30)
    # 外圆
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              outline=(255, 255, 255, 230), width=max(3, size // 60))
    # 经线
    for i in range(1, 4):
        offset = int(r * i / 4)
        d.ellipse([cx - offset, cy - r, cx + offset, cy + r],
                  outline=(255, 255, 255, 120), width=max(1, size // 120))
    # 纬线
    for i in range(1, 4):
        y = cy - r + int(2 * r * i / 4)
        half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
        d.line([cx - half, y, cx + half, y], fill=(255, 255, 255, 120), width=max(1, size // 120))
    # 赤道加粗
    d.line([cx - r, cy, cx + r, cy], fill=(255, 255, 255, 200), width=max(2, size // 100))


def make_icon(draw_fn, filename, sizes=(16, 32, 48, 64, 128, 256)):
    """生成一个 .ico 文件。"""
    c1 = (99, 102, 241)    # indigo
    c2 = (139, 92, 246)    # purple
    c3 = (236, 72, 153)    # pink
    # 生成最大尺寸的图标，PIL 自动缩放到各尺寸
    s = 256
    bg = gradient_bg(s, c1, c2, c3)
    mask = rounded_mask(s, max(4, s // 6))
    rounded = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    rounded.paste(bg, (0, 0), mask)
    draw_fn(rounded, s)
    out = ICON_DIR / filename
    rounded.save(out, format="ICO", sizes=[(sz, sz) for sz in sizes])
    print(f"  OK {out.name} ({out.stat().st_size // 1024} KB)")
    return out


def create_shortcut(name, target, args, icon, description):
    """创建 Windows 桌面快捷方式。"""
    try:
        import winreg
    except ImportError:
        print(f"  ⚠️  非 Windows，跳过快捷方式 {name}")
        return
    # 获取桌面路径
    desktop = Path(os.environ.get("USERPROFILE", ".")) / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("HOMEPATH", ".")) / "Desktop"
    lnk = desktop / f"{name}.lnk"

    # 用 base64 编码路径避免引号问题
    import base64
    fields = {
        "lnk": str(lnk),
        "target": target,
        "args": args,
        "workdir": str(ROOT),
        "icon": icon,
        "desc": description,
    }
    # 构造 PowerShell 脚本，用单引号包裹字符串
    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell\n"
        f"$sc = $ws.CreateShortcut('{fields['lnk']}')\n"
        f"$sc.TargetPath = '{fields['target']}'\n"
        f"$sc.Arguments = '{fields['args']}'\n"
        f"$sc.WorkingDirectory = '{fields['workdir']}'\n"
        f"$sc.IconLocation = '{fields['icon']}, 0'\n"
        f"$sc.Description = '{fields['desc']}'\n"
        "$sc.WindowStyle = 7\n"
        "$sc.Save()\n"
        f"Write-Output 'Created: {fields['lnk']}'\n"
    )
    import subprocess
    ret = subprocess.call(["powershell", "-NoProfile", "-Command", ps_script],
                          cwd=str(ROOT))
    if ret == 0:
        print(f"  ✅ 桌面快捷方式: {lnk.name}")
    else:
        print(f"  ❌ 创建快捷方式失败 ({ret})")


def main():
    # 修复 Windows 控制台编码
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("[1/2] Generating icons...")
    crawler_icon = make_icon(draw_radar, "icon-crawler.ico")
    website_icon = make_icon(draw_globe, "icon-website.ico")
    make_icon(draw_radar, "favicon.ico", sizes=(16, 32, 48))

    print("\n[2/2] Creating desktop shortcuts...")
    python_exe = sys.executable

    # 爬虫快捷方式
    create_shortcut(
        name="广佛活动雷达-爬虫",
        target=str(ROOT / "run_crawler.bat"),
        args="",
        icon=str(crawler_icon),
        description="一键抓取广州佛山最新活动数据",
    )

    # 网站快捷方式（启动服务器并打开浏览器）
    create_shortcut(
        name="广佛活动雷达-网站",
        target=python_exe,
        args=str(ROOT / "serve.py"),
        icon=str(website_icon),
        description="启动本地服务器并打开广佛活动雷达",
    )

    print("\nDone! Desktop shortcuts created.")


if __name__ == "__main__":
    main()
