"""
XHS DunDun Reply - 小红书蹲蹲自动回复助手

TUI 图形界面版本
"""
import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from source.TUI import XHSDunDunReply


def main():
    """主函数"""
    # Windows 系统设置事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    app = XHSDunDunReply()
    app.run()


if __name__ == "__main__":
    main()
