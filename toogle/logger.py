import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

# 确保日志目录存在
LOG_DIR = "logs"
try:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
except Exception:
    # 可能会因为权限等问题失败，忽略或使用当前目录
    pass

def setup_logger(name="ToogleBot"):
    logger = logging.getLogger(name)
    
    # 防止重复添加 Handler
    if logger.handlers:
        return logger
    
    # 获取日志等级配置
    log_level_str = "INFO"
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # 格式化
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 Handler (按天轮转)
    try:
        log_file = os.path.join(LOG_DIR, "bot.log")
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file handler: {e}")

    return logger

# 初始化默认 Logger
logger = setup_logger()
