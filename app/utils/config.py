from dotenv import load_dotenv
import os
from pathlib import Path

# 加载环境变量
load_dotenv()

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# 文件路径配置
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
TEMP_DIR = os.getenv("TEMP_DIR", "temp")

# 文件大小限制 (MB)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50"))

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

# 安全配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# 创建全局设置实例
class Settings:
  """应用配置类"""
  
  def __init__(self):
    self.HOST = HOST
    self.PORT = PORT
    self.DEBUG = DEBUG
    self.UPLOAD_DIR = UPLOAD_DIR
    self.OUTPUT_DIR = OUTPUT_DIR
    self.TEMP_DIR = TEMP_DIR
    self.MAX_FILE_SIZE = MAX_FILE_SIZE
    self.LOG_LEVEL = LOG_LEVEL
    self.LOG_FILE = LOG_FILE
    self.SECRET_KEY = SECRET_KEY
    self.BASE_DIR = BASE_DIR

# 创建全局设置实例
settings = Settings()

# 确保目录存在
def ensure_directories():
  """确保必要的目录存在"""
  directories = [
    settings.UPLOAD_DIR,
    settings.OUTPUT_DIR,
    settings.TEMP_DIR,
    'logs'
  ]
  
  for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True) 