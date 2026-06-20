"""广佛活动雷达 · 一键运行脚本

做 4 件事：
  1. 备份当前 data/ 到 data_backup_<ts>/（保护过往数据）
  2. 运行爬虫 python run.py
  3. 合并新旧数据 → public/data/events.json（过往活动不丢失）
  4. 复制海报 → public/posters/

桌面快捷方式调用这个脚本即可。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"


def step(msg: str):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def main():
    # 1. 备份
    step("1/4 备份当前数据（保护过往活动）")
    if DATA_DIR.exists() and (DATA_DIR / "events.json").exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = ROOT / f"data_backup_{ts}"
        shutil.copytree(DATA_DIR, backup, dirs_exist_ok=True)
        print(f"  ✅ 已备份到 {backup.name}")
        # 只保留最近 3 个备份
        backups = sorted(ROOT.glob("data_backup_*"))
        for old in backups[:-3]:
            shutil.rmtree(old, ignore_errors=True)
            print(f"  🧹 清理旧备份: {old.name}")
    else:
        print("  ℹ️  无现有数据，跳过备份")

    # 2. 运行爬虫
    step("2/4 运行爬虫")
    cmd = [sys.executable, "run.py", "--max-pages", "2", "--poster-limit", "150"]
    print(f"  $ {' '.join(cmd)}")
    ret = subprocess.call(cmd, cwd=str(ROOT))
    if ret != 0:
        print(f"  ⚠️  爬虫返回非零退出码 {ret}，继续同步已有数据")

    # 3. 合并 + 同步
    step("3/4 合并新旧数据并同步到 public/")
    ret = subprocess.call([sys.executable, "sync_data.py"], cwd=str(ROOT))
    if ret != 0:
        print(f"  ❌ 同步失败 ({ret})")
        sys.exit(1)

    # 4. 完成
    step("4/4 完成 ✅")
    print("  数据已更新到 public/data/events.json")
    print("  运行 python serve.py 启动本地服务器查看")
    print("  或部署到 Firebase: firebase deploy")


if __name__ == "__main__":
    main()
