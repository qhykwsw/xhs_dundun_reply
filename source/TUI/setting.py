"""
XHS DunDun Reply TUI 设置页面
"""
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label

from ..module import Settings

__all__ = ["Setting"]


class Setting(Screen):
    """设置界面"""

    BINDINGS = [
        Binding(key="Q", action="quit_app", description="退出程序"),
        Binding(key="B", action="back_to_index", description="返回首页"),
    ]

    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def compose(self) -> ComposeResult:
        """构建界面"""
        yield Header()

        yield ScrollableContainer(
            # ===== 基础配置 =====
            Label("═══ 基础配置 ═══", classes="section-title"),

            Label(Settings.get_description("user_data_dir"), classes="params"),
            Input(
                self.data.get("user_data_dir", "browser_data"),
                placeholder="browser_data",
                id="user_data_dir",
            ),

            # ===== 关键词配置 =====
            Label("═══ 关键词配置 ═══", classes="section-title"),

            Label(Settings.get_description("target_keywords"), classes="params"),
            Input(
                Settings.format_list_value(self.data.get("target_keywords", [])),
                placeholder="蹲, 教程, 屁股, 踢, dun",
                id="target_keywords",
            ),

            Label(Settings.get_description("exact_match_keywords"), classes="params"),
            Input(
                Settings.format_list_value(self.data.get("exact_match_keywords", [])),
                placeholder="我, 我我, 我我我, 求, 求求, 顿, 顿顿",
                id="exact_match_keywords",
            ),

            Label(Settings.get_description("emoji_keywords"), classes="params"),
            Input(
                Settings.format_list_value(self.data.get("emoji_keywords", [])),
                placeholder="蹲后续, 蹲",
                id="emoji_keywords",
            ),

            Label(Settings.get_description("reply_text"), classes="params"),
            Input(
                self.data.get("reply_text", "发了~"),
                placeholder="发了~",
                id="reply_text",
            ),

            # ===== 时间延迟配置 =====
            Label("═══ 时间延迟配置 ═══", classes="section-title"),

            Label(Settings.get_description("login_timeout"), classes="params"),
            Input(
                str(self.data.get("login_timeout", 60)),
                placeholder="60",
                type="integer",
                id="login_timeout",
            ),

            Label(Settings.get_description("element_timeout"), classes="params"),
            Input(
                str(self.data.get("element_timeout", 10)),
                placeholder="10",
                type="integer",
                id="element_timeout",
            ),

            Label(Settings.get_description("comments_load_delay"), classes="params"),
            Input(
                str(self.data.get("comments_load_delay", 1.0)),
                placeholder="1.0",
                type="number",
                id="comments_load_delay",
            ),

            # 导航延迟（min/max 同行）
            Label("导航延迟 (秒): 最小值 / 最大值", classes="params"),
            Horizontal(
                Input(
                    str(self.data.get("navigate_delay_min", 2.0)),
                    placeholder="2.0",
                    type="number",
                    id="navigate_delay_min",
                ),
                Input(
                    str(self.data.get("navigate_delay_max", 3.0)),
                    placeholder="3.0",
                    type="number",
                    id="navigate_delay_max",
                ),
                classes="dual-input",
            ),

            # 回复延迟（min/max 同行）
            Label("回复延迟 (秒): 最小值 / 最大值", classes="params"),
            Horizontal(
                Input(
                    str(self.data.get("reply_delay_min", 0.1)),
                    placeholder="0.1",
                    type="number",
                    id="reply_delay_min",
                ),
                Input(
                    str(self.data.get("reply_delay_max", 0.2)),
                    placeholder="0.2",
                    type="number",
                    id="reply_delay_max",
                ),
                classes="dual-input",
            ),

            # 滚动延迟（min/max 同行）
            Label("滚动延迟 (秒): 最小值 / 最大值", classes="params"),
            Horizontal(
                Input(
                    str(self.data.get("scroll_delay_min", 0.1)),
                    placeholder="0.1",
                    type="number",
                    id="scroll_delay_min",
                ),
                Input(
                    str(self.data.get("scroll_delay_max", 0.2)),
                    placeholder="0.2",
                    type="number",
                    id="scroll_delay_max",
                ),
                classes="dual-input",
            ),

            # 步骤延迟（min/max 同行）
            Label("步骤延迟 (秒): 最小值 / 最大值", classes="params"),
            Horizontal(
                Input(
                    str(self.data.get("step_delay_min", 0.1)),
                    placeholder="0.1",
                    type="number",
                    id="step_delay_min",
                ),
                Input(
                    str(self.data.get("step_delay_max", 0.2)),
                    placeholder="0.2",
                    type="number",
                    id="step_delay_max",
                ),
                classes="dual-input",
            ),

            # ===== 浏览器交互配置 =====
            Label("═══ 浏览器交互配置 ═══", classes="section-title"),

            Label(Settings.get_description("max_expand_clicks"), classes="params"),
            Input(
                str(self.data.get("max_expand_clicks", 10000)),
                placeholder="10000",
                type="integer",
                id="max_expand_clicks",
            ),

            Label(Settings.get_description("max_scroll_attempts"), classes="params"),
            Input(
                str(self.data.get("max_scroll_attempts", 5000)),
                placeholder="5000",
                type="integer",
                id="max_scroll_attempts",
            ),

            Label(Settings.get_description("max_no_new_comments"), classes="params"),
            Input(
                str(self.data.get("max_no_new_comments", 3)),
                placeholder="3",
                type="integer",
                id="max_no_new_comments",
            ),

            # ===== 断点续传配置 =====
            Label("═══ 断点续传配置 ═══", classes="section-title"),

            Label(Settings.get_description("start_from_l1_index"), classes="params"),
            Input(
                str(self.data.get("start_from_l1_index", "") or ""),
                placeholder="留空从头开始",
                id="start_from_l1_index",
            ),

            Label(Settings.get_description("start_from_comment_id"), classes="params"),
            Input(
                str(self.data.get("start_from_comment_id", "") or ""),
                placeholder="留空从头开始",
                id="start_from_comment_id",
            ),

            # ===== 风控配置 =====
            Label("═══ 风控配置 ═══", classes="section-title"),

            Label(Settings.get_description("max_consecutive_failures"), classes="params"),
            Input(
                str(self.data.get("max_consecutive_failures", 3)),
                placeholder="3",
                type="integer",
                id="max_consecutive_failures",
            ),

            Label(Settings.get_description("max_restart_attempts"), classes="params"),
            Input(
                str(self.data.get("max_restart_attempts", 3)),
                placeholder="3",
                type="integer",
                id="max_restart_attempts",
            ),

            # 重启延迟（min/max 同行）
            Label("重启延迟 (秒): 最小值 / 最大值", classes="params"),
            Horizontal(
                Input(
                    str(self.data.get("restart_delay_min", 300)),
                    placeholder="300",
                    type="integer",
                    id="restart_delay_min",
                ),
                Input(
                    str(self.data.get("restart_delay_max", 600)),
                    placeholder="600",
                    type="integer",
                    id="restart_delay_max",
                ),
                classes="dual-input",
            ),

            Horizontal(
                Checkbox(
                    "启用风控检测",
                    id="risk_control_detection",
                    value=self.data.get("risk_control_detection", True),
                ),
                classes="checkbox-row",
            ),

            # ===== 其他配置 =====
            Label("═══ 其他配置 ═══", classes="section-title"),

            Label(Settings.get_description("preview_text_length"), classes="params"),
            Input(
                str(self.data.get("preview_text_length", 50)),
                placeholder="50",
                type="integer",
                id="preview_text_length",
            ),

            # 底部按钮
            Label(""),  # 间隔
            Horizontal(
                Button("保存配置", id="save", variant="success"),
                Button("放弃更改", id="abandon", variant="error"),
                classes="settings-buttons",
            ),
            Horizontal(
                Button("退出程序", id="quit_btn", variant="error"),
                Button("返回首页", id="back_btn", variant="primary"),
                classes="settings-buttons",
            ),

            classes="settings-container",
        )

        yield Footer()

    def on_mount(self) -> None:
        """界面挂载时"""
        self.title = "程序设置"

    @on(Button.Pressed, "#save")
    def save_settings(self):
        """保存设置"""
        try:
            new_data = {
                # 基础配置
                "post_url": self.data.get("post_url", ""),
                "user_data_dir": self.query_one("#user_data_dir", Input).value,
                "headless": self.data.get("headless", False),

                # 关键词配置
                "target_keywords": Settings.parse_list_value(
                    self.query_one("#target_keywords", Input).value
                ),
                "exact_match_keywords": Settings.parse_list_value(
                    self.query_one("#exact_match_keywords", Input).value
                ),
                "emoji_keywords": Settings.parse_list_value(
                    self.query_one("#emoji_keywords", Input).value
                ),
                "reply_text": self.query_one("#reply_text", Input).value,

                # 时间延迟配置
                "login_timeout": int(self.query_one("#login_timeout", Input).value or 60),
                "login_success_delay": self.data.get("login_success_delay", 2.0),
                "element_timeout": int(self.query_one("#element_timeout", Input).value or 10),
                "short_timeout": self.data.get("short_timeout", 3),
                "user_check_timeout": self.data.get("user_check_timeout", 5),
                "navigate_delay_min": float(self.query_one("#navigate_delay_min", Input).value or 2.0),
                "navigate_delay_max": float(self.query_one("#navigate_delay_max", Input).value or 3.0),
                "comments_load_delay": float(self.query_one("#comments_load_delay", Input).value or 1.0),
                "reply_delay_min": float(self.query_one("#reply_delay_min", Input).value or 0.1),
                "reply_delay_max": float(self.query_one("#reply_delay_max", Input).value or 0.2),
                "scroll_delay_min": float(self.query_one("#scroll_delay_min", Input).value or 0.1),
                "scroll_delay_max": float(self.query_one("#scroll_delay_max", Input).value or 0.2),
                "step_delay_min": float(self.query_one("#step_delay_min", Input).value or 0.1),
                "step_delay_max": float(self.query_one("#step_delay_max", Input).value or 0.2),
                "submit_result_delay_min": self.data.get("submit_result_delay_min", 0.1),
                "submit_result_delay_max": self.data.get("submit_result_delay_max", 0.2),

                # 浏览器交互配置
                "max_expand_clicks": int(self.query_one("#max_expand_clicks", Input).value or 10000),
                "max_scroll_attempts": int(self.query_one("#max_scroll_attempts", Input).value or 5000),
                "max_no_new_comments": int(self.query_one("#max_no_new_comments", Input).value or 3),

                # 断点续传配置
                "start_from_l1_index": self._parse_optional_int(
                    self.query_one("#start_from_l1_index", Input).value
                ),
                "start_from_comment_id": self.query_one("#start_from_comment_id", Input).value or None,

                # 风控配置
                "max_consecutive_failures": int(self.query_one("#max_consecutive_failures", Input).value or 3),
                "max_restart_attempts": int(self.query_one("#max_restart_attempts", Input).value or 3),
                "restart_delay_min": int(self.query_one("#restart_delay_min", Input).value or 300),
                "restart_delay_max": int(self.query_one("#restart_delay_max", Input).value or 600),
                "risk_control_detection": self.query_one("#risk_control_detection", Checkbox).value,

                # 其他配置
                "preview_text_length": int(self.query_one("#preview_text_length", Input).value or 50),
            }

            self.dismiss(new_data)

        except ValueError as e:
            self.notify(f"配置值格式错误: {e}", severity="error")

    def _parse_optional_int(self, value: str):
        """解析可选的整数值"""
        if not value or value.strip() == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @on(Button.Pressed, "#abandon")
    def abandon_changes(self):
        """放弃更改"""
        self.dismiss(self.data)

    @on(Button.Pressed, "#quit_btn")
    async def quit_app(self):
        """退出程序"""
        await self.app.action_quit()

    @on(Button.Pressed, "#back_btn")
    async def back_to_index(self):
        """返回首页"""
        self.dismiss(self.data)

    async def action_quit_app(self) -> None:
        """快捷键退出"""
        await self.app.action_quit()

    async def action_back_to_index(self):
        """快捷键返回"""
        self.dismiss(self.data)
