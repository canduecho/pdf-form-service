#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实用 PDF 表单填写工具
基于已知的字段选项提供 PDF 表单填写功能
"""

import os
import sys
from pathlib import Path
from fillpdf import fillpdfs
from loguru import logger
from typing import Dict, List, Optional, Any

class PDFFormFiller:
  """PDF 表单填写工具类"""
  
  def __init__(self, pdf_path: str):
    """
    初始化 PDF 表单填写器
    
    Args:
      pdf_path (str): PDF 文件路径
    """
    self.pdf_path = pdf_path
    self.fields = {}
    
    # 已知的字段选项（基于测试结果）
    self.known_options = {
      'Gender': ['0', '1'],  # 0=女，1=男
      'City': ['New York', 'London', 'Berlin', 'Paris', 'Rome'],
      'Language': ['English', 'German', 'French', 'Italian']
    }
    
    # 复选框字段（不需要选项验证）
    self.checkbox_fields = ['Married']
    
    if not os.path.exists(pdf_path):
      raise FileNotFoundError(f'PDF 文件不存在: {pdf_path}')
    
    # 获取表单字段信息
    self._load_form_fields()
  
  def _load_form_fields(self):
    """加载表单字段信息"""
    try:
      self.fields = fillpdfs.get_form_fields(self.pdf_path)
      logger.info(f'加载了 {len(self.fields)} 个表单字段')
    except Exception as e:
      logger.error(f'加载表单字段失败: {e}')
      raise
  
  def get_field_names(self) -> List[str]:
    """
    获取所有字段名称
    
    Returns:
      List[str]: 字段名称列表
    """
    return list(self.fields.keys())
  
  def get_field_options(self, field_name: str) -> List[str]:
    """
    获取指定字段的选项
    
    Args:
      field_name (str): 字段名称
      
    Returns:
      List[str]: 选项列表
    """
    return self.known_options.get(field_name, [])
  
  def is_checkbox_field(self, field_name: str) -> bool:
    """
    判断字段是否为复选框
    
    Args:
      field_name (str): 字段名称
      
    Returns:
      bool: 是否为复选框
    """
    return field_name in self.checkbox_fields
  
  def get_all_field_info(self) -> Dict[str, Dict[str, Any]]:
    """
    获取所有字段的详细信息
    
    Returns:
      Dict: 字段信息字典
    """
    field_info = {}
    for field_name in self.fields.keys():
      field_info[field_name] = {
        'type': self.fields.get(field_name),
        'options': self.get_field_options(field_name),
        'is_checkbox': self.is_checkbox_field(field_name)
      }
    return field_info
  
  def validate_form_data(self, form_data: Dict[str, str]) -> Dict[str, str]:
    """
    验证表单数据，确保所有值都是有效的
    
    Args:
      form_data (Dict[str, str]): 表单数据
      
    Returns:
      Dict[str, str]: 验证后的表单数据
    """
    validated_data = {}
    
    for field_name, value in form_data.items():
      if field_name not in self.fields:
        logger.warning(f'字段 {field_name} 不存在，跳过')
        continue
      
      # 复选框字段不需要选项验证
      if self.is_checkbox_field(field_name):
        # 将布尔值转换为复选框可接受的值
        if isinstance(value, bool):
          value = 'Yes' if value else 'No'
        elif value.lower() in ['true', '1', 'yes', 'on', 'checked']:
          value = 'Yes'
        elif value.lower() in ['false', '0', 'no', 'off', 'unchecked']:
          value = 'No'
        else:
          # 保持原值
          pass
        logger.info(f'复选框字段 {field_name} 使用值: {value}')
      else:
        # 检查字段是否有选项限制
        options = self.get_field_options(field_name)
        if options and value not in options:
          logger.warning(f'字段 {field_name} 的值 "{value}" 不在选项 {options} 中')
          # 使用第一个选项作为默认值
          value = options[0]
          logger.info(f'使用默认值: {value}')
      
      validated_data[field_name] = value
    
    return validated_data
  
  def fill_form(self, form_data: Dict[str, str], output_path: str) -> bool:
    """
    填写 PDF 表单
    
    Args:
      form_data (Dict[str, str]): 表单数据
      output_path (str): 输出文件路径
      
    Returns:
      bool: 是否成功
    """
    try:
      # 验证表单数据
      validated_data = self.validate_form_data(form_data)
      
      if not validated_data:
        logger.error('没有有效的表单数据')
        return False
      
      logger.info(f'准备填写字段: {list(validated_data.keys())}')
      logger.info(f'表单数据: {validated_data}')
      
      # 填写表单
      fillpdfs.write_fillable_pdf(self.pdf_path, output_path, validated_data)
      
      logger.success(f'PDF 表单填写完成: {output_path}')
      
      # 验证填写结果
      filled_fields = fillpdfs.get_form_fields(output_path)
      logger.info(f'填写后的字段值: {filled_fields}')
      
      return True
      
    except Exception as e:
      logger.error(f'填写 PDF 表单失败: {e}')
      return False
  
  def create_sample_data(self) -> Dict[str, str]:
    """
    创建示例表单数据
    
    Returns:
      Dict[str, str]: 示例表单数据
    """
    sample_data = {}
    
    for field_name in self.fields.keys():
      options = self.get_field_options(field_name)
      
      # 根据字段名称和选项创建示例数据
      if field_name.lower() in ['name', 'fullname', 'username']:
        sample_data[field_name] = '张三'
      elif field_name.lower() in ['id', 'idnumber', 'identity']:
        sample_data[field_name] = '110101199001011234'
      elif field_name.lower() in ['gender', 'sex']:
        if '0' in options and '1' in options:
          sample_data[field_name] = '1'  # 男性
        else:
          sample_data[field_name] = '男'
      elif field_name.lower() in ['married', 'marriage']:
        # 复选框字段，使用 Yes/No
        sample_data[field_name] = 'Yes'  # 已婚
      elif field_name.lower() in ['city', 'location']:
        if options:
          sample_data[field_name] = options[0]  # 使用第一个选项
        else:
          sample_data[field_name] = '北京'
      elif field_name.lower() in ['language', 'lang']:
        if options:
          sample_data[field_name] = options[0]  # 使用第一个选项
        else:
          sample_data[field_name] = '中文'
      elif field_name.lower() in ['notes', 'comment', 'description']:
        sample_data[field_name] = '这是一个示例填写的内容'
      elif field_name.lower() in ['resetbutton', 'button']:
        # 跳过按钮字段
        continue
      else:
        # 对于其他字段，如果有选项就选择第一个
        if options:
          sample_data[field_name] = options[0]
        else:
          sample_data[field_name] = '示例值'
    
    return sample_data

def main():
  """示例用法"""
  # 设置日志
  logger.remove()
  logger.add(sys.stderr, level='INFO', format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>')
  
  # 创建 PDF 表单填写器
  pdf_path = 'outputs/Form.pdf'
  output_path = 'outputs/Form_filled_with_tool.pdf'
  
  try:
    filler = PDFFormFiller(pdf_path)
    
    # 显示字段信息
    logger.info('表单字段信息:')
    field_info = filler.get_all_field_info()
    for field_name, info in field_info.items():
      logger.info(f'  {field_name}: {info}')
    
    # 创建示例数据
    sample_data = filler.create_sample_data()
    logger.info(f'示例数据: {sample_data}')
    
    # 填写表单
    success = filler.fill_form(sample_data, output_path)
    
    if success:
      logger.success('PDF 表单填写成功！')
      
      # 显示输出文件信息
      if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        logger.info(f'输出文件大小: {file_size} 字节')
    else:
      logger.error('PDF 表单填写失败！')
      
  except Exception as e:
    logger.error(f'处理失败: {e}')

if __name__ == '__main__':
  main() 