"""
XHS DunDun Reply TUI 主应用
"""
from textual.app import App

from ..module import (
    ROOT,
    Settings,
)
from .index import Index
from .setting import Setting

__all__ = ["XHSDunDunReply"]


class XHSDunDunReply(App):
    """小红书蹲蹲自动回复 TUI 应用"""

    CSS_PATH = ROOT / "static" / "xhs-dundun-reply.tcss"
    SETTINGS = Settings(ROOT)

    def __init__(self):
        super().__init__()
        self.parameter: dict = {}
        self._initialization()

    def _initialization(self) -> None:
        """初始化配置"""
        self.parameter = self.SETTINGS.run()

    async def on_mount(self) -> None:
        """应用挂载时调用"""
        self.theme = "nord"

        # 安装主页面
        self.install_screen(
            Index(self.parameter),
            name="index",
        )

        # 安装设置页面
        self.install_screen(
            Setting(self.parameter),
            name="setting",
        )

        # 推送主页面
        await self.push_screen("index")

    async def action_settings(self):
        """打开设置页面"""
        async def save_settings(data: dict) -> None:
            self.SETTINGS.update(data)
            await self.refresh_screen()

        await self.push_screen("setting", save_settings)

    async def refresh_screen(self):
        """刷新屏幕（配置更新后）"""
        await self.action_back()
        self._initialization()

        # 重新安装页面
        self.uninstall_screen("index")
        self.uninstall_screen("setting")

        self.install_screen(
            Index(self.parameter),
            name="index",
        )
        self.install_screen(
            Setting(self.parameter),
            name="setting",
        )

        await self.push_screen("index")

    async def action_quit_app(self):
        """退出应用"""
        await self.action_quit()
