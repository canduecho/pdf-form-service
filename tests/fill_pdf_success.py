#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成功 PDF 表单填写示例
使用 fillpdf 库填写 outputs/Form.pdf 文件，使用所有正确的字段选项
"""

import os
import sys
from fillpdf import fillpdfs
from loguru import logger

def main():
  """主函数"""
  # 设置日志
  logger.remove()
  logger.add(sys.stderr, level='INFO', format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>')
  
  # 文件路径
  pdf_path = 'outputs/Form.pdf'
  output_path = 'outputs/Form_filled.pdf'
  
  # 检查文件是否存在
  if not os.path.exists(pdf_path):
    logger.error(f'PDF 文件不存在: {pdf_path}')
    return
  
  logger.info(f'开始处理 PDF 文件: {pdf_path}')
  
  # 获取表单字段
  try:
    fields = fillpdfs.get_form_fields(pdf_path)
    logger.info(f'找到 {len(fields)} 个表单字段: {list(fields.keys())}')
  except Exception as e:
    logger.error(f'获取表单字段失败: {e}')
    return
  
  # 使用所有正确的字段选项
  form_data = {
    'FullName': '张三',
    'ID': '110101199001011234',
    'Gender': '1',  # 0=女，1=男
    'Married': 'Yes',  # 复选框字段，使用 Yes/No
    'City': 'New York',  # 选项: ['New York', 'London', 'Berlin', 'Paris', 'Rome']
    'Language': 'English',  # 选项: ['English', 'German', 'French', 'Italian']
    'Notes': '这是一个测试填写的内容'
  }
  
  logger.info(f'准备填写的数据: {form_data}')
  
  try:
    # 填写表单
    fillpdfs.write_fillable_pdf(pdf_path, output_path, form_data)
    logger.success(f'PDF 表单填写完成，输出文件: {output_path}')
    
    # 验证填写结果
    filled_fields = fillpdfs.get_form_fields(output_path)
    logger.info(f'填写后的字段值: {filled_fields}')
    
  except Exception as e:
    logger.error(f'填写 PDF 表单失败: {e}')
    return
  
  logger.success('PDF 表单填写完成！')
  
  # 显示输出文件信息
  if os.path.exists(output_path):
    file_size = os.path.getsize(output_path)
    logger.info(f'输出文件大小: {file_size} 字节')
    
    # 显示文件路径
    abs_path = os.path.abspath(output_path)
    logger.info(f'输出文件绝对路径: {abs_path}')

if __name__ == '__main__':
  main() 