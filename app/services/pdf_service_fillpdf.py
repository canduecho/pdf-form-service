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
from app.services.pdf_service import PDFService

class PDFServiceFillPDF:
  """使用fillpdf库的PDF表单处理服务"""
  
  def __init__(self):
    """初始化PDF服务"""
    self.ensure_directories()
    self.pdf_service = PDFService()  # 用于解析字段选项
  
  def ensure_directories(self):
    """确保必要的目录存在"""
    directories = [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR]
    for directory in directories:
      Path(directory).mkdir(parents=True, exist_ok=True)
  
  async def parse_form_fields(self, file: UploadFile) -> List[Dict[str, Any]]:
    """
    解析PDF表单字段，包含 option_text 和 option_value
    """
    import PyPDF2
    from io import BytesIO
    try:
      content = await file.read()
      pdf_reader = PyPDF2.PdfReader(BytesIO(content))
      fields = []
      if pdf_reader.trailer and '/Root' in pdf_reader.trailer:
        root = pdf_reader.trailer['/Root'].get_object()
        if root and '/AcroForm' in root:
          acro_form = root['/AcroForm'].get_object()
          if acro_form and '/Fields' in acro_form:
            form_fields = acro_form['/Fields']
            for field_ref in form_fields:
              field_obj = field_ref.get_object()
              # 字段名
              field_name = field_obj.get('/T', '')
              if isinstance(field_name, bytes):
                field_name = field_name.decode('utf-8', errors='ignore')
              # 字段类型
              field_type = 'text'
              if '/FT' in field_obj:
                ft = field_obj['/FT']
                if ft == '/Btn':
                  if '/Ff' in field_obj:
                    ff = field_obj['/Ff']
                    if ff & 32768:
                      field_type = 'radio'
                    elif ff & 65536:
                      field_type = 'button'
                    else:
                      field_type = 'checkbox'
                  else:
                    field_type = 'checkbox'
                elif ft == '/Ch':
                  if '/Ff' in field_obj:
                    ff = field_obj['/Ff']
                    if ff & 131072:
                      field_type = 'select'
                    else:
                      field_type = 'listbox'
                  else:
                    field_type = 'select'
                elif ft == '/Tx':
                  field_type = 'text'
              # 选项
              options = None
              if field_type in ['select', 'listbox'] and '/Opt' in field_obj:
                opt = field_obj['/Opt']
                options = []
                if isinstance(opt, list):
                  for o in opt:
                    text = o.decode('utf-8', errors='ignore') if isinstance(o, bytes) else str(o)
                    options.append({'text': text, 'value': text})
              elif field_type == 'radio' and '/Opt' in field_obj:
                opt = field_obj['/Opt']
                options = []
                if isinstance(opt, list):
                  for idx, o in enumerate(opt):
                    text = o.decode('utf-8', errors='ignore') if isinstance(o, bytes) else str(o)
                    options.append({'text': text, 'value': str(idx)})
              elif field_type == 'checkbox':
                options = [
                  {'text': '选中', 'value': 'Yes'},
                  {'text': '未选中', 'value': 'Off'}
                ]
              # 字段值
              field_value = field_obj.get('/V', '')
              if isinstance(field_value, bytes):
                field_value = field_value.decode('utf-8', errors='ignore')
              # 组装
              field = {
                'name': field_name,
                'type': field_type,
                'value': field_value if field_value else '',
                'options': options,
                'button_info': None,
                'attributes': {},
                'page': 1,
                'position': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                'required': False
              }
              fields.append(field)
      return fields
    except Exception as e:
      logger.error(f'解析PDF表单字段失败: {str(e)}')
      raise Exception(f'解析PDF表单字段失败: {str(e)}')
  async def fill_form(self, file: UploadFile, fields: List[Dict[str, Any]], strict_validation: bool = True) -> str:
    """
    填充PDF表单
    
    Args:
      file: 原始PDF文件 (UploadFile对象)
      fields: 字段数据列表
      strict_validation: 是否严格验证字段选项，默认为 True
      
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
      
      # 非严格验证模式：验证并删除无效字段
      if not strict_validation:
        field_values = await self._validate_and_remove_invalid_fields_from_path(temp_input_path, field_values)
        logger.info(f'非严格验证模式，最终字段: {list(field_values.keys())}')
      
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
  
      return valid_fields
      
    except Exception as e:
      logger.warning(f'验证字段时发生错误: {str(e)}')
      return field_values  # 如果出错，返回原始字段值
  
  async def fill_form_from_path(self, file_path: str, fields: List[Dict[str, Any]], strict_validation: bool = True) -> str:
    """
    从文件路径填充PDF表单
    
    Args:
      file_path: PDF文件路径
      fields: 字段数据列表
      strict_validation: 是否严格验证字段选项，默认为 True
      
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
      
      # 非严格验证模式：验证并删除无效字段
      if not strict_validation:
        field_values = await self._validate_and_remove_invalid_fields_from_path(file_path, field_values)
        logger.info(f'非严格验证模式，最终字段: {list(field_values.keys())}')
      
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
  
  async def _validate_and_remove_invalid_fields_from_path(self, file_path: str, field_values: Dict[str, str]) -> Dict[str, str]:
    """
    从文件路径验证字段值并删除无效字段（非严格验证模式）
    
    Args:
      file_path: PDF文件路径
      field_values: 字段值映射
      
    Returns:
      删除无效字段后的字段值映射
    """
    try:
      # 创建临时的 UploadFile 对象
      with open(file_path, 'rb') as f:
        content = f.read()
      
      from io import BytesIO
      file_obj = BytesIO(content)
      upload_file = UploadFile(
        filename=os.path.basename(file_path),
        file=file_obj,
        
      )
      
      # 使用 pdf_service 解析字段信息（包含选项）
      parsed_fields = await self.pdf_service.parse_form_fields(upload_file)
      
      # 创建字段选项映射
      field_options = {}
      for field in parsed_fields:
        field_name = field.get('name', '')
        options = field.get('options', [])
        field_type = field.get('type', 'text')
        
        if field_name:
          field_options[field_name] = {
            'options': options,
            'type': field_type
          }
      
      # 验证字段值
      valid_fields = {}
      for field_name, value in field_values.items():
        if field_name in field_options:
          field_info = field_options[field_name]
          field_type = field_info['type']
          options = field_info['options']
          
          # 复选框字段不需要选项验证
          if field_type == 'checkbox':
            valid_fields[field_name] = value
            continue
          
          # 如果有选项且值不在选项中，删除该字段
          if options:
            # 从 options 中提取 value 值
            option_values = [opt.get('value', '') for opt in options if isinstance(opt, dict)]
            if value not in option_values:
              logger.warning(f'字段 {field_name} 的值 "{value}" 不在选项 {option_values} 中，已删除')
              continue
          
          # 验证通过，添加到结果中
          valid_fields[field_name] = value
        else:
          # 字段不存在于PDF中，删除
          logger.warning(f'字段 {field_name} 不存在于PDF表单中，已删除')
      
      return valid_fields
      
    except Exception as e:
      logger.warning(f'验证字段时发生错误: {str(e)}')
      return field_values  # 如果出错，返回原始字段值
  
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
