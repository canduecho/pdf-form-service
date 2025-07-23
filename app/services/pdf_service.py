import PyPDF2
import io
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from loguru import logger
import aiofiles
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile

from app.utils.config import settings

class PDFService:
  """PDF表单处理服务"""
  
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
      # 读取PDF文件内容
      content = await file.read()
      
      # 创建PDF读取器
      pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
      
      fields = []
      
      # 方法1: 从 AcroForm 中获取字段信息（推荐）
      if pdf_reader.trailer and '/Root' in pdf_reader.trailer:
        root = pdf_reader.trailer['/Root'].get_object()
        if root and '/AcroForm' in root:  # type: ignore
          acro_form = root['/AcroForm'].get_object()  # type: ignore
          if acro_form and '/Fields' in acro_form:  # type: ignore
            form_fields = acro_form['/Fields']  # type: ignore
            for field_ref in form_fields:
              field_obj = field_ref.get_object()
              field_info = self._extract_acroform_field_info(field_obj)
              if field_info:
                if field_info.get('type') == 'button':
                  logger.debug(f'跳过按钮字段: {field_info.get("name", "Unknown")}')
                else:
                  fields.append(field_info)
      
      # 方法2: 从页面注释中获取字段信息
      if not fields:
        for page_num, page in enumerate(pdf_reader.pages):
          if '/Annots' in page:
            annotations = page['/Annots']
            
            if annotations:
              # 获取 annotations 的实际值
              annotations_obj = annotations.get_object()
              if isinstance(annotations_obj, list):
                annotation_list = annotations_obj
              else:
                annotation_list = [annotations_obj]
              
              for annotation in annotation_list:
                try:
                  if annotation.get('/Subtype') == '/Widget':  # type: ignore
                    field_info = self._extract_field_info(annotation, page_num)
                    if field_info:
                      if field_info.get('type') == 'button':
                        logger.debug(f'跳过按钮字段: {field_info.get("name", "Unknown")}')
                      else:
                        fields.append(field_info)
                except (KeyError, AttributeError):
                  continue
      
      # 方法3: 如果没有找到表单字段，尝试文本识别
      if not fields:
        fields = self._extract_text_fields(pdf_reader)
      
      logger.info(f'解析到 {len(fields)} 个表单字段')
      return fields
      
    except Exception as e:
      logger.error(f'解析PDF表单字段失败: {str(e)}')
      raise Exception(f'解析PDF表单字段失败: {str(e)}')
  
  def _extract_acroform_field_info(self, field_obj) -> Optional[Dict[str, Any]]:
    """
    从 AcroForm 字段对象中提取字段信息
    
    Args:
      field_obj: AcroForm 字段对象
      
    Returns:
      字段信息字典
    """
    try:
      # 获取字段名称
      field_name = field_obj.get('/T', '')
      if isinstance(field_name, bytes):
        field_name = field_name.decode('utf-8', errors='ignore')
      
      # 尝试获取标签文本
      label = None
      # 1. 尝试从 TU (tool tip) 获取
      if '/TU' in field_obj:
        label = field_obj['/TU']
        if isinstance(label, bytes):
          label = label.decode('utf-8', errors='ignore')
      # 2. 尝试从 TM (mapping name) 获取
      if not label and '/TM' in field_obj:
        label = field_obj['/TM']
        if isinstance(label, bytes):
          label = label.decode('utf-8', errors='ignore')
      # 3. 尝试从相关注释获取
      if not label and '/Parent' in field_obj:
        parent = field_obj['/Parent'].get_object()
        if '/TU' in parent:
          label = parent['/TU']
          if isinstance(label, bytes):
            label = label.decode('utf-8', errors='ignore')
      
      # 获取字段类型
      field_type = 'text'  # 默认为文本类型
      if '/FT' in field_obj:
        ft = field_obj['/FT']
        if ft == '/Btn':
          # 检查按钮类型
          if '/Ff' in field_obj:
            ff = field_obj['/Ff']
            if ff & 32768:  # Radio button flag
              field_type = 'radio'
            elif ff & 65536:  # Push button flag
              field_type = 'button'
            else:
              field_type = 'checkbox'
          else:
            field_type = 'checkbox'
        elif ft == '/Ch':
          # 检查是否为下拉选择框
          if '/Ff' in field_obj:
            ff = field_obj['/Ff']
            if ff & 131072:  # Combo box flag
              field_type = 'select'
            else:
              field_type = 'listbox'
          else:
            field_type = 'select'
        elif ft == '/Tx':
          field_type = 'text'
      
      # 获取字段值
      field_value = field_obj.get('/V', '')
      if isinstance(field_value, bytes):
        field_value = field_value.decode('utf-8', errors='ignore')
      
      # 获取字段属性
      field_attributes = {}
      
      # 获取最大长度（对于文本字段）
      if field_type == 'text' and '/MaxLen' in field_obj:
        max_len = field_obj['/MaxLen']
        if isinstance(max_len, (int, float)):
          field_attributes['max_length'] = int(max_len)
      
      # 获取字段标志
      if '/Ff' in field_obj:
        ff = field_obj['/Ff']
        if isinstance(ff, (int, float)):
          flags_int = int(ff)
          field_attributes['flags'] = flags_int
          field_attributes['flag_meanings'] = self._parse_field_flags(flags_int)
      
      # 获取选项（对于选择框和单选按钮）
      options = []
      if field_type in ['select', 'radio', 'checkbox', 'listbox'] and '/Opt' in field_obj:
        opt = field_obj['/Opt']
        if isinstance(opt, list):
          for option in opt:
            if isinstance(option, bytes):
              options.append(option.decode('utf-8', errors='ignore'))
            else:
              options.append(str(option))
      
      # 获取按钮信息（对于按钮类型）
      button_info = None
      if field_type == 'button':
        button_info = self._extract_button_info(field_obj)
      
      # 获取字段位置
      rect = field_obj.get('/Rect', [0, 0, 0, 0])
      
      return {
        'name': field_name,
        'label': label,  # 添加标签
        'type': field_type,
        'value': field_value,
        'options': options if options else None,
        'button_info': button_info,
        'attributes': field_attributes if field_attributes else None,
        'page': 1,  # AcroForm 字段通常在第一页
        'position': {
          'x': rect[0],
          'y': rect[1],
          'width': rect[2] - rect[0],
          'height': rect[3] - rect[1]
        },
        'required': False  # 默认非必填
      }
      
    except Exception as e:
      logger.warning(f'提取 AcroForm 字段信息失败: {str(e)}')
      return None
  
  def _extract_button_info(self, field_obj) -> Optional[Dict[str, Any]]:
    """
    提取按钮信息
    
    Args:
      field_obj: 按钮字段对象
      
    Returns:
      按钮信息字典
    """
    try:
      button_info = {}
      
      # 获取按钮文本
      if '/MK' in field_obj and '/CA' in field_obj['/MK']:
        ca = field_obj['/MK']['/CA']
        if isinstance(ca, bytes):
          button_info['text'] = ca.decode('utf-8', errors='ignore')
        else:
          button_info['text'] = str(ca)
      
      # 获取按钮动作
      if '/A' in field_obj:
        action = field_obj['/A']
        if '/S' in action:
          action_type = action['/S']
          if isinstance(action_type, bytes):
            action_type = action_type.decode('utf-8', errors='ignore')
          button_info['action'] = str(action_type)
      
      return button_info if button_info else None
      
    except Exception as e:
      logger.warning(f'提取按钮信息失败: {str(e)}')
      return None
  
  def _parse_field_flags(self, flags: int) -> Dict[str, bool]:
    """
    解析字段标志的含义
    
    Args:
      flags: 字段标志值
      
    Returns:
      标志含义字典
    """
    flag_meanings = {
      'read_only': bool(flags & 1),
      'required': bool(flags & 2),
      'no_export': bool(flags & 4),
      'multiline': bool(flags & 4096),
      'password': bool(flags & 8192),
      'file_select': bool(flags & 1048576),
      'do_not_spell_check': bool(flags & 4194304),
      'do_not_scroll': bool(flags & 8388608),
      'comb': bool(flags & 16777216),  # 等宽字符显示
      'rich_text': bool(flags & 33554432),
      'radios_in_unison': bool(flags & 33554432),
      'combo': bool(flags & 131072),
      'edit': bool(flags & 262144),
      'sort': bool(flags & 524288),
      'multi_select': bool(flags & 2097152),
      'commit_on_sel_change': bool(flags & 67108864)
    }
    
    return flag_meanings
  
  def _extract_field_info(self, annotation, page_num: int) -> Optional[Dict[str, Any]]:
    """
    从PDF注释中提取字段信息
    
    Args:
      annotation: PDF注释对象
      page_num: 页码
      
    Returns:
      字段信息字典
    """
    try:
      # 如果 annotation 已经是对象，直接使用；否则获取对象
      obj = annotation if hasattr(annotation, 'get') else annotation.get_object()
      
      # 获取字段名称
      field_name = obj.get('/T', '')
      if isinstance(field_name, bytes):
        field_name = field_name.decode('utf-8', errors='ignore')
      
      # 尝试获取标签文本
      label = None
      # 1. 尝试从 TU (tool tip) 获取
      if '/TU' in obj:
        label = obj['/TU']
        if isinstance(label, bytes):
          label = label.decode('utf-8', errors='ignore')
      # 2. 尝试从 TM (mapping name) 获取
      if not label and '/TM' in obj:
        label = obj['/TM']
        if isinstance(label, bytes):
          label = label.decode('utf-8', errors='ignore')
      # 3. 尝试从相关注释获取
      if not label and '/Parent' in obj:
        parent = obj['/Parent'].get_object()
        if '/TU' in parent:
          label = parent['/TU']
          if isinstance(label, bytes):
            label = label.decode('utf-8', errors='ignore')
      
      # 获取字段类型
      field_type = 'text'  # 默认为文本类型
      if '/FT' in obj:
        ft = obj['/FT']
        if ft == '/Btn':
          # 检查按钮类型
          if '/Ff' in obj:
            ff = obj['/Ff']
            if ff & 32768:  # Radio button flag
              field_type = 'radio'
            elif ff & 65536:  # Push button flag
              field_type = 'button'
            else:
              field_type = 'checkbox'
          else:
            field_type = 'checkbox'
        elif ft == '/Ch':
          # 检查是否为下拉选择框
          if '/Ff' in obj:
            ff = obj['/Ff']
            if ff & 131072:  # Combo box flag
              field_type = 'select'
            else:
              field_type = 'listbox'
          else:
            field_type = 'select'
        elif ft == '/Tx':
          field_type = 'text'
      
      # 获取字段值
      field_value = obj.get('/V', '')
      if isinstance(field_value, bytes):
        field_value = field_value.decode('utf-8', errors='ignore')
      
      # 获取字段属性
      field_attributes = {}
      
      # 获取最大长度（对于文本字段）
      if field_type == 'text' and '/MaxLen' in obj:
        max_len = obj['/MaxLen']
        if isinstance(max_len, (int, float)):
          field_attributes['max_length'] = int(max_len)
      
      # 获取字段标志
      if '/Ff' in obj:
        ff = obj['/Ff']
        if isinstance(ff, (int, float)):
          flags_int = int(ff)
          field_attributes['flags'] = flags_int
          field_attributes['flag_meanings'] = self._parse_field_flags(flags_int)
      
      # 获取选项（对于选择框和单选按钮）
      options = []
      if field_type in ['select', 'radio', 'checkbox'] and '/Opt' in obj:
        opt = obj['/Opt']
        if isinstance(opt, list):
          for option in opt:
            if isinstance(option, bytes):
              options.append(option.decode('utf-8', errors='ignore'))
            else:
              options.append(str(option))
      
      # 获取按钮信息（对于按钮类型）
      button_info = None
      if field_type == 'button':
        button_info = self._extract_button_info(obj)
      
      # 获取字段位置
      rect = obj.get('/Rect', [0, 0, 0, 0])
      
      return {
        'name': field_name,
        'label': label,  # 添加标签
        'type': field_type,
        'value': field_value,
        'options': options if options else None,
        'button_info': button_info,
        'attributes': field_attributes if field_attributes else None,
        'page': page_num + 1,
        'position': {
          'x': rect[0],
          'y': rect[1],
          'width': rect[2] - rect[0],
          'height': rect[3] - rect[1]
        },
        'required': False  # 默认非必填
      }
      
    except Exception as e:
      logger.warning(f'提取字段信息失败: {str(e)}')
      return None
  
  def _extract_text_fields(self, pdf_reader) -> List[Dict[str, Any]]:
    """
    从PDF文本中提取可能的表单字段，支持多种字段类型
    
    Args:
      pdf_reader: PDF读取器
      
    Returns:
      可能的字段列表
    """
    fields = []
    
    try:
      for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        
        # 字段识别逻辑
        lines = text.split('\n')
        for line in lines:
          line = line.strip()
          
          # 跳过空行和过长的行
          if not line or len(line) > 200:
            continue
          
          # 识别不同类型的字段
          field_info = self._identify_field_type(line, page_num)
          if field_info:
            fields.append(field_info)
      
    except Exception as e:
      logger.warning(f'提取文本字段失败: {str(e)}')
    
    return fields
  
  def _identify_field_type(self, line: str, page_num: int) -> Optional[Dict[str, Any]]:
    """
    识别字段类型和提取字段信息
    
    Args:
      line: 文本行
      page_num: 页码
      
    Returns:
      字段信息字典或None
    """
    try:
      # 1. 识别复选框 (checkbox)
      if self._is_checkbox_field(line):
        return self._extract_checkbox_field(line, page_num)
      
      # 2. 识别选择框 (select/dropdown)
      elif self._is_select_field(line):
        return self._extract_select_field(line, page_num)
      
      # 3. 识别单选按钮 (radio)
      elif self._is_radio_field(line):
        return self._extract_radio_field(line, page_num)
      
      # 4. 识别文本字段 (text)
      elif ':' in line and len(line) < 100:
        return self._extract_text_field(line, page_num)
      
      # 5. 识别必填字段标记
      elif self._is_required_field(line):
        return self._extract_required_field(line, page_num)
      
    except Exception as e:
      logger.warning(f'识别字段类型失败: {str(e)}')
    
    return None
  
  def _is_checkbox_field(self, line: str) -> bool:
    """判断是否为复选框字段"""
    # 支持简繁中文和英文的复选框标记
    checkbox_indicators = [
      # 通用符号
      '□', '☐', '☑', '☒', '[ ]', '[x]', '[X]', '☐', '☑', '☒',
      # 简体中文
      '□ 是', '□ 否', '□ 同意', '□ 不同意', '□ 有', '□ 无',
      # 繁体中文
      '□ 是', '□ 否', '□ 同意', '□ 不同意', '□ 有', '□ 無',
      # 英文
      '□ Yes', '□ No', '□ Agree', '□ Disagree', '□ Yes/No',
      '[ ] Yes', '[ ] No', '[ ] Agree', '[ ] Disagree',
      # 混合语言
      '□ 是/否', '□ Yes/No', '□ 同意/不同意', '□ Agree/Disagree'
    ]
    return any(indicator in line for indicator in checkbox_indicators)
  
  def _is_select_field(self, line: str) -> bool:
    """判断是否为选择框字段"""
    # 支持简繁中文和英文的选择框标记
    select_indicators = [
      # 简体中文
      '请选择', '选择', '下拉', '选项', '□ 男 □ 女', '□ 已婚 □ 未婚',
      # 繁体中文
      '請選擇', '選擇', '下拉', '選項', '□ 男 □ 女', '□ 已婚 □ 未婚',
      # 英文
      'Please select', 'Select', 'Choose', 'Option', 'Dropdown',
      '□ Male □ Female', '□ Married □ Single', '□ Yes □ No',
      # 混合语言
      '请选择/Please select', '选择/Select'
    ]
    return any(indicator in line for indicator in select_indicators)
  
  def _is_radio_field(self, line: str) -> bool:
    """判断是否为单选按钮字段"""
    # 支持简繁中文和英文的单选按钮标记
    radio_indicators = [
      # 通用符号
      '○', '●', '○ 是 ○ 否', '● 是 ○ 否',
      # 简体中文
      '○ 是', '○ 否', '● 是', '● 否',
      # 繁体中文
      '○ 是', '○ 否', '● 是', '● 否',
      # 英文
      '○ Yes', '○ No', '● Yes', '● No', '○ Yes ○ No', '● Yes ○ No',
      # 混合语言
      '○ 是/Yes', '○ 否/No'
    ]
    return any(indicator in line for indicator in radio_indicators)
  
  def _is_required_field(self, line: str) -> bool:
    """判断是否为必填字段"""
    # 支持简繁中文和英文的必填标记
    required_indicators = [
      # 通用符号
      '*', '（必填）', '(必填)', '（必選）', '(必選)',
      # 简体中文
      '必填', '必选', '必填项', '必选项', '（必填）', '(必填)',
      # 繁体中文
      '必填', '必選', '必填項', '必選項', '（必填）', '(必填)',
      # 英文
      'required', 'Required', 'REQUIRED', 'Required field',
      'Mandatory', 'MANDATORY', '(Required)', '(required)',
      # 混合语言
      '必填/Required', '必选/Required'
    ]
    return any(indicator in line for indicator in required_indicators)
  
  def _extract_checkbox_field(self, line: str, page_num: int) -> Dict[str, Any]:
    """提取复选框字段信息"""
    # 提取字段名称
    field_name = self._extract_field_name(line)
    
    # 提取选项 - 支持多语言
    options = self._extract_checkbox_options(line)
    
    return {
      'name': field_name,
      'type': 'checkbox',
      'value': '',
      'options': options,
      'page': page_num + 1,
      'position': None,
      'required': False
    }
  
  def _extract_checkbox_options(self, line: str) -> List[str]:
    """提取复选框选项，支持多语言"""
    # 简体中文选项
    if '□ 是' in line and '□ 否' in line:
      return ['是', '否']
    elif '□ 同意' in line and '□ 不同意' in line:
      return ['同意', '不同意']
    elif '□ 有' in line and '□ 无' in line:
      return ['有', '无']
    
    # 繁体中文选项
    elif '□ 是' in line and '□ 否' in line:
      return ['是', '否']
    elif '□ 同意' in line and '□ 不同意' in line:
      return ['同意', '不同意']
    elif '□ 有' in line and '□ 無' in line:
      return ['有', '無']
    
    # 英文选项
    elif '□ Yes' in line and '□ No' in line:
      return ['Yes', 'No']
    elif '□ Agree' in line and '□ Disagree' in line:
      return ['Agree', 'Disagree']
    elif '[ ] Yes' in line and '[ ] No' in line:
      return ['Yes', 'No']
    
    # 混合语言选项
    elif '□ 是/否' in line or '□ Yes/No' in line:
      return ['是/Yes', '否/No']
    elif '□ 同意/不同意' in line or '□ Agree/Disagree' in line:
      return ['同意/Agree', '不同意/Disagree']
    
    # 默认选项
    else:
      return ['是', '否']
  
  def _extract_select_field(self, line: str, page_num: int) -> Dict[str, Any]:
    """提取选择框字段信息"""
    field_name = self._extract_field_name(line)
    
    # 提取选项 - 支持多语言
    options = self._extract_select_options(line)
    
    return {
      'name': field_name,
      'type': 'select',
      'value': '',
      'options': options,
      'page': page_num + 1,
      'position': None,
      'required': False
    }
  
  def _extract_select_options(self, line: str) -> List[str]:
    """提取选择框选项，支持多语言"""
    # 简体中文选项
    if '□ 男 □ 女' in line:
      return ['男', '女']
    elif '□ 已婚 □ 未婚' in line:
      return ['已婚', '未婚']
    
    # 繁体中文选项
    elif '□ 男 □ 女' in line:
      return ['男', '女']
    elif '□ 已婚 □ 未婚' in line:
      return ['已婚', '未婚']
    
    # 英文选项
    elif '□ Male □ Female' in line:
      return ['Male', 'Female']
    elif '□ Married □ Single' in line:
      return ['Married', 'Single']
    elif '□ Yes □ No' in line:
      return ['Yes', 'No']
    
    # 混合语言选项
    elif '请选择/Please select' in line or '选择/Select' in line:
      return ['请选择/Please select', '选择/Select']
    
    # 默认选项
    else:
      return ['请选择', 'Please select']
  
  def _extract_radio_field(self, line: str, page_num: int) -> Dict[str, Any]:
    """提取单选按钮字段信息"""
    field_name = self._extract_field_name(line)
    
    # 提取选项 - 支持多语言
    options = self._extract_radio_options(line)
    
    return {
      'name': field_name,
      'type': 'radio',
      'value': '',
      'options': options,
      'page': page_num + 1,
      'position': None,
      'required': False
    }
  
  def _extract_radio_options(self, line: str) -> List[str]:
    """提取单选按钮选项，支持多语言"""
    # 简体中文选项
    if '○ 是 ○ 否' in line or '● 是 ○ 否' in line:
      return ['是', '否']
    
    # 繁体中文选项
    elif '○ 是 ○ 否' in line or '● 是 ○ 否' in line:
      return ['是', '否']
    
    # 英文选项
    elif '○ Yes ○ No' in line or '● Yes ○ No' in line:
      return ['Yes', 'No']
    elif '○ Yes' in line and '○ No' in line:
      return ['Yes', 'No']
    elif '● Yes' in line and '● No' in line:
      return ['Yes', 'No']
    
    # 混合语言选项
    elif '○ 是/Yes' in line or '○ 否/No' in line:
      return ['是/Yes', '否/No']
    
    # 默认选项
    else:
      return ['选项1', '选项2']
  
  def _extract_text_field(self, line: str, page_num: int) -> Optional[Dict[str, Any]]:
    """提取文本字段信息"""
    parts = line.split(':', 1)
    if len(parts) == 2:
      field_name = parts[0].strip()
      field_value = parts[1].strip()
      
      if field_name and not field_name.isdigit():
        return {
          'name': field_name,
          'type': 'text',
          'value': field_value,
          'page': page_num + 1,
          'position': None,
          'required': self._is_required_field(line)
        }
    
    return None
  
  def _extract_required_field(self, line: str, page_num: int) -> Dict[str, Any]:
    """提取必填字段信息"""
    field_name = self._extract_field_name(line)
    
    return {
      'name': field_name,
      'type': 'text',
      'value': '',
      'page': page_num + 1,
      'position': None,
      'required': True
    }
  
  def _extract_field_name(self, line: str) -> str:
    """从文本行中提取字段名称，支持多语言"""
    # 移除常见的字段标记 - 支持多语言
    line = self._remove_field_markers(line)
    
    # 提取冒号前的部分作为字段名
    if ':' in line:
      return line.split(':', 1)[0].strip()
    
    # 提取方括号前的部分
    if '[' in line:
      return line.split('[', 1)[0].strip()
    
    # 提取圆括号前的部分
    if '(' in line:
      return line.split('(', 1)[0].strip()
    
    return line.strip()
  
  def _remove_field_markers(self, line: str) -> str:
    """移除字段标记，支持多语言"""
    # 通用符号
    line = line.replace('*', '')
    
    # 简体中文标记
    line = line.replace('（必填）', '').replace('(必填)', '')
    line = line.replace('（必选）', '').replace('(必选)', '')
    
    # 繁体中文标记
    line = line.replace('（必填）', '').replace('(必填)', '')
    line = line.replace('（必選）', '').replace('(必選)', '')
    
    # 英文标记
    line = line.replace('(Required)', '').replace('(required)', '')
    line = line.replace('(Mandatory)', '').replace('(mandatory)', '')
    
    # 混合语言标记
    line = line.replace('（必填/Required）', '').replace('(必填/Required)', '')
    line = line.replace('（必选/Required）', '').replace('(必选/Required)', '')
    
    return line
  
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
      # 读取原始PDF
      content = await file.read()
      
      # 创建PDF读取器和写入器
      pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
      pdf_writer = PyPDF2.PdfWriter()
      
      # 创建字段值映射，支持新格式
      field_values = {}
      for field in fields:
        field_name = field.get('name', '')
        if field_name:
          # 新格式：包含类型和值的完整字段信息
          field_values[field_name] = field
      
      # 处理每一页
      for page_num, page in enumerate(pdf_reader.pages):
        # 尝试填充表单字段
        if '/Annots' in page:
          annotations = page['/Annots']
          if annotations:
            # 获取 annotations 的实际值
            annotations_obj = annotations.get_object()
            if isinstance(annotations_obj, list):
              annotation_list = annotations_obj
            else:
              annotation_list = [annotations_obj]
            
            for annotation in annotation_list:
              try:
                if annotation.get('/Subtype') == '/Widget':  # type: ignore
                  # 跳过按钮类型的字段
                  field_type = self._get_actual_field_type(annotation.get_object())
                  if field_type == 'button':
                    field_name = annotation.get_object().get('/T', 'Unknown')
                    if isinstance(field_name, bytes):
                      field_name = field_name.decode('utf-8', errors='ignore')
                    logger.debug(f'跳过按钮字段填充: {field_name}')
                  else:
                    self._fill_field(annotation, field_values)
              except (KeyError, AttributeError):
                continue
        
        # 添加页面到写入器
        pdf_writer.add_page(page)
      
      # 生成输出文件名
      output_filename = f'filled_{uuid.uuid4().hex}_{file.filename}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 写入填充后的PDF
      with open(output_path, 'wb') as output_file:
        pdf_writer.write(output_file)
      
      logger.info(f'PDF表单填充完成: {output_path}')
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
      # 读取原始PDF
      with open(file_path, 'rb') as f:
        content = f.read()
      
      # 创建PDF读取器和写入器
      pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
      pdf_writer = PyPDF2.PdfWriter()
      
      # 创建字段值映射
      field_values = {}
      for field in fields:
        field_name = field.get('name', '')
        if field_name:
          field_values[field_name] = field.get('value', '')
      
      # 添加所有页面到写入器
      for page in pdf_reader.pages:
        pdf_writer.add_page(page)
      
      # 处理AcroForm字段
      if pdf_reader.trailer and '/Root' in pdf_reader.trailer:
        root = pdf_reader.trailer['/Root'].get_object()
        if root and '/AcroForm' in root:
          acro_form = root['/AcroForm'].get_object()
          if '/Fields' in acro_form:
            form_fields = acro_form['/Fields']
            logger.info(f'找到 {len(form_fields)} 个AcroForm字段')
            
            # 创建新的字段列表
            new_fields = []
            
            for field_ref in form_fields:
              field_obj = field_ref.get_object()
              field_name = field_obj.get('/T', 'Unknown')
              if isinstance(field_name, bytes):
                field_name = field_name.decode('utf-8', errors='ignore')
              
              # 检查是否是按钮类型，如果是则跳过
              actual_field_type = self._get_actual_field_type(field_obj)
              if actual_field_type == 'button':
                logger.debug(f'跳过按钮字段: {field_name}')
                new_fields.append(field_ref)
                continue
              
              # 如果字段需要填充
              if field_name in field_values:
                value = field_values[field_name]
                logger.info(f'填充AcroForm字段: {field_name} = {value}')
                
                # 创建字段对象的副本
                new_field_obj = PyPDF2.generic.DictionaryObject()
                
                # 复制原始字段的所有属性
                for key, val in field_obj.items():
                  new_field_obj[key] = val
                
                # 根据字段类型设置值
                if actual_field_type == 'checkbox':
                  self._fill_checkbox_field(new_field_obj, value)
                elif actual_field_type == 'radio':
                  self._fill_radio_field(new_field_obj, value)
                elif actual_field_type == 'select':
                  self._fill_select_field(new_field_obj, value)
                else:  # 文本字段
                  self._fill_text_field(new_field_obj, value)
                
                # 将新字段对象添加到写入器
                new_field_ref = pdf_writer._add_object(new_field_obj)
                new_fields.append(new_field_ref)
              else:
                # 不需要填充的字段，直接添加
                new_fields.append(field_ref)
            
            # 创建新的AcroForm
            new_acro_form = PyPDF2.generic.DictionaryObject()
            for key, val in acro_form.items():
              if key == '/Fields':
                # 创建新的字段数组
                new_fields_array = PyPDF2.generic.ArrayObject()
                for field_ref in new_fields:
                  new_fields_array.append(field_ref)
                new_acro_form[key] = new_fields_array
              else:
                new_acro_form[key] = val
            
            # 设置AcroForm到写入器
            pdf_writer._root_object[PyPDF2.generic.NameObject('/AcroForm')] = new_acro_form
            logger.info('AcroForm已添加到写入器')
      
      # 生成输出文件名
      original_filename = os.path.basename(file_path)
      output_filename = f'filled_{uuid.uuid4().hex}_{original_filename}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 写入填充后的PDF
      with open(output_path, 'wb') as output_file:
        pdf_writer.write(output_file)
      
      logger.info(f'PDF表单填充完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'填充PDF表单失败: {str(e)}')
      raise Exception(f'填充PDF表单失败: {str(e)}')
  
  def _fill_field(self, annotation, field_values: Dict[str, Any]):
    """
    填充单个字段，支持多种字段类型
    
    Args:
      annotation: PDF注释对象
      field_values: 字段值映射
    """
    try:
      obj = annotation.get_object()
      
      # 获取字段名称
      field_name = obj.get('/T', '')
      if isinstance(field_name, bytes):
        field_name = field_name.decode('utf-8', errors='ignore')
      
      logger.debug(f'尝试填充字段: {field_name}')
      logger.debug(f'可用字段: {list(field_values.keys())}')
      
      # 如果字段名在值映射中，则填充值
      if field_name in field_values:
        field_data = field_values[field_name]
        logger.debug(f'找到字段数据: {field_data}')
        
        # 处理不同类型的字段数据
        if isinstance(field_data, dict):
          # 新格式：包含类型和值的字典
          field_type = field_data.get('type', 'text')
          value = field_data.get('value', '')
        else:
          # 旧格式：直接是值字符串
          field_type = 'text'
          value = str(field_data)
        
        # 获取字段的实际类型
        actual_field_type = self._get_actual_field_type(obj)
        logger.info(f'字段 {field_name}: 期望类型={field_type}, 实际类型={actual_field_type}, 值={value}')
        
        # 根据实际字段类型设置值
        if actual_field_type == 'checkbox':
          self._fill_checkbox_field(obj, value)
        elif actual_field_type == 'radio':
          self._fill_radio_field(obj, value)
        elif actual_field_type == 'select':
          self._fill_select_field(obj, value)
        elif actual_field_type == 'button':
          self._fill_button_field(obj, 'button', value)
        else:  # 文本字段
          self._fill_text_field(obj, value)
        
        # 设置字段为已填充
        obj[PyPDF2.generic.NameObject('/Ff')] = PyPDF2.generic.NumberObject(1)  # type: ignore
        logger.info(f'字段 {field_name} 填充完成')
      else:
        logger.warning(f'字段 {field_name} 不在填充数据中')
        
    except Exception as e:
      logger.error(f'填充字段 {field_name} 失败: {str(e)}')
        
    except Exception as e:
      logger.warning(f'填充字段 {field_name} 失败: {str(e)}')
  
  def _get_actual_field_type(self, obj) -> str:
    """获取字段的实际类型"""
    if '/FT' in obj:
      ft = obj['/FT']
      if ft == '/Btn':
        # 检查按钮类型
        if '/Ff' in obj:
          ff = obj['/Ff']
          if ff & 32768:  # Radio button flag
            return 'radio'
          elif ff & 65536:  # Push button flag
            return 'button'
          else:
            return 'checkbox'
        else:
          return 'checkbox'
      elif ft == '/Ch':
        # 检查是否为下拉选择框
        if '/Ff' in obj:
          ff = obj['/Ff']
          if ff & 131072:  # Combo box flag
            return 'select'
          else:
            return 'listbox'
        else:
          return 'select'
      elif ft == '/Tx':
        return 'text'
    
    return 'text'
  
  def _fill_checkbox_field(self, obj, value: str):
    """填充复选框字段"""
    try:
      if self._is_positive_value(value):
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Yes')  # type: ignore
      else:
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Off')  # type: ignore
    except Exception as e:
      logger.warning(f'填充复选框字段失败: {str(e)}')
  
  def _fill_radio_field(self, obj, value: str):
    """填充单选按钮字段"""
    try:
      logger.debug(f'填充单选按钮字段: {value}')
      
      # 检查是否有选项
      if '/Opt' in obj:
        options = obj['/Opt']
        if isinstance(options, list):
          # 检查值是否在选项中
          if value in options:
            obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
            logger.debug(f'设置单选按钮值为: {value}')
          else:
            logger.warning(f'值 {value} 不在选项 {options} 中')
        else:
          # 直接设置值
          obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      else:
        # 没有选项，直接设置值
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      
      logger.debug(f'单选按钮字段填充完成')
    except Exception as e:
      logger.warning(f'填充单选按钮字段失败: {str(e)}')
  
  def _fill_select_field(self, obj, value: str):
    """填充选择框字段"""
    try:
      obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
    except Exception as e:
      logger.warning(f'填充选择框字段失败: {str(e)}')
  
  def _fill_button_field(self, obj, field_type: str, value: str):
    """填充按钮类型字段（复选框、单选按钮、普通按钮），支持多语言"""
    try:
      if field_type == 'checkbox':
        # 复选框：根据布尔值设置 - 支持多语言
        if self._is_positive_value(value):
          obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Yes')  # type: ignore
        else:
          obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Off')  # type: ignore
      elif field_type == 'radio':
        # 单选按钮：设置选中的值
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      elif field_type == 'button':
        # 普通按钮：通常不需要设置值，但可以设置按钮文本
        if value:
          # 更新按钮外观文本
          if '/MK' not in obj:
            obj[PyPDF2.generic.NameObject('/MK')] = PyPDF2.generic.DictionaryObject()  # type: ignore
          obj['/MK'][PyPDF2.generic.NameObject('/CA')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      else:
        # 默认按钮处理
        if self._is_positive_value(value):
          obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Yes')  # type: ignore
        else:
          obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.NameObject('/Off')  # type: ignore
    except Exception as e:
      logger.warning(f'填充按钮字段失败: {str(e)}')
  
  def _is_positive_value(self, value: str) -> bool:
    """判断是否为正值，支持多语言"""
    positive_values = [
      # 英文
      'true', 'yes', '1', 'on', 'positive',
      # 简体中文
      '是', '同意', '有', '对', '正确',
      # 繁体中文
      '是', '同意', '有', '對', '正確',
      # 混合语言
      '是/Yes', '同意/Agree'
    ]
    return value.lower() in positive_values
  
  def _fill_choice_field(self, obj, field_type: str, value: str):
    """填充选择框字段"""
    try:
      if field_type == 'select':
        # 选择框：设置选中的选项
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      else:
        # 默认选择框处理
        obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
    except Exception as e:
      logger.warning(f'填充选择框字段失败: {str(e)}')
  
  def _fill_text_field(self, obj, value: str):
    """填充文本字段"""
    try:
      logger.debug(f'设置文本字段值: {value}')
      obj[PyPDF2.generic.NameObject('/V')] = PyPDF2.generic.createStringObject(value)  # type: ignore
      logger.debug(f'文本字段值设置完成')
    except Exception as e:
      logger.warning(f'填充文本字段失败: {str(e)}')
  
  async def create_sample_form(self) -> str:
    """
    创建一个示例PDF表单用于测试
    
    Returns:
      示例PDF文件路径
    """
    try:
      # 创建临时文件
      temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
      temp_path = temp_file.name
      temp_file.close()
      
      # 创建PDF
      c = canvas.Canvas(temp_path, pagesize=letter)
      width, height = letter
      
      # 添加标题
      c.setFont('Helvetica-Bold', 16)
      c.drawString(50, height - 50, 'PDF Form Example')
      
      # 添加说明文字
      c.setFont('Helvetica', 10)
      c.drawString(50, height - 80, 'This is a user-fillable PDF form, created with OpenOffice (version 3.4.0).')
      c.drawString(50, height - 95, 'Important fields are marked yellow.')
      
      # 添加表单字段
      c.setFont('Helvetica', 12)
      y_position = height - 130
      
      # 文本字段
      text_fields = [
        ('Given Name', 50, y_position),
        ('Family Name', 50, y_position - 30),
        ('Address 1', 50, y_position - 60),
        ('House nr', 250, y_position - 60),
        ('Address 2', 50, y_position - 90),
        ('Postcode', 50, y_position - 120),
        ('City', 150, y_position - 120),
        ('Country', 50, y_position - 150),
        ('Gender', 50, y_position - 180),
        ('Height (cm)', 50, y_position - 210)
      ]
      
      for label, x, y in text_fields:
        c.drawString(x, y, f'{label}:')
        # 绘制文本框
        c.rect(x + 80, y - 15, 150, 20)
      
      # 复选框
      c.drawString(50, y_position - 240, 'Driving License:')
      c.rect(150, y_position - 255, 15, 15)  # 复选框
      
      c.save()
      
      # 移动到输出目录
      output_filename = f'sample_form_{uuid.uuid4().hex}.pdf'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 复制文件
      with open(temp_path, 'rb') as src, open(output_path, 'wb') as dst:
        dst.write(src.read())
      
      # 删除临时文件
      os.unlink(temp_path)
      
      logger.info(f'创建示例表单: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'创建示例表单失败: {str(e)}')
      raise Exception(f'创建示例表单失败: {str(e)}') 