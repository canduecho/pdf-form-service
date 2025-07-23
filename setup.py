#!/usr/bin/env python3
"""
PDF表单服务环境设置脚本
"""

import os
import shutil
from pathlib import Path

def setup_environment():
  """设置项目环境"""
  print('🚀 开始设置 PDF 表单服务环境...')
  
  # 检查是否存在 .env 文件
  if not os.path.exists('.env'):
    if os.path.exists('env.example'):
      print('📋 复制环境变量示例文件...')
      shutil.copy('env.example', '.env')
      print('✅ 已创建 .env 文件，请根据需要修改配置')
    else:
      print('❌ 未找到 env.example 文件')
      return False
  else:
    print('✅ .env 文件已存在')
  
  # 创建必要的目录
  directories = ['uploads', 'outputs', 'temp', 'logs']
  for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f'📁 创建目录: {directory}')
  
  # 创建 app 目录结构（如果不存在）
  app_dirs = ['app', 'app/utils', 'app/services', 'app/models']
  for directory in app_dirs:
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f'📁 创建目录: {directory}')
  
  print('\n🎉 环境设置完成！')
  print('\n📝 下一步：')
  print('1. 编辑 .env 文件，根据需要修改配置')
  print('2. 安装依赖: pip install -r requirements.txt')
  print('3. 运行服务: python main.py')
  
  return True

if __name__ == '__main__':
  setup_environment() 