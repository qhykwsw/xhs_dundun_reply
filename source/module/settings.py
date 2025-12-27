"""
配置管理模块
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

__all__ = ["Settings"]

# 默认配置
DEFAULT_CONFIG = {
    # 基础配置
    "post_url": "",
    "user_data_dir": "browser_data",
    "headless": False,

    # 关键词配置
    "target_keywords": ["蹲", "教程", "屁股", "踢", "dun"],
    "exact_match_keywords": ["我", "我我", "我我我", "求", "求求", "顿", "顿顿"],
    "emoji_keywords": ["蹲后续", "蹲"],
    "reply_text": "发了~",

    # 时间延迟配置
    "login_timeout": 60,
    "login_success_delay": 2.0,
    "element_timeout": 10,
    "short_timeout": 3,
    "user_check_timeout": 5,
    "navigate_delay_min": 2.0,
    "navigate_delay_max": 3.0,
    "comments_load_delay": 1.0,
    "reply_delay_min": 0.1,
    "reply_delay_max": 0.2,
    "scroll_delay_min": 0.1,
    "scroll_delay_max": 0.2,
    "step_delay_min": 0.1,
    "step_delay_max": 0.2,
    "submit_result_delay_min": 0.1,
    "submit_result_delay_max": 0.2,

    # 浏览器交互配置
    "max_expand_clicks": 10000,
    "max_scroll_attempts": 5000,
    "max_no_new_comments": 3,

    # 断点续传配置
    "start_from_l1_index": None,
    "start_from_comment_id": None,

    # 风控配置
    "max_consecutive_failures": 3,
    "max_restart_attempts": 3,
    "restart_delay_min": 300,
    "restart_delay_max": 600,
    "risk_control_detection": True,

    # 其他配置
    "preview_text_length": 50,
}

# 配置项描述
CONFIG_DESCRIPTIONS = {
    "post_url": "目标帖子URL (必须包含 xsec_token)",
    "user_data_dir": "浏览器用户数据目录",
    "headless": "是否无头模式运行",
    "target_keywords": "包含匹配关键词 (逗号分隔)",
    "exact_match_keywords": "精确匹配关键词 (逗号分隔)",
    "emoji_keywords": "Emoji关键词 (逗号分隔)",
    "reply_text": "自动回复内容",
    "login_timeout": "登录等待超时时间 (秒)",
    "login_success_delay": "登录成功后的缓冲时间 (秒)",
    "element_timeout": "页面元素等待超时时间 (秒)",
    "short_timeout": "短超时时间 (秒)",
    "user_check_timeout": "用户身份检查超时时间 (秒)",
    "navigate_delay_min": "导航延迟最小值 (秒)",
    "navigate_delay_max": "导航延迟最大值 (秒)",
    "comments_load_delay": "评论区加载等待时间 (秒)",
    "reply_delay_min": "回复操作延迟最小值 (秒)",
    "reply_delay_max": "回复操作延迟最大值 (秒)",
    "scroll_delay_min": "滚动延迟最小值 (秒)",
    "scroll_delay_max": "滚动延迟最大值 (秒)",
    "step_delay_min": "UI操作步骤延迟最小值 (秒)",
    "step_delay_max": "UI操作步骤延迟最大值 (秒)",
    "submit_result_delay_min": "提交回复后延迟最小值 (秒)",
    "submit_result_delay_max": "提交回复后延迟最大值 (秒)",
    "max_expand_clicks": "展开按钮最大点击次数",
    "max_scroll_attempts": "页面滚动最大尝试次数",
    "max_no_new_comments": "连续无新评论的最大轮数",
    "start_from_l1_index": "从第N个L1评论开始 (留空从头开始)",
    "start_from_comment_id": "从指定comment_id开始 (留空从头开始)",
    "max_consecutive_failures": "连续失败触发风控的次数",
    "max_restart_attempts": "最大重启尝试次数",
    "restart_delay_min": "重启前最小等待时间 (秒)",
    "restart_delay_max": "重启前最大等待时间 (秒)",
    "risk_control_detection": "是否启用风控检测",
    "preview_text_length": "日志中评论预览长度",
}


class Settings:
    """配置管理类"""

    def __init__(self, root: Path):
        self.root = root
        self.settings_file = root / "settings.json"
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """从文件加载配置"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

        # 合并默认配置
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = value

    def run(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._data.copy()

    def update(self, data: Dict[str, Any]) -> None:
        """更新并保存配置"""
        self._data.update(data)
        self._save()

    def _save(self) -> None:
        """保存配置到文件"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置单个配置项"""
        self._data[key] = value
        self._save()

    @staticmethod
    def get_description(key: str) -> str:
        """获取配置项描述"""
        return CONFIG_DESCRIPTIONS.get(key, key)

    @staticmethod
    def get_default(key: str) -> Any:
        """获取配置项默认值"""
        return DEFAULT_CONFIG.get(key)

    @staticmethod
    def parse_list_value(value: str) -> List[str]:
        """将逗号分隔的字符串解析为列表"""
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def format_list_value(value: List[str]) -> str:
        """将列表格式化为逗号分隔的字符串"""
        if not value:
            return ""
        return ", ".join(value)
