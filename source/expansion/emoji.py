"""
Emoji 提取模块
用于解析小红书评论中的 emoji 表情
"""
import re
import json
from pathlib import Path
from typing import List, Dict

__all__ = ["EmojiExtraction"]


class EmojiExtraction:
    """Emoji 提取器类"""

    def __init__(self):
        # 从emoji.json文件中加载emoji数据
        self.emoji_data = self._load_emoji_data()

    def _load_emoji_data(self) -> Dict[str, str]:
        """从emoji.json文件中加载emoji数据"""
        try:
            # 获取当前文件所在目录
            current_dir = Path(__file__).parent
            emoji_json_path = current_dir / 'emoji.json'

            with open(emoji_json_path, 'r', encoding='utf-8') as f:
                emoji_data = json.load(f)

            return emoji_data
        except Exception as e:
            print(f"加载emoji.json文件失败: {e}")
            # 如果加载失败，返回空字典
            return {}

    def get_emoji_name_from_src(self, src: str) -> str:
        """根据emoji图片src获取emoji名称"""
        try:
            # 直接检查完整的URL是否在emoji_data中
            if src in self.emoji_data:
                return self.emoji_data[src]

            # 如果完整URL不匹配，尝试部分匹配（向后兼容）
            for emoji_url, emoji_meaning in self.emoji_data.items():
                if emoji_url in src or src in emoji_url:
                    return emoji_meaning

            # 如果不在已知的emoji中，返回unknown
            return "unknown"

        except Exception as e:
            print(f"解析emoji名称失败: {e}")
            return "unknown"

    def parse_html_content_with_emoji(self, html_content: str) -> List[str]:
        """解析HTML内容，提取文本和emoji"""
        content_parts = []

        # 使用正则表达式匹配文本和img标签
        # 匹配模式：文本、span标签中的文本、img标签
        pattern = r'(<span[^>]*>([^<]*)</span>|<img[^>]*src="([^"]*)"[^>]*>|([^<]+))'

        matches = re.findall(pattern, html_content, re.DOTALL)

        for match in matches:
            full_match, span_text, img_src, plain_text = match

            if span_text:
                # span标签中的文本
                content_parts.append(span_text.strip())
            elif img_src:
                # 图片（emoji）
                emoji_name = self.get_emoji_name_from_src(img_src)
                content_parts.append(f"emoji{{{emoji_name}}}")
            elif plain_text and plain_text.strip():
                # 纯文本
                content_parts.append(plain_text.strip())

        return content_parts
