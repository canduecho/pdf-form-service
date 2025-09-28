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
    使用fillpdf库解析PDF表单字段
    """
    try:
      # 保存上传的文件到临时位置
      temp_input_path = os.path.join(settings.TEMP_DIR, f'parse_{uuid.uuid4().hex}_{file.filename}')
      content = await file.read()
      
      with open(temp_input_path, 'wb') as f:
        f.write(content)
      
      # 使用fillpdf库的get_form_fields函数
      import fillpdf.fillpdfs as fillpdfs
      fillpdf_fields = fillpdfs.get_form_fields(temp_input_path)
      
      logger.info(f'fillpdf库解析到 {len(fillpdf_fields)} 个字段: {list(fillpdf_fields.keys())}')
      
      # 转换为标准格式
      fields = []
      for field_name, field_value in fillpdf_fields.items():
        field = {
          'name': field_name,
          'type': 'text',  # fillpdf的get_form_fields不返回类型信息，默认为text
          'value': field_value if field_value else '',
          'options': [],  # fillpdf的get_form_fields不返回选项信息
          'button_info': None,
          'attributes': {},
          'page': 1,
          'position': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
          'required': False
        }
        fields.append(field)
      
      # 清理临时文件
      os.remove(temp_input_path)
      
      return fields
      
    except Exception as e:
      logger.error(f'使用fillpdf解析PDF表单字段失败: {str(e)}')
      # 如果fillpdf失败，回退到PyPDF2方法
      try:
        import PyPDF2
        from io import BytesIO
        
        logger.info('fillpdf解析失败，回退到PyPDF2方法...')
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
                
                if field_name:
                  field = {
                    'name': field_name,
                    'type': 'text',
                    'value': '',
                    'options': [],
                    'button_info': None,
                    'attributes': {},
                    'page': 1,
                    'position': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                    'required': False
                  }
                  fields.append(field)
        
        return fields
        
      except Exception as e2:
        logger.error(f'PyPDF2回退解析也失败: {str(e2)}')
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
      
      # 先尝试获取现有字段来理解字段结构，利用fillpdf的子字段支持
      existing_fields = {}
      final_field_values = field_values
      
      try:
        existing_fields = fillpdfs.get_form_fields(temp_input_path)
        logger.info(f'PDF中现有字段: {list(existing_fields.keys())}')
        
        # 检查是否需要字段名映射 - 但保留原始字段以支持隐藏/子字段
        mapped_field_values = {}
        for field_name, field_value in field_values.items():
          # 直接匹配
          if field_name in existing_fields:
            mapped_field_values[field_name] = field_value
            logger.debug(f'直接匹配字段: {field_name}')
          else:
            # 首先尝试保留原始字段名（fillpdf可能支持隐藏字段）
            mapped_field_values[field_name] = field_value
            logger.info(f'保留原始字段名（可能是隐藏/子字段）: {field_name}')
            
            # 尝试模糊匹配作为备选（去除空格、大小写等）
            matched = False
            for existing_field in existing_fields.keys():
              if (field_name.lower().replace(' ', '') == 
                  existing_field.lower().replace(' ', '')):
                # 如果找到精确匹配，则替换原始字段名
                mapped_field_values[existing_field] = field_value
                mapped_field_values.pop(field_name, None)  # 移除原始字段名
                logger.info(f'精确映射字段: "{field_name}" -> "{existing_field}"')
                matched = True
                break
            
            # 只有在严格验证模式下才报告未匹配字段为警告
            if not matched and strict_validation:
              logger.warning(f'严格模式下未找到匹配字段: {field_name}')
            elif not matched:
              logger.debug(f'保持原始字段名，让fillpdf处理: {field_name}')
        
        # 使用映射后的字段值
        final_field_values = mapped_field_values
        logger.info(f'最终字段值: {list(final_field_values.keys())}')
        
      except Exception as e:
        logger.warning(f'获取现有字段失败: {str(e)}，使用原始字段值')

      # 使用fillpdf填充表单（利用其子字段支持）
      try:
        fillpdfs.write_fillable_pdf(temp_input_path, output_path, final_field_values)
        logger.info(f'使用fillpdf成功填充，支持子字段')
      except AttributeError as e:
        if "'NoneType' object has no attribute 'update'" in str(e):
          logger.warning('PDF AcroForm结构问题，尝试修复后重试...')
          # 尝试修复PDF结构后重新填充
          import PyPDF2
          from PyPDF2.generic import DictionaryObject
          
          # 读取并修复PDF
          with open(temp_input_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            writer = PyPDF2.PdfWriter()
            
            # 复制所有页面
            for page in reader.pages:
              writer.add_page(page)
            
            # 确保AcroForm存在
            if hasattr(writer, 'trailer') and writer.trailer and '/Root' in writer.trailer:
              root = writer.trailer['/Root']
              if '/AcroForm' not in root:
                root['/AcroForm'] = DictionaryObject()
                logger.info('创建缺失的AcroForm结构')
          
          # 保存修复后的PDF到临时文件
          fixed_input_path = temp_input_path.replace('.pdf', '_fixed.pdf')
          with open(fixed_input_path, 'wb') as f:
            writer.write(f)
          
          # 使用修复后的PDF重试填充
          try:
            fillpdfs.write_fillable_pdf(fixed_input_path, output_path, final_field_values)
            logger.info('使用修复PDF成功填充')
            # 清理临时文件
            os.remove(fixed_input_path)
          except Exception as e2:
            logger.error(f'修复PDF后仍然填充失败: {str(e2)}')
            # 清理临时文件
            if os.path.exists(fixed_input_path):
              os.remove(fixed_input_path)
            raise e2
        else:
          raise e
      
      # 清理临时文件
      os.remove(temp_input_path)
      
      logger.info(f'使用fillpdf填充PDF表单完成: {output_path}')
      return output_path
      
    except Exception as outer_e:
      logger.error(f'填充PDF表单失败: {str(outer_e)}')
      raise Exception(f'填充PDF表单失败: {str(outer_e)}')
  
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
      
    except Exception as path_e:
      logger.error(f'填充PDF表单失败: {str(path_e)}')
      raise Exception(f'填充PDF表单失败: {str(path_e)}')
  
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
