"""
XHS DunDun Reply TUI 首页
"""
import asyncio
from pyperclip import paste
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Link, RichLog, Checkbox

from ..application import XHSCommentReply
from ..module import (
    LICENCE,
    PROJECT,
    REPOSITORY,
    MASTER,
    PROMPT,
    GENERAL,
    WARNING,
    ERROR,
    SUCCESS,
    ROOT,
)

# 导入 emoji_extraction
from ..expansion import EmojiExtraction
EMOJI_EXTRACTOR = EmojiExtraction()

__all__ = ["Index"]


class Index(Screen):
    """首页界面"""

    BINDINGS = [
        Binding(key="Q", action="quit_app", description="退出程序"),
        Binding(key="S", action="open_settings_screen", description="程序设置"),
    ]

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.url_input = None
        self.log_output = None
        self.headless_checkbox = None
        self.bot = None
        self._current_worker = None  # 用于跟踪当前运行的 worker

    @property
    def is_task_running(self) -> bool:
        """检查是否有任务正在运行"""
        return self._current_worker is not None and self._current_worker.is_running

    def compose(self) -> ComposeResult:
        """构建界面"""
        yield Header()

        # Block 1: 顶部信息和输入区域
        yield ScrollableContainer(
            # 标题和项目信息
            Label(
                Text(PROJECT, style="bold magenta"),
                classes="title",
            ),
            Label(
                Text(f"开源协议: {LICENCE}", style=MASTER),
                classes="center-label",
            ),
            Link(
                Text(f"项目地址: {REPOSITORY}", style=MASTER),
                url=REPOSITORY,
                tooltip="点击访问",
                classes="center-label",
            ),
            Label(
                Text("请输入小红书作品链接", style=PROMPT),
                classes="prompt",
            ),
            # URL 输入框
            Input(
                placeholder="帖子的URL (必须包含 xsec_token 等参数以确保能正常访问)",
                id="url_input",
            ),
            # 控制按钮行
            Horizontal(
                Checkbox("无头模式", id="headless_checkbox", value=self.config.get("headless", False)),
                Button("开始回复", id="start_btn", variant="success"),
                Button("停止", id="stop_btn", variant="error"),
                Button("读取剪贴板", id="paste_btn", variant="primary"),
                Button("清空输入框", id="reset_btn", variant="default"),
                classes="control-row",
            ),
            classes="top-block",
        )

        # Block 2: 日志显示区域
        yield Vertical(
            RichLog(
                markup=True,
                wrap=True,
                auto_scroll=True,
                id="log_output",
            ),
            Horizontal(
                Button("退出程序", id="quit_btn", variant="error"),
                Button("程序设置", id="settings_btn", variant="primary"),
                classes="bottom-row",
            ),
            classes="bottom-block",
        )

        yield Footer()

    def on_mount(self) -> None:
        """界面挂载时"""
        self.title = PROJECT
        self.url_input = self.query_one("#url_input", Input)
        self.log_output = self.query_one("#log_output", RichLog)
        self.headless_checkbox = self.query_one("#headless_checkbox", Checkbox)

        # 如果配置中有URL，填充到输入框
        if self.config.get("post_url"):
            self.url_input.value = self.config.get("post_url", "")

        # 显示欢迎信息
        self.log_output.write(
            Text("=" * 50, style=GENERAL),
            scroll_end=True,
        )
        self.log_output.write(
            Text("欢迎使用小红书蹲蹲自动回复助手！", style=MASTER),
            scroll_end=True,
        )
        self.log_output.write(
            Text("请输入帖子链接，然后点击「开始回复」", style=PROMPT),
            scroll_end=True,
        )
        self.log_output.write(
            Text("=" * 50, style=GENERAL),
            scroll_end=True,
        )

    def _log_callback(self, message: str, level: str = "INFO"):
        """日志回调函数，用于将日志输出到界面"""
        style_map = {
            "INFO": GENERAL,
            "WARNING": WARNING,
            "ERROR": ERROR,
            "DEBUG": "dim",
        }
        style = style_map.get(level, GENERAL)

        # 特殊处理包含特定关键字的消息
        if "✅" in message or "成功" in message:
            style = SUCCESS
        elif "❌" in message or "失败" in message:
            style = ERROR
        elif "⚠" in message or "警告" in message:
            style = WARNING

        self.log_output.write(
            Text(message, style=style),
            scroll_end=True,
        )

    @on(Button.Pressed, "#start_btn")
    async def start_reply(self):
        """开始回复"""
        if self.is_task_running:
            self._log_callback("任务正在运行中，请先停止当前任务", "WARNING")
            return

        url = self.url_input.value.strip()
        if not url:
            self._log_callback("未输入任何小红书作品链接", "WARNING")
            return

        if "xiaohongshu.com" not in url:
            self._log_callback("请输入有效的小红书链接", "WARNING")
            return

        # 更新配置
        current_config = self.config.copy()
        current_config["post_url"] = url
        current_config["headless"] = self.headless_checkbox.value

        self._log_callback("=" * 50)
        self._log_callback("正在启动回复任务...", "INFO")

        # 启动任务并保存 worker 引用
        self._current_worker = self.run_reply_task(current_config)

    @work(exclusive=True)
    async def run_reply_task(self, config: dict):
        """在后台运行回复任务"""
        try:
            self.bot = XHSCommentReply(
                config=config,
                log_callback=self._log_callback,
                emoji_extractor=EMOJI_EXTRACTOR,
            )

            await self.bot.run()

        except asyncio.CancelledError:
            self._log_callback("任务已取消", "WARNING")
        except Exception as e:
            self._log_callback(f"任务执行出错: {e}", "ERROR")
        finally:
            if self.bot:
                try:
                    await self.bot.cleanup()
                except Exception:
                    pass
                self.bot = None
            self._current_worker = None
            self._log_callback("=" * 50)
            self._log_callback("任务已结束", "INFO")

    @on(Button.Pressed, "#stop_btn")
    async def stop_reply(self):
        """停止回复"""
        if not self.is_task_running:
            self._log_callback("当前没有运行中的任务", "WARNING")
            return

        if self.bot:
            self.bot.stop()
            self._log_callback("正在停止任务...", "WARNING")

    @on(Button.Pressed, "#paste_btn")
    def paste_button(self):
        """读取剪贴板"""
        try:
            clipboard_content = paste()
            if clipboard_content:
                self.url_input.value = clipboard_content
                self._log_callback("已读取剪贴板内容", "INFO")
            else:
                self._log_callback("剪贴板为空", "WARNING")
        except Exception as e:
            self._log_callback(f"读取剪贴板失败: {e}", "ERROR")

    @on(Button.Pressed, "#reset_btn")
    def reset_button(self):
        """清空输入框"""
        self.url_input.value = ""
        self._log_callback("已清空输入框", "INFO")

    @on(Button.Pressed, "#quit_btn")
    async def quit_app(self):
        """退出程序"""
        if self.is_task_running and self.bot:
            self.bot.stop()
            await asyncio.sleep(1)
        await self.app.action_quit()

    @on(Button.Pressed, "#settings_btn")
    async def open_settings(self):
        """打开设置"""
        if self.is_task_running:
            self._log_callback("请先停止当前任务再修改设置", "WARNING")
            return
        await self.app.run_action("settings")

    async def action_quit_app(self) -> None:
        """快捷键退出"""
        await self.quit_app()

    async def action_open_settings_screen(self):
        """快捷键打开设置"""
        await self.open_settings()
