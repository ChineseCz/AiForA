"""读取 .env 配置。所有可调参数集中在这里。"""
import os

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return (os.getenv(key, default) or "").strip()


# ===== 中转站 API =====
RELAY_API_KEY = _get("RELAY_API_KEY")
RELAY_API_URL = _get("RELAY_API_URL", "https://www.micuapi.ai/v1")
RELAY_MODEL = _get("RELAY_MODEL", "gpt-5.4-mi/ni")
# 帖子配图描述用的视觉模型；不配置就沿用 RELAY_MODEL（若中转站该模型不支持图片输入，需在 .env 单独指定支持视觉的模型名）。
VISION_MODEL = _get("VISION_MODEL", RELAY_MODEL)

# ===== 雪球 =====
XUEQIU_COOKIE = _get("XUEQIU_COOKIE")


def _parse_users(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


XUEQIU_USERS = _parse_users(_get("XUEQIU_USERS"))

# ===== 抓取参数 =====
MAX_PAGES = int(_get("MAX_PAGES", "10") or "10")
FETCH_FULL_TEXT = _get("FETCH_FULL_TEXT", "true").lower() in ("1", "true", "yes", "on")
REQUEST_DELAY = float(_get("REQUEST_DELAY", "1.5") or "1.5")

# ===== 路径 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "posts.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# ===== 浏览器抓取（方案 A：复用专用 Edge 配置目录）=====
# 登录态保存在这个目录里，登录一次后长期有效。
PROFILE_DIR = os.path.join(DATA_DIR, "edge_profile")
# 是否无头运行。默认 false（显示窗口），这样不容易被反爬识别，弹滑块也能手动处理。
HEADLESS = _get("HEADLESS", "false").lower() in ("1", "true", "yes", "on")
