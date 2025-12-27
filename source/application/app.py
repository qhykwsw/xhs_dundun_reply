"""
小红书评论自动回复核心逻辑
"""
import asyncio
import random
import json
import os
import re
import logging
from datetime import datetime
from typing import Set, Optional, Dict, Any, Callable
from logging.handlers import RotatingFileHandler
from playwright.async_api import async_playwright, Page, BrowserContext

from ..module import ROOT

__all__ = ["XHSCommentReply"]


class XHSCommentReply:
    """小红书评论回复自动化类"""

    def __init__(
        self,
        config: dict,
        log_callback: Optional[Callable[[str, str], None]] = None,
        emoji_extractor=None,
    ):
        """
        初始化评论回复器

        Args:
            config: 配置字典
            log_callback: 日志回调函数，用于将日志输出到TUI界面
            emoji_extractor: Emoji提取器实例
        """
        self.config = config
        self.log_callback = log_callback
        self.emoji_extractor = emoji_extractor

        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.processed_comments_count = 0
        self.replied_count = 0
        self.already_replied_ids: Set[str] = set()
        self.post_id = self._extract_post_id(config.get("post_url", ""))
        self.record_file_path = ROOT / "reply_data" / f"{self.post_id}.jsonl"
        self.processed_comment_ids: Set[str] = set()
        self.own_user_id: Optional[str] = None

        # 会话级日志去重集合
        self.session_logged_ids: Set[str] = set()

        # 帖子信息
        self.post_title: Optional[str] = None
        self.post_author: Optional[str] = None

        # 风控和重启相关
        self.restart_count = 0
        self.risk_control_detected = False
        self.consecutive_reply_failures = 0
        self.max_consecutive_failures = config.get("max_consecutive_failures", 3)

        # 停止标志
        self._stop_flag = False

        # 日志器
        self.logger: Optional[logging.Logger] = None
        self.file_handler: Optional[RotatingFileHandler] = None

        # 确保目录存在
        os.makedirs(ROOT / "reply_data", exist_ok=True)
        os.makedirs(ROOT / "logs", exist_ok=True)

        # 加载已处理的评论记录
        self._load_processed_comments()

    def _init_logger(self):
        """初始化日志器（每次开始回复时调用）"""
        self.logger = logging.getLogger(f"xhs_reply_bot_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.logger.setLevel(logging.DEBUG)

        # 清除已有的 handlers
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 文件 Handler
        log_file = ROOT / "logs" / f"xhs_reply_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        self.file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        self.file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.file_handler.setFormatter(file_formatter)
        self.logger.addHandler(self.file_handler)

    def _log(self, message: str, level: str = "INFO"):
        """统一日志输出"""
        # 输出到文件
        if self.logger:
            log_func = getattr(self.logger, level.lower(), self.logger.info)
            log_func(message)

        # 输出到TUI界面
        if self.log_callback:
            self.log_callback(message, level)

    def stop(self):
        """停止回复任务"""
        self._stop_flag = True
        self._log("收到停止信号，正在停止...")

    def _extract_post_id(self, url: str) -> str:
        """从URL中提取帖子ID"""
        pattern = r'/explore/([a-f0-9]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return f"unknown_{int(datetime.now().timestamp())}"

    def _load_processed_comments(self):
        """加载已处理的评论记录"""
        if self.record_file_path.exists():
            try:
                with open(self.record_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            self.processed_comment_ids.add(record['comment_id'])
                            if record.get('replied', False):
                                self.already_replied_ids.add(record['comment_id'])
            except Exception as e:
                pass  # 静默处理加载失败

    def _save_comment_record(self, comment_data: Dict[str, Any]):
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
        except Exception as e:
            self._log(f"❌ 保存评论记录失败: {e}", "ERROR")

    async def init_browser(self):
        """初始化浏览器（使用持久化上下文）"""
        self.playwright = await async_playwright().start()

        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-component-update'
        ]

        headless = self.config.get("headless", False)
        if headless:
            self._log("🛡️ 启用'伪无头模式'：浏览器将在屏幕外运行")
            browser_args.append('--window-position=10000,10000')
            browser_args.append('--window-size=1920,1080')
        else:
            self._log("🖥️ 启用'前台模式'：浏览器将最大化显示")
            browser_args.append('--start-maximized')

        user_data_dir = ROOT / self.config.get("user_data_dir", "browser_data")
        os.makedirs(user_data_dir, exist_ok=True)

        self._log(f"使用用户数据目录: {user_data_dir}")

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
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

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        self._log("浏览器初始化完成 (持久化模式)")

    async def _get_own_user_id(self):
        """获取当前登录用户的ID"""
        if self.own_user_id:
            return self.own_user_id

        try:
            user_element = await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=self.config.get("user_check_timeout", 5) * 1000
            )
            if user_element:
                user_link = await self.page.locator("li.user a[href*='/user/profile/']").first.get_attribute("href")
                if user_link:
                    user_id_match = re.search(r'/user/profile/([a-f0-9]+)', user_link)
                    if user_id_match:
                        self.own_user_id = user_id_match.group(1)
                        self._log(f"获取到当前用户ID: {self.own_user_id}")
                        return self.own_user_id
        except Exception as e:
            self._log(f"无法获取当前用户ID: {e}", "WARNING")
        return None

    async def _check_risk_control(self) -> bool:
        """检测是否触发了风控"""
        try:
            risk_control_selectors = [
                "text=操作过于频繁",
                "text=请稍后再试",
                "text=系统繁忙",
                "text=网络异常",
                "text=发送失败",
            ]
            short_timeout = self.config.get("short_timeout", 3)
            for selector in risk_control_selectors:
                try:
                    element = await self.page.locator(selector).first
                    if await element.is_visible(timeout=short_timeout * 1000):
                        self._log(f"检测到风控信号: {selector}", "WARNING")
                        return True
                except:
                    continue

            try:
                reply_input = self.page.locator("#content-textarea")
                if await reply_input.is_visible(timeout=short_timeout * 1000):
                    is_disabled = await reply_input.is_disabled()
                    if is_disabled:
                        self._log("回复输入框被禁用，可能触发风控", "WARNING")
                        return True
            except:
                pass

            return False
        except Exception as e:
            self._log(f"检测风控时出错: {e}", "WARNING")
            return False

    async def _extract_post_info(self):
        """提取帖子标题和作者信息"""
        try:
            title_element = await self.page.wait_for_selector(
                "#detail-title",
                timeout=self.config.get("element_timeout", 10) * 1000
            )
            if title_element:
                self.post_title = await title_element.text_content()
                self.post_title = self.post_title.strip() if self.post_title else None
                self._log(f"获取到帖子标题: {self.post_title}")

            author_element = await self.page.wait_for_selector(
                ".author-container .author-wrapper .info a.name .username",
                timeout=self.config.get("element_timeout", 10) * 1000
            )
            if author_element:
                self.post_author = await author_element.text_content()
                self.post_author = self.post_author.strip() if self.post_author else None
                self._log(f"获取到帖子作者: {self.post_author}")

        except Exception as e:
            self._log(f"提取帖子信息失败: {e}", "WARNING")
            if not self.post_title:
                self.post_title = "未知标题"
            if not self.post_author:
                self.post_author = "未知作者"

    async def _extract_comment_content_with_emoji(self, comment_element) -> str:
        """提取评论内容，包含文本和emoji表情转换"""
        try:
            text_element = comment_element.locator("div.content span.note-text")
            inner_html = await text_element.inner_html()

            if self.emoji_extractor:
                content_parts = self.emoji_extractor.parse_html_content_with_emoji(inner_html)
                return ''.join(content_parts)
            else:
                # 简单提取文本
                text_content = await text_element.text_content()
                return text_content or ""
        except Exception as e:
            self._log(f"❌ 提取评论内容失败: {e}", "ERROR")
            return ""

    async def _extract_comment_info(self, comment_element) -> Optional[Dict[str, Any]]:
        """提取评论的详细信息"""
        try:
            comment_id = await comment_element.get_attribute('id')
            if not comment_id:
                return None

            if comment_id.startswith('comment-'):
                comment_id = comment_id[8:]

            comment_classes = await comment_element.get_attribute('class') or ''
            comment_level = 'l2' if 'comment-item-sub' in comment_classes else 'l1'

            author_element = comment_element.locator("div.author-wrapper div.author a.name")
            user_name = await author_element.text_content()
            user_href = await author_element.get_attribute('href')

            user_id = None
            if user_href:
                user_id_match = re.search(r'data-user-id="([^"]+)"', await comment_element.inner_html())
                if user_id_match:
                    user_id = user_id_match.group(1)
                else:
                    href_match = re.search(r'/user/profile/([a-f0-9]+)', user_href)
                    if href_match:
                        user_id = href_match.group(1)

            comment_content = await self._extract_comment_content_with_emoji(comment_element)

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
            self._log(f"❌ 提取评论信息失败: {e}", "ERROR")
            return None

    async def login(self):
        """登录流程（持久化模式）"""
        self._log("打开小红书...")
        await self.page.goto("https://www.xiaohongshu.com")

        try:
            self._log("正在检查登录状态...")
            await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=self.config.get("user_check_timeout", 5) * 1000
            )
            self._log("✅ 检测到有效登录状态，自动登录成功！")
            await asyncio.sleep(self.config.get("login_success_delay", 2.0))
            await self._get_own_user_id()
            return
        except:
            self._log("❌ 未检测到登录状态，需要扫码登录")

        login_timeout = self.config.get("login_timeout", 60)
        self._log(f"请在 {login_timeout} 秒内扫描二维码登录...")

        try:
            await self.page.wait_for_selector(
                "li.user.side-bar-component span.channel",
                timeout=login_timeout * 1000
            )
            self._log("✅ 登录成功！")
            self._log("登录状态已自动保存至用户数据目录")
            await asyncio.sleep(self.config.get("login_success_delay", 2.0))
            await self._get_own_user_id()
        except Exception as e:
            self._log(f"❌ 登录超时或失败: {e}", "ERROR")
            raise

    async def navigate_to_post(self):
        """导航到目标文章"""
        post_url = self.config.get("post_url", "")
        self._log(f"导航到目标作品: {post_url}")
        await self.page.goto(post_url)

        delay_min = self.config.get("navigate_delay_min", 2.0)
        delay_max = self.config.get("navigate_delay_max", 3.0)
        await asyncio.sleep(random.uniform(delay_min, delay_max))

        self._log("等待评论区加载...")
        await self.page.wait_for_selector(
            "div.comments-el",
            timeout=self.config.get("element_timeout", 10) * 1000
        )
        self._log("评论区已加载")
        await asyncio.sleep(self.config.get("comments_load_delay", 1.0))

    async def _check_keywords(self, text: str) -> Optional[str]:
        """检查文本中是否包含目标关键词"""
        text_clean = text.strip()

        # 1. 精确匹配
        exact_keywords = self.config.get("exact_match_keywords", [])
        for exact_keyword in exact_keywords:
            if text_clean == exact_keyword:
                return f"完全匹配:{exact_keyword}"

        # 2. Emoji匹配
        emoji_keywords = self.config.get("emoji_keywords", [])
        for emoji_meaning in emoji_keywords:
            emoji_pattern = f"emoji{{{emoji_meaning}}}"
            if emoji_pattern in text:
                return f"包含emoji:{emoji_meaning}"

        # 3. 包含匹配
        target_keywords = self.config.get("target_keywords", [])
        for keyword in target_keywords:
            if keyword in text:
                return f"包含:{keyword}"

        return None

    async def _execute_reply(self, comment_element, comment_id: str) -> bool:
        """执行回复操作"""
        try:
            self._log(f"执行回复操作 for {comment_id}...")

            await comment_element.scroll_into_view_if_needed()
            step_delay_min = self.config.get("step_delay_min", 0.1)
            step_delay_max = self.config.get("step_delay_max", 0.2)
            await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

            reply_button = comment_element.locator("div.reply.icon-container")
            await reply_button.click()
            self._log("回复按钮已点击")

            await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

            reply_input = self.page.locator("#content-textarea")
            await reply_input.wait_for(timeout=self.config.get("element_timeout", 10) * 1000)

            reply_text = self.config.get("reply_text", "发了~")
            await reply_input.fill(reply_text)
            self._log(f"输入回复: {reply_text}")

            await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

            send_button = self.page.locator("button.btn.submit")
            await send_button.click()
            self._log(f"发送按钮已点击 for {comment_id}")

            submit_delay_min = self.config.get("submit_result_delay_min", 0.1)
            submit_delay_max = self.config.get("submit_result_delay_max", 0.2)
            await asyncio.sleep(random.uniform(submit_delay_min, submit_delay_max))

            if self.config.get("risk_control_detection", True):
                risk_detected = await self._check_risk_control()
                if risk_detected:
                    self._log(f"❌ 检测到风控，回复失败 for {comment_id}", "ERROR")
                    self.risk_control_detected = True
                    self.consecutive_reply_failures += 1
                    return False

            await asyncio.sleep(self.config.get("comments_load_delay", 1.0))
            self._log(f"✅ 回复发送成功 for {comment_id}")
            self.consecutive_reply_failures = 0
            return True

        except Exception as e:
            self._log(f"❌ 回复操作失败 for {comment_id}: {e}", "ERROR")
            self.consecutive_reply_failures += 1
            if self.consecutive_reply_failures >= self.max_consecutive_failures:
                self._log(f"连续失败 {self.consecutive_reply_failures} 次，可能触发风控", "WARNING")
                self.risk_control_detected = True
            return False

    async def _process_single_comment(self, comment_element, comment_level: str, processed_ids: Set[str]) -> bool:
        """处理单条评论"""
        if self._stop_flag:
            return False

        try:
            comment_info = await self._extract_comment_info(comment_element)
            if not comment_info:
                return False

            comment_id = comment_info['comment_id']
            text = comment_info['comment_content']
            preview_length = self.config.get("preview_text_length", 50)
            preview_text = text[:preview_length].replace('\n', ' ') + "..." if len(text) > preview_length else text

            if comment_id in self.processed_comment_ids or comment_id in processed_ids:
                if comment_id not in self.session_logged_ids:
                    self._log(f"跳过已处理的 {comment_level} 评论: {comment_id} | {preview_text}")
                    self.session_logged_ids.add(comment_id)
                return False

            if comment_info['user_id'] == self.own_user_id:
                if comment_id not in self.session_logged_ids:
                    self._log(f"跳过本人的 {comment_level} 评论: {comment_id} | {preview_text}")
                    self.session_logged_ids.add(comment_id)
                processed_ids.add(comment_id)
                return False

            await comment_element.scroll_into_view_if_needed()
            step_delay_min = self.config.get("step_delay_min", 0.1)
            step_delay_max = self.config.get("step_delay_max", 0.2)
            await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

            self.processed_comments_count += 1
            self._log(f"检查 {comment_level} 评论 {comment_id}: {preview_text}")
            self._log(f"  用户: {comment_info['user_name']} (ID: {comment_info['user_id']})")

            self.session_logged_ids.add(comment_id)

            keyword_found = await self._check_keywords(text)
            comment_info['need_reply'] = bool(keyword_found)

            if keyword_found:
                self._log(f"-> {comment_level} 找到关键词 '{keyword_found}'!")
                if await self._execute_reply(comment_element, comment_id):
                    comment_info['replied'] = True
                    self.already_replied_ids.add(comment_id)
                    self.replied_count += 1
                    self._save_comment_record(comment_info)

                    reply_delay_min = self.config.get("reply_delay_min", 0.1)
                    reply_delay_max = self.config.get("reply_delay_max", 0.2)
                    delay = random.uniform(reply_delay_min, reply_delay_max)
                    self._log(f"等待 {delay:.2f} 秒...")
                    await asyncio.sleep(delay)
                    return True
                else:
                    if self.risk_control_detected:
                        self._log(f"❌ 回复失败，检测到风控: {comment_id}", "ERROR")
                        raise Exception("回复失败，检测到风控")
                    else:
                        self._log(f"❌ 回复失败，不保存记录: {comment_id}", "ERROR")
                        return False
            else:
                self._log(f"-- {comment_level} 未找到任何目标关键词")
                self._save_comment_record(comment_info)

            processed_ids.add(comment_id)
            return False

        except Exception as e:
            self._log(f"❌ 处理 {comment_level} 评论时出错: {e}", "ERROR")
            return False

    async def process_comments(self):
        """处理评论主流程"""
        target_keywords = self.config.get("target_keywords", [])
        exact_keywords = self.config.get("exact_match_keywords", [])
        emoji_keywords = self.config.get("emoji_keywords", [])

        self._log("=" * 50)
        self._log(f"开始处理评论，查找关键词: {target_keywords}...")
        self._log(f"完全匹配关键词: {exact_keywords}")
        self._log(f"emoji关键词: {emoji_keywords}")

        start_processing = True
        start_from_l1_index = self.config.get("start_from_l1_index")
        start_from_comment_id = self.config.get("start_from_comment_id")

        if start_from_l1_index or start_from_comment_id:
            start_processing = False

        current_l1_index = 0
        processed_parent_keys = set()
        scroll_attempts = 0
        max_scroll_attempts = self.config.get("max_scroll_attempts", 5000)
        no_new_comments_count = 0
        max_no_new_comments = self.config.get("max_no_new_comments", 3)
        last_processed_parent_index = 0

        while scroll_attempts < max_scroll_attempts and no_new_comments_count < max_no_new_comments:
            if self._stop_flag:
                self._log("收到停止信号，停止处理评论")
                break

            scroll_attempts += 1
            self._log("=" * 50)
            self._log(f"滚动循环 #{scroll_attempts}")

            if self.risk_control_detected:
                self._log("检测到风控，停止处理评论", "WARNING")
                break

            parent_comments = await self.page.locator("div.parent-comment").all()
            current_parent_count = len(parent_comments)
            self._log(f"当前找到 {current_parent_count} 个可见的顶级评论区 (新增: {current_parent_count - last_processed_parent_index})")

            new_comments_found = False

            if current_parent_count > last_processed_parent_index:
                new_parent_comments = parent_comments[last_processed_parent_index:]
                for parent_element in new_parent_comments:
                    if self._stop_flag:
                        break

                    try:
                        parent_bounds = await parent_element.bounding_box()
                        if not parent_bounds:
                            continue

                        l1_comment = parent_element.locator("div.comment-item:not(.comment-item-sub)").first
                        try:
                            comment_id = await l1_comment.get_attribute('id')
                            if comment_id:
                                parent_key = comment_id
                            else:
                                parent_key = f"parent_{int(parent_bounds['y'])}_{int(parent_bounds['x'])}"
                        except:
                            parent_key = f"parent_{int(parent_bounds['y'])}_{int(parent_bounds['x'])}"

                        if parent_key in processed_parent_keys:
                            continue

                        new_comments_found = True
                        current_l1_index += 1
                        self._log("-" * 30)
                        self._log(f"发现L1评论 #{current_l1_index} (key: {parent_key})")

                        if not start_processing:
                            if start_from_l1_index and current_l1_index >= start_from_l1_index:
                                start_processing = True
                                self._log(f"达到起始索引 #{start_from_l1_index}，开始处理")
                            elif start_from_comment_id and comment_id and comment_id == start_from_comment_id:
                                start_processing = True
                                self._log(f"找到起始comment_id '{start_from_comment_id}'，开始处理")

                            if not start_processing:
                                self._log(f"跳过L1评论 #{current_l1_index} (未达到起始条件)")
                                await parent_element.scroll_into_view_if_needed()
                                step_delay_min = self.config.get("step_delay_min", 0.1)
                                step_delay_max = self.config.get("step_delay_max", 0.2)
                                await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))
                                processed_parent_keys.add(parent_key)
                                continue

                        self._log(f"处理L1评论 #{current_l1_index} (key: {parent_key})")

                        await parent_element.scroll_into_view_if_needed()
                        step_delay_min = self.config.get("step_delay_min", 0.1)
                        step_delay_max = self.config.get("step_delay_max", 0.2)
                        await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

                        processed_l1_ids = set()
                        await self._process_single_comment(l1_comment, "Level 1", processed_l1_ids)

                        # 处理L2评论
                        processed_l2_ids = set()
                        expand_clicks = 0
                        max_expand_clicks = self.config.get("max_expand_clicks", 10000)
                        last_processed_l2_index = 0

                        while expand_clicks < max_expand_clicks:
                            if self._stop_flag:
                                break

                            if expand_clicks > 0:
                                await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))

                            l2_comments = await parent_element.locator("div.comment-item-sub").all()
                            current_l2_count = len(l2_comments)

                            if current_l2_count > last_processed_l2_index:
                                for i in range(last_processed_l2_index, current_l2_count):
                                    if self._stop_flag:
                                        break
                                    sub_comment = l2_comments[i]
                                    await self._process_single_comment(sub_comment, "Level 2", processed_l2_ids)
                                last_processed_l2_index = current_l2_count

                            try:
                                expand_button = parent_element.locator(
                                    "div.reply-container div.show-more:has-text('展开')"
                                ).first
                                short_timeout = self.config.get("short_timeout", 3)
                                if await expand_button.is_visible(timeout=short_timeout * 1000):
                                    self._log("发现'展开'按钮，尝试点击...")
                                    await expand_button.click()
                                    expand_clicks += 1
                                    self._log(f"'展开'已点击 ({expand_clicks}/{max_expand_clicks})")
                                    await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))
                                else:
                                    break
                            except Exception:
                                break

                        processed_parent_keys.add(parent_key)

                    except Exception as e:
                        self._log(f"❌ 处理顶级评论区时发生错误: {e}", "ERROR")
                        continue

            last_processed_parent_index = current_parent_count

            if new_comments_found:
                no_new_comments_count = 0
                self._log("本轮发现了新评论，重置计数器")
            else:
                no_new_comments_count += 1
                self._log(f"本轮没有发现新评论 ({no_new_comments_count}/{max_no_new_comments})")

            if scroll_attempts < max_scroll_attempts and no_new_comments_count < max_no_new_comments:
                if not self._stop_flag:
                    self._log("滚动页面以加载更多评论...")
                    await self.page.keyboard.press("End")
                    scroll_delay_min = self.config.get("scroll_delay_min", 0.1)
                    scroll_delay_max = self.config.get("scroll_delay_max", 0.2)
                    await asyncio.sleep(random.uniform(scroll_delay_min, scroll_delay_max))

                    try:
                        short_timeout = self.config.get("short_timeout", 3)
                        more_comments_button = self.page.locator("div.show-more:has-text('查看更多评论')").first
                        if await more_comments_button.is_visible(timeout=short_timeout * 1000):
                            self._log("发现'查看更多评论'按钮，尝试点击...")
                            await more_comments_button.click()
                            await asyncio.sleep(random.uniform(scroll_delay_min, scroll_delay_max))
                    except Exception:
                        pass

        if scroll_attempts >= max_scroll_attempts:
            self._log(f"达到最大滚动次数 ({max_scroll_attempts})")
        if no_new_comments_count >= max_no_new_comments:
            self._log(f"连续 {max_no_new_comments} 轮没有发现新评论，停止处理")

        self._log(f"总共处理了 {len(processed_parent_keys)} 个顶级评论区")

    async def run(self):
        """主运行流程"""
        try:
            # 初始化日志器
            self._init_logger()

            start_time = datetime.now()
            self._log("=" * 60)
            self._log("开始执行小红书评论回复脚本")
            self._log("=" * 60)

            await self.init_browser()
            await self.login()
            await self.navigate_to_post()
            await self._extract_post_info()

            open_page_time = datetime.now()

            def _format_duration(value) -> str:
                total_seconds = int(value.total_seconds()) if hasattr(value, "total_seconds") else int(value)
                if total_seconds < 0:
                    total_seconds = 0
                hours, rem = divmod(total_seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                return f"{hours}时{minutes}分{seconds}秒"

            self._log(f"页面准备耗时: {_format_duration(open_page_time - start_time)}")

            await self.process_comments()

            if self.risk_control_detected:
                self._log("因风控检测而停止", "WARNING")
                raise Exception("检测到风控，需要重启脚本")

            self._log("--- 任务完成 ---")
            self._log(f"共检查了 {self.processed_comments_count} 条评论")
            self._log(f"成功发送了 {self.replied_count} 条回复")
            self._log(f"总共已处理的评论记录数: {len(self.processed_comment_ids)}")
            self._log(f"记录文件路径: {self.record_file_path}")
            self._log(f"处理评论耗时: {_format_duration(datetime.now() - open_page_time)}")

        except Exception as e:
            self._log(f"❌ 脚本执行过程中发生错误: {e}", "ERROR")
            raise

    async def cleanup(self):
        """清理资源"""
        self._log("关闭浏览器...")
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self._log(f"清理资源时出现警告: {e}", "WARNING")

        # 关闭日志handler
        if self.file_handler:
            self.file_handler.close()
            if self.logger:
                self.logger.removeHandler(self.file_handler)

        self._log("脚本结束")
