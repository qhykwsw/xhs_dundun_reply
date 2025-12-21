"""
测试emoji提取功能
"""
import re
import json
import os
from typing import List, Dict

class EmojiExtraction:
    def __init__(self):
        # 从emoji.json文件中加载emoji数据
        self.emoji_data = self._load_emoji_data()

    def _load_emoji_data(self) -> Dict[str, str]:
        """从emoji.json文件中加载emoji数据"""
        try:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_json_path = os.path.join(current_dir, 'emoji.json')

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

def test_emoji_extraction():
    """测试emoji提取功能"""
    tester = EmojiExtraction()

    # 测试用例1：包含已知emoji的HTML（使用emoji.json中的真实数据）
    test_html = '<span>嘻嘻</span><img class="note-content-emoji" crossorigin="anonymous" src="https://picasso-static.xiaohongshu.com/fe-platform/9366d16631e3e208689cbc95eefb7cfb0901001e.png"><img class="note-content-emoji" crossorigin="anonymous" src="https://picasso-static.xiaohongshu.com/fe-platform/219fe9d7e40b14dd7a6712203143bb1f9972bc5c.png">'

    result = tester.parse_html_content_with_emoji(test_html)
    final_content = ''.join(result)

    print("测试用例1:")
    print(f"输入HTML: {test_html}")
    print(f"解析部分: {result}")
    print(f"最终结果: {final_content}")
    print(f"期望结果: 嘻嘻emoji{{微笑}}emoji{{害羞}}")
    print(f"测试{'通过' if final_content == '嘻嘻emoji{微笑}emoji{害羞}' else '失败'}")
    print()

    # 测试用例2：只有文本
    test_html2 = '<span>只有文本内容</span>'
    result2 = tester.parse_html_content_with_emoji(test_html2)
    final_content2 = ''.join(result2)

    print("测试用例2:")
    print(f"输入HTML: {test_html2}")
    print(f"解析部分: {result2}")
    print(f"最终结果: {final_content2}")
    print(f"期望结果: 只有文本内容")
    print(f"测试{'通过' if final_content2 == '只有文本内容' else '失败'}")
    print()

    # 测试用例3：只有emoji（使用json中的数据）
    test_html3 = '<img class="note-content-emoji" crossorigin="anonymous" src="https://picasso-static.xiaohongshu.com/fe-platform/b862c8f94da375f55805a97c152efeeb5099c149.png">'
    result3 = tester.parse_html_content_with_emoji(test_html3)
    final_content3 = ''.join(result3)

    print("测试用例3:")
    print(f"输入HTML: {test_html3}")
    print(f"解析部分: {result3}")
    print(f"最终结果: {final_content3}")
    print(f"期望结果: emoji{{失望}}")
    print(f"测试{'通过' if final_content3 == 'emoji{失望}' else '失败'}")
    print()

    # 测试用例4：包含未知emoji的情况
    test_html4 = '<img class="note-content-emoji" crossorigin="anonymous" src="https://unknown-domain.com/unknown-emoji.png">'
    result4 = tester.parse_html_content_with_emoji(test_html4)
    final_content4 = ''.join(result4)

    print("测试用例4:")
    print(f"输入HTML: {test_html4}")
    print(f"解析部分: {result4}")
    print(f"最终结果: {final_content4}")
    print(f"期望结果: emoji{{unknown}}")
    print(f"测试{'通过' if final_content4 == 'emoji{unknown}' else '失败'}")

if __name__ == "__main__":
    test_emoji_extraction()
