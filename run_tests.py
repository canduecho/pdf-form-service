#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行脚本
运行 tests 目录中的所有测试
"""

import os
import sys
import subprocess
from pathlib import Path

def run_test_file(test_file):
  """运行单个测试文件"""
  print(f'🧪 运行测试: {test_file}')
  print('=' * 50)
  
  try:
    # 切换到 tests 目录运行测试
    result = subprocess.run(
      ['python', test_file],
      cwd='tests',
      capture_output=True,
      text=True,
      timeout=60
    )
    
    if result.returncode == 0:
      print('✅ 测试通过')
      print(result.stdout)
    else:
      print('❌ 测试失败')
      print(result.stdout)
      print(result.stderr)
    
    return result.returncode == 0
    
  except subprocess.TimeoutExpired:
    print('⏰ 测试超时')
    return False
  except Exception as e:
    print(f'💥 运行测试时出错: {e}')
    return False

def run_shell_test(test_file):
  """运行 shell 测试文件"""
  print(f'🐚 运行 Shell 测试: {test_file}')
  print('=' * 50)
  
  try:
    # 切换到 tests 目录运行测试
    result = subprocess.run(
      ['bash', test_file],
      cwd='tests',
      capture_output=True,
      text=True,
      timeout=60
    )
    
    if result.returncode == 0:
      print('✅ Shell 测试通过')
      print(result.stdout)
    else:
      print('❌ Shell 测试失败')
      print(result.stdout)
      print(result.stderr)
    
    return result.returncode == 0
    
  except subprocess.TimeoutExpired:
    print('⏰ Shell 测试超时')
    return False
  except Exception as e:
    print(f'💥 运行 Shell 测试时出错: {e}')
    return False

def main():
  """主函数"""
  print('🚀 开始运行所有测试...')
  print()
  
  # 检查 tests 目录是否存在
  if not os.path.exists('tests'):
    print('❌ tests 目录不存在')
    return
  
  # 获取所有测试文件
  test_files = []
  shell_test_files = []
  
  for file in os.listdir('tests'):
    if file.startswith('test_') and file.endswith('.py'):
      test_files.append(file)
    elif file.startswith('test_') and file.endswith('.sh'):
      shell_test_files.append(file)
  
  print(f'📁 找到 {len(test_files)} 个 Python 测试文件')
  print(f'📁 找到 {len(shell_test_files)} 个 Shell 测试文件')
  print()
  
  # 运行 Python 测试
  python_passed = 0
  python_total = len(test_files)
  
  for test_file in test_files:
    if run_test_file(test_file):
      python_passed += 1
    print()
  
  # 运行 Shell 测试
  shell_passed = 0
  shell_total = len(shell_test_files)
  
  for test_file in shell_test_files:
    if run_shell_test(test_file):
      shell_passed += 1
    print()
  
  # 输出测试结果
  print('📊 测试结果汇总')
  print('=' * 50)
  print(f'Python 测试: {python_passed}/{python_total} 通过')
  print(f'Shell 测试: {shell_passed}/{shell_total} 通过')
  
  total_passed = python_passed + shell_passed
  total_tests = python_total + shell_total
  
  print(f'总计: {total_passed}/{total_tests} 通过')
  
  if total_passed == total_tests:
    print('🎉 所有测试都通过了！')
  else:
    print('⚠️  有测试失败，请检查相关功能。')

if __name__ == '__main__':
  main() 