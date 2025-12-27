"""
XHS DunDun Reply - 小红书蹲蹲自动回复助手

TUI 图形界面版本
"""
import asyncio
import sys
import traceback
from pathlib import Path

# 将项目根目录添加到 Python 路径
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    """主函数"""
    try:
        # 导入模块
        from source.TUI import XHSDunDunReply

        # Windows 系统设置事件循环策略
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # 创建并运行应用
        app = XHSDunDunReply()
        app.run()

    except Exception as e:
        # 捕获所有异常并显示
        print("\n" + "=" * 60)
        print("程序启动失败！错误信息：")
        print("=" * 60)
        print(f"\n错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}\n")
        print("详细堆栈跟踪：")
        print("-" * 60)
        traceback.print_exc()
        print("-" * 60)
        print("\n请按任意键退出...")
        input()
        sys.exit(1)


if __name__ == "__main__":
    main()
