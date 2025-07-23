import sys
from loguru import logger
from pathlib import Path

def setup_logger():
  """配置日志系统"""
  
  # 移除默认的日志处理器
  logger.remove()
  
  # 添加控制台日志处理器
  logger.add(
    sys.stdout,
    format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
    level='INFO',
    colorize=True
  )
  
  # 添加文件日志处理器
  log_file = Path('logs/app.log')
  log_file.parent.mkdir(parents=True, exist_ok=True)
  
  logger.add(
    log_file,
    format='{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}',
    level='DEBUG',
    rotation='10 MB',
    retention='7 days',
    compression='zip'
  )
  
  # 添加错误日志处理器
  error_log_file = Path('logs/error.log')
  logger.add(
    error_log_file,
    format='{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}',
    level='ERROR',
    rotation='10 MB',
    retention='30 days',
    compression='zip'
  )
  
  return logger 