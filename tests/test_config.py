#!/usr/bin/env python3
"""
测试配置文件是否正确从 .env 文件读取
"""

import os
from app.utils.config import settings, BASE_DIR

def test_config():
  """测试配置读取"""
  print('🔍 测试配置读取...')
  print()
  
  # 显示当前配置值
  print('📋 当前配置值:')
  print(f'  BASE_DIR: {BASE_DIR}')
  print(f'  HOST: {settings.HOST}')
  print(f'  PORT: {settings.PORT}')
  print(f'  DEBUG: {settings.DEBUG}')
  print(f'  UPLOAD_DIR: {settings.UPLOAD_DIR}')
  print(f'  OUTPUT_DIR: {settings.OUTPUT_DIR}')
  print(f'  TEMP_DIR: {settings.TEMP_DIR}')
  print(f'  MAX_FILE_SIZE: {settings.MAX_FILE_SIZE}')
  print(f'  LOG_LEVEL: {settings.LOG_LEVEL}')
  print(f'  LOG_FILE: {settings.LOG_FILE}')
  print(f'  SECRET_KEY: {settings.SECRET_KEY[:10]}...' if len(settings.SECRET_KEY) > 10 else f'  SECRET_KEY: {settings.SECRET_KEY}')
  print()
  
  # 检查环境变量
  print('🌍 环境变量检查:')
  env_vars = ['HOST', 'PORT', 'DEBUG', 'UPLOAD_DIR', 'OUTPUT_DIR', 'TEMP_DIR', 'MAX_FILE_SIZE', 'LOG_LEVEL', 'LOG_FILE', 'SECRET_KEY']
  
  for var in env_vars:
    value = os.getenv(var)
    if value:
      print(f'  {var}: {value} (从环境变量读取)')
    else:
      print(f'  {var}: 未设置 (使用默认值)')
  
  print()
  print('✅ 配置测试完成！')

if __name__ == '__main__':
  test_config() 