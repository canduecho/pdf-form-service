import os
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from loguru import logger
import aiofiles
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile

from fillpdf import fillpdfs

from app.utils.config import settings

class PDFServiceFillPDF:
  """使用fillpdf库的PDF表单处理服务"""
  
  def __init__(self):
    """初始化PDF服务"""
    self.ensure_directories()
  
  def ensure_directories(self):
    """确保必要的目录存在"""
    directories = [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR]
    for directory in directories:
      Path(directory).mkdir(parents=True, exist_ok=True)
  
  async def parse_form_fields(self, file: UploadFile) -> List[Dict[str, Any]]:
    """
    解析PDF表单字段
    
    Args:
      file: 上传的PDF文件
      
    Returns:
      字段列表，包含字段名称、类型、位置等信息
    """
    try:
      # 保存上传的文件到临时位置
      temp_file_path = os.path.join(settings.TEMP_DIR, f'temp_{uuid.uuid4().hex}_{file.filename}')
      content = await file.read()
      
      with open(temp_file_path, 'wb') as f:
        f.write(content)
      
      # 使用fillpdf提取字段信息
      fields_data = fillpdfs.get_form_fields(temp_file_path)
      
      # 清理临时文件
      os.remove(temp_file_path)
      
      # 转换字段格式
      fields = []
      for field_name, field_value in fields_data.items():
        # fillpdf返回的是 {field_name: field_value} 格式
        field = {
          'name': field_name,
          'type': 'text',  # 默认类型，fillpdf不提供类型信息
          'value': field_value if field_value else '',
          'options': None,
          'button_info': None,
          'attributes': {},
          'page': 1,  # fillpdf默认处理第一页
          'position': {
            'x': 0,
            'y': 0,
            'width': 0,
            'height': 0
          },
          'required': False
        }
        fields.append(field)
      
      logger.info(f'使用fillpdf解析到 {len(fields)} 个表单字段')
      return fields
      
    except Exception as e:
      logger.error(f'解析PDF表单字段失败: {str(e)}')
      raise Exception(f'解析PDF表单字段失败: {str(e)}')
  
  def _get_field_type(self, field_info: Dict[str, Any]) -> str:
    """根据字段信息确定字段类型"""
    field_type = field_info.get('type', '')
    
    if field_type == 'text':
      return 'text'
    elif field_type == 'checkbox':
      return 'checkbox'
    elif field_type == 'radio':
      return 'radio'
    elif field_type == 'select':
      return 'select'
    elif field_type == 'listbox':
      return 'listbox'
    elif field_type == 'button':
      return 'button'
    else:
      return 'text'  # 默认类型
  
  async def fill_form(self, file: UploadFile, fields: List[Dict[str, Any]]) -> str:
    """
    填充PDF表单
    
    Args:
      file: 原始PDF文件 (UploadFile对象)
      fields: 字段数据列表
      
    Returns:
      填充后的PDF文件路径
    """
    try:
      # 保存上传的文件到临时位置
      temp_input_path = os.path.join(settings.TEMP_DIR, f'input_{uuid.uuid4().hex}_{file.filename}')
      content = await file.read()
      
      with open(temp_input_path, 'wb') as f:
        f.write(content)
      
      # 创建字段值字典
      field_values = {}
      for field in fields:
        field_name = field.get('name', '')
        if field_name:
          field_values[field_name] = field.get('value', '')
      
      # 生成输出文件名
      output_filename = f'filled_{uuid.uuid4().hex}_{file.filename}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 使用fillpdf填充表单
      fillpdfs.write_fillable_pdf(temp_input_path, output_path, field_values)
      
      # 清理临时文件
      os.remove(temp_input_path)
      
      logger.info(f'使用fillpdf填充PDF表单完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'填充PDF表单失败: {str(e)}')
      raise Exception(f'填充PDF表单失败: {str(e)}')
  
  async def fill_form_from_path(self, file_path: str, fields: List[Dict[str, Any]]) -> str:
    """
    从文件路径填充PDF表单
    
    Args:
      file_path: PDF文件路径
      fields: 字段数据列表
      
    Returns:
      填充后的PDF文件路径
    """
    try:
      # 创建字段值字典
      field_values = {}
      for field in fields:
        field_name = field.get('name', '')
        if field_name:
          field_values[field_name] = field.get('value', '')
      
      # 生成输出文件名
      original_filename = os.path.basename(file_path)
      output_filename = f'filled_{uuid.uuid4().hex}_{original_filename}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 使用fillpdf填充表单
      fillpdfs.write_fillable_pdf(file_path, output_path, field_values)
      
      logger.info(f'使用fillpdf填充PDF表单完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'填充PDF表单失败: {str(e)}')
      raise Exception(f'填充PDF表单失败: {str(e)}')
  
  async def create_sample_form(self) -> str:
    """
    创建示例PDF表单
    
    Returns:
      创建的PDF文件路径
    """
    try:
      # 创建示例表单
      output_path = os.path.join(settings.OUTPUT_DIR, 'Form.pdf')
      
      # 使用reportlab创建简单的表单
      c = canvas.Canvas(output_path, pagesize=letter)
      width, height = letter
      
      # 标题
      c.setFont("Helvetica-Bold", 16)
      c.drawString(50, height - 50, "示例表单")
      
      # 字段标签和输入框
      y_position = height - 100
      field_spacing = 40
      
      fields = [
        ("Full name:", "FullName"),
        ("ID:", "ID"),
        ("Gender:", "Gender"),
        ("Married:", "Married"),
        ("City:", "City"),
        ("Language:", "Language"),
        ("Notes:", "Notes")
      ]
      
      c.setFont("Helvetica", 12)
      for label, field_name in fields:
        c.drawString(50, y_position, label)
        # 绘制输入框
        c.rect(200, y_position - 15, 150, 20)
        y_position -= field_spacing
      
      c.save()
      
      logger.info(f'示例表单创建成功: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'创建示例表单失败: {str(e)}')
      raise Exception(f'创建示例表单失败: {str(e)}') 