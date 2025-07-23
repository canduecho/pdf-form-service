#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 表单填写功能测试脚本
"""

import os
import sys

# 添加父目录到 Python 路径，以便导入模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_form_filler_practical import PDFFormFiller
from loguru import logger

def test_basic_functionality():
  """测试基本功能"""
  logger.info('=== 测试基本功能 ===')
  
  pdf_path = '../outputs/Form.pdf'
  output_path = '../outputs/test_basic.pdf'
  
  try:
    # 创建填写器
    filler = PDFFormFiller(pdf_path)
    
    # 测试获取字段信息
    field_names = filler.get_field_names()
    logger.info(f'字段名称: {field_names}')
    
    # 测试获取字段详情
    field_info = filler.get_all_field_info()
    logger.info('字段详情:')
    for field_name, info in field_info.items():
      logger.info(f'  {field_name}: {info}')
    
    # 测试创建示例数据
    sample_data = filler.create_sample_data()
    logger.info(f'示例数据: {sample_data}')
    
    # 测试填写表单
    success = filler.fill_form(sample_data, output_path)
    
    if success and os.path.exists(output_path):
      file_size = os.path.getsize(output_path)
      logger.success(f'基本功能测试通过！文件大小: {file_size} 字节')
      return True
    else:
      logger.error('基本功能测试失败！')
      return False
      
  except Exception as e:
    logger.error(f'基本功能测试异常: {e}')
    return False

def test_custom_data():
  """测试自定义数据填写"""
  logger.info('=== 测试自定义数据 ===')
  
  pdf_path = '../outputs/Form.pdf'
  output_path = '../outputs/test_custom.pdf'
  
  try:
    filler = PDFFormFiller(pdf_path)
    
    # 自定义数据
    custom_data = {
      'FullName': '李四',
      'ID': '110101199002022345',
      'Gender': '0',  # 女性
      'Married': 'No',  # 未婚
      'City': 'London',
      'Language': 'German',
      'Notes': '这是自定义测试数据'
    }
    
    # 填写表单
    success = filler.fill_form(custom_data, output_path)
    
    if success and os.path.exists(output_path):
      file_size = os.path.getsize(output_path)
      logger.success(f'自定义数据测试通过！文件大小: {file_size} 字节')
      return True
    else:
      logger.error('自定义数据测试失败！')
      return False
      
  except Exception as e:
    logger.error(f'自定义数据测试异常: {e}')
    return False

def test_data_validation():
  """测试数据验证功能"""
  logger.info('=== 测试数据验证 ===')
  
  pdf_path = '../outputs/Form.pdf'
  
  try:
    filler = PDFFormFiller(pdf_path)
    
    # 测试无效数据
    invalid_data = {
      'FullName': '王五',
      'Gender': '男',  # 无效值
      'City': '北京',  # 无效值
      'Language': '中文'  # 无效值
    }
    
    # 验证数据
    validated_data = filler.validate_form_data(invalid_data)
    logger.info(f'原始数据: {invalid_data}')
    logger.info(f'验证后数据: {validated_data}')
    
    # 检查验证结果
    if validated_data.get('Gender') == '0' and validated_data.get('City') == 'New York':
      logger.success('数据验证测试通过！')
      return True
    else:
      logger.error('数据验证测试失败！')
      return False
      
  except Exception as e:
    logger.error(f'数据验证测试异常: {e}')
    return False

def main():
  """主测试函数"""
  # 设置日志
  logger.remove()
  logger.add(sys.stderr, level='INFO', format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>')
  
  logger.info('开始 PDF 表单填写功能测试')
  
  # 运行测试
  tests = [
    test_basic_functionality,
    test_custom_data,
    test_data_validation
  ]
  
  passed = 0
  total = len(tests)
  
  for test in tests:
    try:
      if test():
        passed += 1
    except Exception as e:
      logger.error(f'测试 {test.__name__} 异常: {e}')
  
  # 输出测试结果
  logger.info(f'=== 测试结果 ===')
  logger.info(f'通过: {passed}/{total}')
  
  if passed == total:
    logger.success('所有测试通过！PDF 表单填写功能正常工作。')
  else:
    logger.warning(f'有 {total - passed} 个测试失败，请检查相关功能。')
  
  # 显示生成的文件
  logger.info('=== 生成的文件 ===')
  output_dir = '../outputs'
  for file in os.listdir(output_dir):
    if file.startswith('test_') and file.endswith('.pdf'):
      file_path = os.path.join(output_dir, file)
      file_size = os.path.getsize(file_path)
      logger.info(f'  {file}: {file_size} 字节')

if __name__ == '__main__':
  main() 