from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Config:
    """
    项目配置类

    用于集中管理所有可配置的参数，包括目标帖子、关键词、回复设置、浏览器行为以及风控策略等。
    """

    # -------------------------------------------------------------------------
    # 基础配置
    # -------------------------------------------------------------------------

    # 目标帖子的URL (必须包含 xsec_token 等参数以确保能正常访问)
    # 样例: "https://www.xiaohongshu.com/explore/68a46f1c000000001d34fg67?xsec_token=ABjbtfsALJXlymLrgZJPkvE464hl5irgp1L4STBTn-Wh4Q=&xsec_source=pc_user"
    # post_url: str = "https://www.xiaohongshu.com/explore/68a46f1c000000001d02ba67?xsec_token=ABjbtfsALJXlyjLrgHPkvE464hl5irgp1L1STBTn-Wh4Q=&xsec_source=pc_user"
    post_url: str = "https://www.xiaohongshu.com/explore/694b6a62000000000d038f58?xsec_token=ABrr-MnVf8LYApks6FZ1g1VIxCDVZyOXlkOSOAB_c2Gp8=&xsec_source=pc_user"

    # 浏览器用户数据目录 (用于持久化保存登录状态)
    # 建议使用绝对路径，或者相对于项目根目录的路径
    user_data_dir: str = "browser_data"

    # 是否无头模式运行 (False: 显示浏览器窗口; True: 后台运行)
    # 调试时建议设置为 False，正式运行时可设置为 True
    headless: bool = False

    # -------------------------------------------------------------------------
    # 关键词与回复策略
    # -------------------------------------------------------------------------

    # 包含匹配关键词列表：只要评论中包含这些词，就会触发回复
    target_keywords: List[str] = field(default_factory=lambda: ["蹲", "教程", "屁股", "踢", "dun"])

    # 精确匹配关键词列表：只有评论内容完全等于这些词时，才会触发回复 (优先级最高)
    exact_match_keywords: List[str] = field(default_factory=lambda: ["我", "我我", "我我我", "求", "求求", "顿", "顿顿"])

    # Emoji关键词列表：用于匹配特定的表情含义 (例如 "蹲" 对应的表情)
    emoji_keywords: List[str] = field(default_factory=lambda: ["蹲后续", "蹲"])

    # 回复内容文本
    reply_text: str = "发了~"

    # -------------------------------------------------------------------------
    # 时间延迟与超时配置 (单位: 秒)
    # -------------------------------------------------------------------------

    # 登录等待超时时间 (给用户扫码登录的时间)
    login_timeout: int = 60

    # 登录成功后的缓冲时间 (秒)
    login_success_delay: float = 2.0

    # 页面元素等待超时时间
    element_timeout: int = 10

    # 短超时时间 (用于快速检查)
    short_timeout: int = 3

    # 用户身份检查超时时间
    user_check_timeout: int = 5

    # 导航到新页面后的等待时间 (秒)
    navigate_delay_min: float = 2.0
    navigate_delay_max: float = 3.0

    # 评论区加载后的等待时间 (秒)
    comments_load_delay: float = 1.0

    # 回复操作的延迟时间 (模拟人工操作)
    reply_delay_min: float = 0.1
    reply_delay_max: float = 0.2

    # 滚动页面后的等待时间 (秒)
    scroll_delay_min: float = 0.1
    scroll_delay_max: float = 0.2

    # UI操作步骤间的微小延迟 (秒)
    step_delay_min: float = 0.1
    step_delay_max: float = 0.2

    # 提交回复后的等待时间 (秒)
    submit_result_delay_min: float = 0.1
    submit_result_delay_max: float = 0.2

    # -------------------------------------------------------------------------
    # 浏览器交互配置
    # -------------------------------------------------------------------------

    # "展开"更多评论按钮的最大点击次数 (防止无限展开导致内存溢出)
    max_expand_clicks: int = 10000

    # 页面滚动的最大尝试次数
    max_scroll_attempts: int = 5000

    # 连续没有新评论的最大轮数
    max_no_new_comments: int = 3

    # -------------------------------------------------------------------------
    # 断点续传/起始位置配置
    # -------------------------------------------------------------------------

    # 从第n个一级评论(L1)开始处理 (1-based索引)
    # 设置为 None 则从头开始
    start_from_l1_index: Optional[int] = None

    # 从指定 comment_id 的一级评论开始处理
    # 设置为 None 则不使用此条件
    # 样例: "comment-68a470aa000000003101332e"
    start_from_comment_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # 风控与自动重启配置
    # -------------------------------------------------------------------------

    # 连续回复失败多少次认为触发风控
    max_consecutive_failures: int = 3

    # 最大重启尝试次数 (遇到风控或错误时尝试重启脚本)
    max_restart_attempts: int = 3

    # 重启前的最小等待时间 (秒)
    restart_delay_min: int = 300

    # 重启前的最大等待时间 (秒)
    restart_delay_max: int = 600

    # 是否启用风控检测 (检测到风控信号时自动停止或重启)
    risk_control_detection: bool = True


    # -------------------------------------------------------------------------
    # 其他配置
    # -------------------------------------------------------------------------

    # 评论预览文本长度 (用于日志输出，避免日志过长)
    preview_text_length: int = 50
