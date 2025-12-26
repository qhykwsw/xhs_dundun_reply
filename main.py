import asyncio
import random
import time
import json
import os
from datetime import datetime
from typing import List, Set, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from config import Config
import logging
import re
from logging.handlers import RotatingFileHandler
from emoji_extraction.emoji_extraction import EmojiExtraction
from tqdm import tqdm

# -------------------------------------------------------------------------
# 日志配置
# -------------------------------------------------------------------------
# 确保日志目录存在
os.makedirs("logs", exist_ok=True)

# 创建 logger
logger = logging.getLogger("xhs_reply_bot")
logger.setLevel(logging.DEBUG)  # 总开关设为 DEBUG，允许所有级别的日志通过

# 清除已有的 handlers (避免重复打印)
if logger.hasHandlers():
    logger.handlers.clear()

# 1. 控制台 Handler (只显示 INFO 及以上)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# 2. 文件 Handler (显示 DEBUG 及以上，按大小轮转)
log_file = f"logs/xhs_reply_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
file_handler.setFormatter(file_formatter)

# 添加 handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# -------------------------------------------------------------------------

class XHSCommentReply:
    """小红书评论回复自动化类"""

    def __init__(self, config: Config):
        self.config = config
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.processed_comments_count = 0
        self.replied_count = 0
        self.already_replied_ids: Set[str] = set()
        self.post_id = self.extract_post_id(config.post_url)
        self.record_file_path = f"reply_data/{self.post_id}.jsonl"
        self.processed_comment_ids: Set[str] = set()
        self.own_user_id: Optional[str] = None

        # 会话级日志去重集合：记录本次运行中已打印过日志的评论ID
        self.session_logged_ids: Set[str] = set()

        # 帖子信息
        self.post_title: Optional[str] = None
        self.post_author: Optional[str] = None

        # 风控和重启相关
        self.restart_count = 0
        self.risk_control_detected = False
        self.consecutive_reply_failures = 0
        self.max_consecutive_failures = self.config.max_consecutive_failures

        # 初始化emoji提取器
        self.emoji_extractor = EmojiExtraction()

        # 确保reply_data目录存在
        os.makedirs("reply_data", exist_ok=True)

        # 加载已处理的评论记录
        self.load_processed_comments()

    async def init_browser(self):
        """初始化浏览器（使用持久化上下文）"""
        self.playwright = await async_playwright().start()

        # 基础浏览器启动参数
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            # --- 禁用后台节流 ---
            '--disable-background-timer-throttling',       # 禁用后台计时器节流
            '--disable-backgrounding-occluded-windows',    # 禁用被遮挡窗口的后台挂起
            '--disable-renderer-backgrounding',            # 禁用渲染器后台运行
            '--disable-component-update'                   # 禁用组件更新，减少干扰
        ]

        # 核心逻辑：处理“无头”模式
        # 由于小红书风控极严，原生 Headless 模式会导致 Cookies 失效或扫码失败。
        # 因此我们使用 "伪无头模式"：开启有头浏览器，但将窗口移到屏幕外。
        if self.config.headless:
            logger.info("🛡️ 启用'伪无头模式'：浏览器将在屏幕外运行 (坐标 10000,10000)")
            logger.info("   这能最大程度规避风控，保持登录状态稳定。")
            actual_headless = False
            # 移出屏幕并设置固定大小
            browser_args.append('--window-position=10000,10000')
            browser_args.append('--window-size=1920,1080')
            # 伪无头模式下不能使用 start-maximized，否则可能导致窗口跳回屏幕
        else:
            logger.info("🖥️ 启用'前台模式'：浏览器将最大化显示")
            actual_headless = False
            browser_args.append('--start-maximized')

        # 确保数据目录存在
        if not os.path.exists(self.config.user_data_dir):
            os.makedirs(self.config.user_data_dir, exist_ok=True)

        logger.info(f"使用用户数据目录: {os.path.abspath(self.config.user_data_dir)}")

        # 使用 launch_persistent_context 启动
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.config.user_data_dir,
            headless=actual_headless,  # 使用计算出的 actual_headless
            args=browser_args,
            no_viewport=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport=None
        )

        # 添加反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en'],
            });

            window.chrome = {
                runtime: {},
            };

            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
        """)

        # 获取默认页面或新建页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        logger.info("浏览器初始化完成 (持久化模式)")

    def extract_post_id(self, url: str) -> str:
        """从URL中提取帖子ID"""
        pattern = r'/explore/([a-f0-9]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        else:
            # 备选方案：使用时间戳
            return f"unknown_{int(datetime.now().timestamp())}"

    def load_processed_comments(self):
        """加载已处理的评论记录"""
        if os.path.exists(self.record_file_path):
            try:
                with open(self.record_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            self.processed_comment_ids.add(record['comment_id'])
                            if record.get('replied', False):
                                self.already_replied_ids.add(record['comment_id'])
                logger.info(f"已加载 {len(self.processed_comment_ids)} 条已处理评论记录")
            except Exception as e:
                logger.error(f"❌ 加载已处理评论记录失败: {e}")

    def save_comment_record(self, comment_data: Dict[str, Any]):
        """保存评论处理记录"""
        try:
            record = {
                "timestamp": datetime.now().isoformat(),
                "post_title": self.post_title,
                "post_author": self.post_author,
                **comment_data
            }

            with open(self.record_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

            self.processed_comment_ids.add(comment_data['comment_id'])
            logger.info(f"已保存评论记录: {comment_data['comment_id']}")
        except Exception as e:
            logger.error(f"❌ 保存评论记录失败: {e}")

    async def get_own_user_id(self):
        """获取当前登录用户的ID"""
        if self.own_user_id:
            return self.own_user_id

        try:
            # 尝试从页面元素中获取当前用户ID
            user_element = await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=self.config.user_check_timeout * 1000
            )
            if user_element:
                # 查找包含用户信息的元素
                user_link = await self.page.locator("li.user a[href*='/user/profile/']").first.get_attribute("href")
                if user_link:
                    user_id_match = re.search(r'/user/profile/([a-f0-9]+)', user_link)
                    if user_id_match:
                        self.own_user_id = user_id_match.group(1)
                        logger.info(f"获取到当前用户ID: {self.own_user_id}")
                        return self.own_user_id
        except Exception as e:
            logger.warning(f"无法获取当前用户ID: {e}")

        return None

    async def check_risk_control(self) -> bool:
        """检测是否触发了风控"""
        try:
            # 检查是否出现风控相关的提示
            risk_control_selectors = [
                "text=操作过于频繁",
                "text=请稍后再试",
                "text=系统繁忙",
                "text=网络异常",
                "text=发送失败",
                "[class*='error']",
                "[class*='fail']"
            ]

            for selector in risk_control_selectors:
                try:
                    element = await self.page.locator(selector).first
                    if await element.is_visible(timeout=self.config.short_timeout * 1000):
                        logger.warning(f"检测到风控信号: {selector}")
                        return True
                except:
                    continue

            # 检查回复输入框是否被禁用
            try:
                reply_input = self.page.locator("#content-textarea")
                if await reply_input.is_visible(timeout=self.config.short_timeout * 1000):
                    is_disabled = await reply_input.is_disabled()
                    if is_disabled:
                        logger.warning("回复输入框被禁用，可能触发风控")
                        return True
            except:
                pass

            return False

        except Exception as e:
            logger.warning(f"检测风控时出错: {e}")
            return False

    async def extract_post_info(self):
        """提取帖子标题和作者信息"""
        try:
            # 提取帖子标题
            title_element = await self.page.wait_for_selector(
                "#detail-title",
                timeout=self.config.element_timeout * 1000
            )
            if title_element:
                self.post_title = await title_element.text_content()
                self.post_title = self.post_title.strip() if self.post_title else None
                logger.info(f"获取到帖子标题: {self.post_title}")

            # 提取帖子作者
            author_element = await self.page.wait_for_selector(
                ".author-container .author-wrapper .info a.name .username",
                timeout=self.config.element_timeout * 1000
            )
            if author_element:
                self.post_author = await author_element.text_content()
                self.post_author = self.post_author.strip() if self.post_author else None
                logger.info(f"获取到帖子作者: {self.post_author}")

        except Exception as e:
            logger.warning(f"提取帖子信息失败: {e}")
            # 设置默认值
            if not self.post_title:
                self.post_title = "未知标题"
            if not self.post_author:
                self.post_author = "未知作者"

    async def extract_comment_content_with_emoji(self, comment_element) -> str:
        """提取评论内容，包含文本和emoji表情转换"""
        try:
            text_element = comment_element.locator("div.content span.note-text")

            inner_html = await text_element.inner_html()
            content_parts = self.emoji_extractor.parse_html_content_with_emoji(inner_html)

            return ''.join(content_parts)

        except Exception as e:
            logger.error(f"❌ 提取评论内容失败: {e}")
            return ""

    async def extract_comment_info(self, comment_element) -> Optional[Dict[str, Any]]:
        """提取评论的详细信息"""
        try:
            # 获取评论ID
            comment_id = await comment_element.get_attribute('id')
            if not comment_id:
                return None

            # 清理comment_id，移除"comment-"前缀
            if comment_id.startswith('comment-'):
                comment_id = comment_id[8:]

            # 判断评论级别
            comment_classes = await comment_element.get_attribute('class') or ''
            comment_level = 'l2' if 'comment-item-sub' in comment_classes else 'l1'

            # 获取用户信息
            author_element = comment_element.locator("div.author-wrapper div.author a.name")
            user_name = await author_element.text_content()
            user_href = await author_element.get_attribute('href')

            user_id = None
            if user_href:
                user_id_match = re.search(r'data-user-id="([^"]+)"', await comment_element.inner_html())
                if user_id_match:
                    user_id = user_id_match.group(1)
                else:
                    # 备选方案：从href中提取
                    href_match = re.search(r'/user/profile/([a-f0-9]+)', user_href)
                    if href_match:
                        user_id = href_match.group(1)

            # 获取评论内容（包含文本和emoji表情）
            comment_content = await self.extract_comment_content_with_emoji(comment_element)

            return {
                'comment_id': comment_id,
                'comment_level': comment_level,
                'user_id': user_id,
                'user_name': user_name,
                'comment_content': comment_content,
                'replied': False,
                'need_reply': False
            }

        except Exception as e:
            logger.error(f"❌ 提取评论信息失败: {e}")
            return None

    async def login(self):
        """登录流程（持久化模式）"""
        logger.info("打开小红书...")
        await self.page.goto("https://www.xiaohongshu.com")

        # 1. 检查是否已经自动登录
        try:
            logger.info("正在检查登录状态...")
            # 使用较短的超时时间快速检查
            await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=self.config.user_check_timeout * 1000
            )
            logger.info("✅ 检测到有效登录状态（持久化会话），自动登录成功！")
            await asyncio.sleep(self.config.login_success_delay)
            await self.get_own_user_id()
            return  # 直接返回，跳过扫码流程
        except:
            logger.info("❌ 未检测到登录状态，需要扫码登录")

        # 2. 如果未登录，进入扫码流程
        logger.info(f"请在 {self.config.login_timeout} 秒内扫描二维码登录...")

        try:
            # 等待登录成功标志
            await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=self.config.login_timeout * 1000
            )
            logger.info("✅ 登录成功！")

            # 持久化上下文会自动保存数据，不需要手动保存Cookies
            logger.info("登录状态已自动保存至用户数据目录")

            await asyncio.sleep(self.config.login_success_delay)

            # 获取当前用户ID
            await self.get_own_user_id()
        except Exception as e:
            logger.error(f"❌ 登录超时或失败: {e}")
            raise

    async def navigate_to_post(self):
        """导航到目标文章"""
        logger.info(f"导航到目标作品: {self.config.post_url}")
        await self.page.goto(self.config.post_url)
        await asyncio.sleep(random.uniform(self.config.navigate_delay_min, self.config.navigate_delay_max))

        # 等待评论区加载
        logger.info("等待评论区加载...")
        await self.page.wait_for_selector(
            "div.comments-el",
            timeout=self.config.element_timeout * 1000
        )
        logger.info("评论区已加载")
        await asyncio.sleep(self.config.comments_load_delay)

    async def check_keywords(self, text: str, comment_element=None) -> Optional[str]:
        """检查文本中是否包含目标关键词"""
        # 1. 检查完全匹配的关键词（优先级最高）
        text_clean = text.strip()
        for exact_keyword in self.config.exact_match_keywords:
            if text_clean == exact_keyword:
                return f"完全匹配:{exact_keyword}"

        # 2. 检查emoji表情（现在emoji已经包含在text中，格式为emoji{name}）
        for emoji_meaning in self.config.emoji_keywords:
            emoji_pattern = f"emoji{{{emoji_meaning}}}"
            if emoji_pattern in text:
                return f"包含emoji:{emoji_meaning}"

        # 3. 检查包含匹配的关键词
        for keyword in self.config.target_keywords:
            if keyword in text:
                return f"包含:{keyword}"

        return None

    async def execute_reply(self, comment_element, comment_id: str) -> bool:
        """执行回复操作"""
        try:
            logger.info(f"执行回复操作 for {comment_id}...")

            # 滚动到评论位置
            await comment_element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

            # 点击回复按钮
            reply_button = comment_element.locator("div.reply.icon-container")
            await reply_button.click()
            logger.info("回复按钮已点击")

            await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

            # 输入回复内容
            reply_input = self.page.locator("#content-textarea")
            await reply_input.wait_for(timeout=self.config.element_timeout * 1000)
            await reply_input.fill(self.config.reply_text)
            logger.info(f"输入回复: {self.config.reply_text}")

            await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

            # 点击发送按钮
            send_button = self.page.locator("button.btn.submit")
            await send_button.click()
            logger.info(f"发送按钮已点击 for {comment_id}")

            # 等待回复结果
            await asyncio.sleep(random.uniform(self.config.submit_result_delay_min, self.config.submit_result_delay_max))

            # 检测是否触发风控
            if self.config.risk_control_detection:
                risk_detected = await self.check_risk_control()
                if risk_detected:
                    logger.error(f"❌ 检测到风控，回复失败 for {comment_id}")
                    self.risk_control_detected = True
                    self.consecutive_reply_failures += 1
                    return False

            # 检查回复是否成功（可以通过检查页面是否有新的回复或者其他成功标志）
            try:
                # 简单的成功检测：如果没有错误提示，认为成功
                await asyncio.sleep(self.config.comments_load_delay)
                logger.info(f"✅ 回复发送成功 for {comment_id}")
                self.consecutive_reply_failures = 0  # 重置连续失败计数
                return True
            except Exception:
                logger.error(f"❌ 回复可能失败 for {comment_id}")
                self.consecutive_reply_failures += 1
                return False

        except Exception as e:
            logger.error(f"❌ 回复操作失败 for {comment_id}: {e}")
            self.consecutive_reply_failures += 1

            # 检测是否可能触发风控
            if self.consecutive_reply_failures >= self.max_consecutive_failures:
                logger.warning(f"连续失败 {self.consecutive_reply_failures} 次，可能触发风控")
                self.risk_control_detected = True

            return False

    async def process_single_comment(self, comment_element, comment_level: str, processed_ids: Set[str]) -> bool:
        """通用的评论处理函数，用于处理L1和L2评论"""
        try:
            # 提取评论详细信息
            comment_info = await self.extract_comment_info(comment_element)
            if not comment_info:
                return False

            comment_id = comment_info['comment_id']
            text = comment_info['comment_content']
            preview_text = text[:self.config.preview_text_length].replace('\n', ' ') + "..." if len(text) > self.config.preview_text_length else text

            # 检查是否已处理过
            if comment_id in self.processed_comment_ids or comment_id in processed_ids:
                # 只有当这个ID从未被记录过日志时，才打印DEBUG日志
                if comment_id not in self.session_logged_ids:
                    logger.info(f"跳过已处理的 {comment_level} 评论: {comment_id} | {preview_text}")
                    self.session_logged_ids.add(comment_id)
                return False

            # 检查是否是本人的评论
            if comment_info['user_id'] == self.own_user_id:
                if comment_id not in self.session_logged_ids:
                    logger.info(f"跳过本人的 {comment_level} 评论: {comment_id} | {preview_text}")
                    self.session_logged_ids.add(comment_id)
                processed_ids.add(comment_id)
                return False

            await comment_element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

            self.processed_comments_count += 1
            logger.info(f"检查 {comment_level} 评论 {comment_id}: {preview_text}")
            logger.info(f"  用户: {comment_info['user_name']} (ID: {comment_info['user_id']})")

            # 标记为已记录日志（避免后续重复处理时再次打印跳过日志）
            self.session_logged_ids.add(comment_id)

            keyword_found = await self.check_keywords(text)
            comment_info['need_reply'] = bool(keyword_found)

            if keyword_found:
                logger.info(f"-> {comment_level} 找到关键词 '{keyword_found}'!")
                if await self.execute_reply(comment_element, comment_id):
                    comment_info['replied'] = True
                    self.already_replied_ids.add(comment_id)
                    self.replied_count += 1

                    # 保存成功回复的记录
                    self.save_comment_record(comment_info)

                    delay = random.uniform(self.config.reply_delay_min, self.config.reply_delay_max)
                    logger.info(f"等待 {delay:.2f} 秒...")
                    await asyncio.sleep(delay)
                    return True
                else:
                    # 回复失败，检查是否触发风控
                    if self.risk_control_detected:
                        logger.error(f"❌ 回复失败，检测到风控: {comment_id}")
                        raise Exception("回复失败，检测到风控")
                    else:
                        logger.error(f"❌ 回复失败，不保存记录: {comment_id}")
                        return False
            else:
                logger.info(f"-- {comment_level} 未找到任何目标关键词")
                # 保存不需要回复的记录
                self.save_comment_record(comment_info)

            processed_ids.add(comment_id)
            return False

        except Exception as e:
            logger.error(f"❌ 处理 {comment_level} 评论时出错: {e}")
            return False

    async def process_comments(self):
        """处理评论主流程，使用滚动式更新来发现所有顶级评论区"""
        logger.info(f"{'='*50}")
        logger.info(f"开始处理评论，查找关键词: {self.config.target_keywords}...")
        logger.info(f"完全匹配关键词: {self.config.exact_match_keywords}")
        logger.info(f"emoji关键词: {self.config.emoji_keywords}")

        # 起始位置相关变量
        start_processing = False
        if self.config.start_from_l1_index is None and self.config.start_from_comment_id is None:
            start_processing = True  # 如果没有设置起始位置，从头开始

        current_l1_index = 0  # 当前L1评论的索引（0-based）

        processed_parent_keys = set()
        scroll_attempts = 0
        max_scroll_attempts = self.config.max_scroll_attempts
        no_new_comments_count = 0  # 连续没有新评论的次数
        max_no_new_comments = self.config.max_no_new_comments
        # 记录已遍历过的顶级评论区索引，避免重复遍历
        last_processed_parent_index = 0

        while scroll_attempts < max_scroll_attempts and no_new_comments_count < max_no_new_comments:
            scroll_attempts += 1
            logger.info(f"{'='*50}")
            logger.info(f"滚动循环 #{scroll_attempts}")

            # 检查是否触发风控
            if self.risk_control_detected:
                logger.warning("检测到风控，停止处理评论")
                break

            # 获取当前可见的顶级评论区
            parent_comments = await self.page.locator("div.parent-comment").all()
            current_parent_count = len(parent_comments)
            logger.info(f"当前找到 {current_parent_count} 个可见的顶级评论区 (新增: {current_parent_count - last_processed_parent_index})")

            new_comments_found = False

            # 只处理新出现的顶级评论区（从上次处理的位置开始）
            if current_parent_count > last_processed_parent_index:
                new_parent_comments = parent_comments[last_processed_parent_index:]
                for parent_element in tqdm(new_parent_comments, desc="处理顶级评论区"):
                    try:
                        # 生成父评论的唯一标识
                        parent_bounds = await parent_element.bounding_box()
                        if not parent_bounds:
                            continue

                        # 使用位置和内容的组合作为唯一标识
                        l1_comment = parent_element.locator("div.comment-item:not(.comment-item-sub)").first
                        try:
                            comment_id = await l1_comment.get_attribute('id')
                            if comment_id:
                                parent_key = comment_id
                            else:
                                # 如果没有id，使用位置作为备选
                                parent_key = f"parent_{int(parent_bounds['y'])}_{int(parent_bounds['x'])}"
                        except:
                            parent_key = f"parent_{int(parent_bounds['y'])}_{int(parent_bounds['x'])}"

                        if parent_key in processed_parent_keys:
                            continue

                        new_comments_found = True
                        current_l1_index += 1
                        logger.info("-" * 30)
                        logger.info(f"发现L1评论 #{current_l1_index} (key: {parent_key})")

                        # 检查是否需要开始处理
                        if not start_processing:
                            # 检查索引条件
                            if (self.config.start_from_l1_index and
                                current_l1_index >= self.config.start_from_l1_index):
                                start_processing = True
                                logger.info(f"达到起始索引 #{self.config.start_from_l1_index}，开始处理")

                            # 检查comment_id条件
                            elif (self.config.start_from_comment_id and comment_id and
                                  comment_id == self.config.start_from_comment_id):
                                start_processing = True
                                logger.info(f"找到起始comment_id '{self.config.start_from_comment_id}'，开始处理")

                            if not start_processing:
                                logger.info(f"跳过L1评论 #{current_l1_index} (未达到起始条件)")
                                # 即使跳过，也要滚动到该元素，确保页面能够正确加载后续内容
                                await parent_element.scroll_into_view_if_needed()
                                await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))
                                processed_parent_keys.add(parent_key)
                                continue

                        logger.info(f"处理L1评论 #{current_l1_index} (key: {parent_key})")

                        # 滚动到当前评论区
                        await parent_element.scroll_into_view_if_needed()
                        await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

                        # 处理Level 1评论
                        processed_l1_ids = set()
                        await self.process_single_comment(l1_comment, "Level 1", processed_l1_ids)

                        # 处理Level 2评论（展开逻辑）
                        processed_l2_ids = set()
                        expand_clicks = 0
                        # 记录已遍历过的L2评论索引，避免重复遍历
                        last_processed_l2_index = 0

                        while expand_clicks < self.config.max_expand_clicks:
                            # 每轮循环之间添加等待时间（第一轮除外）
                            if expand_clicks > 0:
                                await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))

                            logger.info(f"L2 处理/展开循环 #{expand_clicks + 1}")

                            # 处理当前可见的L2评论
                            l2_comments = await parent_element.locator("div.comment-item-sub").all()
                            current_l2_count = len(l2_comments)

                            # 只处理新出现的L2评论（从上次处理的位置开始）
                            if current_l2_count > last_processed_l2_index:
                                logger.debug(f"发现 {current_l2_count - last_processed_l2_index} 条新L2评论 (总数: {current_l2_count})")
                                for i in range(last_processed_l2_index, current_l2_count):
                                    sub_comment = l2_comments[i]
                                    await self.process_single_comment(sub_comment, "Level 2", processed_l2_ids)
                                last_processed_l2_index = current_l2_count
                            else:
                                logger.debug(f"没有新的L2评论需要处理 (当前总数: {current_l2_count})")

                            # 查找展开按钮
                            try:
                                expand_button = parent_element.locator(
                                    "div.reply-container div.show-more:has-text('展开')"
                                ).first

                                if await expand_button.is_visible(timeout=self.config.short_timeout * 1000):
                                    logger.info("发现'展开'按钮，尝试点击...")
                                    await expand_button.click()
                                    expand_clicks += 1
                                    logger.info(f"'展开'已点击 ({expand_clicks}/{self.config.max_expand_clicks})")
                                    await asyncio.sleep(random.uniform(self.config.step_delay_min, self.config.step_delay_max))
                                else:
                                    logger.info("未找到'展开'按钮，结束L2展开")
                                    break

                            except Exception:
                                logger.info("展开按钮不可用，结束L2展开")
                                break

                        if expand_clicks >= self.config.max_expand_clicks:
                            logger.info(f"达到最大'展开'点击次数 ({self.config.max_expand_clicks})")

                        processed_parent_keys.add(parent_key)

                    except Exception as e:
                        logger.error(f"❌ 处理顶级评论区时发生错误: {e}")
                        continue

            # for 循环结束后，更新已处理的顶级评论区索引
            last_processed_parent_index = current_parent_count

            # 更新无新评论计数器
            if new_comments_found:
                no_new_comments_count = 0
                logger.info(f"本轮发现了新评论，重置计数器")
            else:
                no_new_comments_count += 1
                logger.info(f"本轮没有发现新评论 ({no_new_comments_count}/{max_no_new_comments})")

            # 滚动页面以加载更多评论
            if scroll_attempts < max_scroll_attempts and no_new_comments_count < max_no_new_comments:
                logger.info("滚动页面以加载更多评论...")
                await self.page.keyboard.press("End")  # 滚动到页面底部
                await asyncio.sleep(random.uniform(self.config.scroll_delay_min, self.config.scroll_delay_max))

                # 也可以尝试点击"查看更多评论"按钮
                try:
                    more_comments_button = self.page.locator("div.show-more:has-text('查看更多评论')").first
                    if await more_comments_button.is_visible(timeout=self.config.short_timeout * 1000):
                        logger.info("发现'查看更多评论'按钮，尝试点击...")
                        await more_comments_button.click()
                        await asyncio.sleep(random.uniform(self.config.scroll_delay_min, self.config.scroll_delay_max))
                except Exception:
                    pass  # 忽略按钮不存在的情况

        if scroll_attempts >= max_scroll_attempts:
            logger.info(f"达到最大滚动次数 ({max_scroll_attempts})")
        if no_new_comments_count >= max_no_new_comments:
            logger.info(f"连续 {max_no_new_comments} 轮没有发现新评论，停止处理")

        logger.info(f"总共处理了 {len(processed_parent_keys)} 个顶级评论区")

    async def run(self):
        """主运行流程"""
        try:
            start_time = datetime.now()
            await self.init_browser()
            await self.login()
            await self.navigate_to_post()

            # 提取帖子信息
            await self.extract_post_info()

            open_page_time = datetime.now()

            def _format_duration(value) -> str:
                total_seconds = int(value.total_seconds()) if hasattr(value, "total_seconds") else int(value)
                if total_seconds < 0:
                    total_seconds = 0
                hours, rem = divmod(total_seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                return f"{hours}时{minutes}分{seconds}秒"

            logger.info(f"页面准备耗时: {_format_duration(open_page_time - start_time)}")

            # 处理评论
            await self.process_comments()

            # 检查是否因风控而停止
            if self.risk_control_detected:
                logger.warning("因风控检测而停止，需要重启")
                raise Exception("检测到风控，需要重启脚本")

            # 最终统计
            logger.info("--- 任务完成 ---")
            logger.info(f"共检查了 {self.processed_comments_count} 条评论")
            logger.info(f"成功发送了 {self.replied_count} 条回复")
            logger.info(f"总共已处理的评论记录数: {len(self.processed_comment_ids)}")
            logger.info(f"记录文件路径: {self.record_file_path}")
            logger.info(f"处理评论耗时: {_format_duration(datetime.now() - open_page_time)}")

        except Exception:
            # 重新抛出风控异常
            raise
        except Exception as e:
            logger.error(f"❌ 脚本执行过程中发生严重错误: {e}")
            raise
        finally:
            # cleanup会在main函数的finally块中调用
            pass

    async def cleanup(self):
        """清理资源"""
        logger.info("关闭浏览器...")
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            # 持久化模式下没有 browser 对象需要关闭，关闭 context 即可
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"清理资源时出现警告: {e}")
        logger.info("脚本结束")

# 主函数
async def main():
    config = Config()
    restart_count = 0

    while restart_count <= config.max_restart_attempts:
        bot = XHSCommentReply(config)
        bot.restart_count = restart_count  # 传递重启次数

        try:
            logger.info(f"{'='*60}")
            if restart_count == 0:
                logger.info("开始执行小红书评论回复脚本")
            else:
                logger.info(f"第 {restart_count} 次重启脚本")
            logger.info(f"{'='*60}")

            await bot.run()

            # 如果正常完成，退出循环
            logger.info("脚本正常完成，退出")
            break

        except Exception as e:
            logger.warning(f"检测到风控: {e}")
            restart_count += 1

            if restart_count <= config.max_restart_attempts:
                # 计算重启延迟时间
                delay = random.uniform(config.restart_delay_min, config.restart_delay_max)
                logger.info(f"将在 {delay:.0f} 秒后进行第 {restart_count} 次重启...")
                logger.info(f"剩余重启次数: {config.max_restart_attempts - restart_count}")

                # 清理当前资源
                await bot.cleanup()

                # 等待延迟时间
                await asyncio.sleep(delay)
            else:
                logger.error(f"已达到最大重启次数 ({config.max_restart_attempts})，脚本停止")
                await bot.cleanup()
                break

        except KeyboardInterrupt:
            logger.info("用户中断程序")
            await bot.cleanup()
            break

        except Exception as e:
            logger.error(f"❌ 程序执行出错: {e}")
            restart_count += 1

            if restart_count <= config.max_restart_attempts:
                delay = random.uniform(config.restart_delay_min, config.restart_delay_max)
                logger.info(f"将在 {delay:.0f} 秒后进行第 {restart_count} 次重启...")

                # 清理当前资源
                await bot.cleanup()

                # 等待延迟时间
                await asyncio.sleep(delay)
            else:
                logger.error(f"已达到最大重启次数 ({config.max_restart_attempts})，脚本停止")
                await bot.cleanup()
                break
        finally:
            # 确保资源被清理（如果还没有清理的话）
            try:
                await bot.cleanup()
            except:
                pass

def run_main():
    """运行主函数并正确处理Windows下的asyncio"""
    if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
        # Windows系统使用ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"❌ 程序执行出错: {e}")

if __name__ == "__main__":
    run_main()
