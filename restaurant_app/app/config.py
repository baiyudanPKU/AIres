import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///restaurant_app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    # ==================== AI API 配置 ====================
    # 支持两种模式：
    # 1. 使用自定义 API（如 DeepSeek）：需设置 DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
    # 2. 使用默认北大网关：如果未设置自定义 API，则使用默认的北大网关配置
    
    # 检查是否配置了自定义的 DeepSeek API
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # 默认的北大网关配置（当未配置 DeepSeek API 时使用）
    DEFAULT_GATEWAY_BASE_URL = os.getenv("DEFAULT_GATEWAY_BASE_URL", "https://chat.noc.pku.edu.cn")
    DEFAULT_GATEWAY_API_KEY = os.getenv("DEFAULT_GATEWAY_API_KEY", "GuoWeiCourse_tGv4UT02q7q7")
    DEFAULT_GATEWAY_MODEL = os.getenv("DEFAULT_GATEWAY_MODEL", "deepseek-v3-250324")
    
    # 判断是否使用自定义 API
    USE_CUSTOM_API = DEEPSEEK_API_KEY is not None
    
    # 最终使用的 API 配置
    if USE_CUSTOM_API:
        AI_API_KEY = DEEPSEEK_API_KEY
        AI_BASE_URL = DEEPSEEK_BASE_URL
        AI_MODEL = DEEPSEEK_MODEL
    else:
        AI_API_KEY = DEFAULT_GATEWAY_API_KEY
        AI_BASE_URL = DEFAULT_GATEWAY_BASE_URL
        AI_MODEL = DEFAULT_GATEWAY_MODEL
