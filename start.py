#!/usr/bin/env python3
"""
PDF表单处理服务启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.logger import setup_logger
from app.main import app
import uvicorn

def main():
  """主函数"""
  # 设置日志
  logger = setup_logger()
  
  # 确保必要的目录存在
  directories = ['uploads', 'outputs', 'temp', 'logs']
  for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True)
  
  # 启动服务器
  logger.info('启动PDF表单处理服务...')
  
  uvicorn.run(
    'app.main:app',
    host='0.0.0.0',
    port=8001,
    reload=True,
    log_level='info'
  )

if __name__ == '__main__':
  main() 