"""
项目静态常量定义
"""
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent

# 项目信息
VERSION = "1.0.0"
PROJECT = f"XHS DunDun Reply V{VERSION}"
LICENCE = "GNU General Public License v3.0"
REPOSITORY = "https://github.com/qhykwsw/xhs_dundun_reply"

# 样式常量
MASTER = "bold magenta"
PROMPT = "bold cyan"
GENERAL = "dim"
WARNING = "bold yellow"
ERROR = "bold red"
SUCCESS = "bold green"
