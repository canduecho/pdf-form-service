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
from datetime import datetime

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
      
      # 获取字段值和子字段信息
      field_value = field_obj.get('/V', '')
      is_subfield = False
      subfield_info = None
      
      # 如果父字段没有值，但有子字段，尝试从子字段获取值
      if not field_value and '/Kids' in field_obj:
        kids = field_obj['/Kids']
        if kids and len(kids) > 0:
          is_subfield = True
          subfield_info = {
            'has_kids': True,
            'kids_count': len(kids),
            'parent_field': field_name
          }
          # 获取第一个子字段的值
          try:
            kid_obj = kids[0].get_object()
            kid_value = kid_obj.get('/V', '')
            if kid_value:
              field_value = kid_value
              subfield_info['kid_value_source'] = 0  # 从第0个子字段获取值
              logger.debug(f'从子字段获取到值: {field_name} = {field_value}')
          except Exception as e:
            logger.warning(f'读取子字段值失败: {str(e)}')
      
      if isinstance(field_value, bytes):
        field_value = field_value.decode('utf-8', errors='ignore')
      # 处理复选框和单选按钮的值：去掉开头的 "/"
      if field_type in ['checkbox', 'radio'] and isinstance(field_value, str) and field_value.startswith('/'):
        field_value = field_value[1:]
      # 处理复选框和单选按钮的值：将 "On" 转换为 "Yes"
      if field_type in ['checkbox', 'radio'] and isinstance(field_value, str) and field_value == 'On':
        field_value = 'Yes'
      
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
      options = None
      if field_type in ['select', 'radio', 'checkbox'] and '/Opt' in field_obj:
        opt = field_obj['/Opt']
        if isinstance(opt, list):
          options = []
          if field_type in ['select', 'listbox']:
            # 下拉框/列表框：text 和 value 都是选项文本
            for option in opt:
              text = option.decode('utf-8', errors='ignore') if isinstance(option, bytes) else str(option)
              options.append({'text': text, 'value': text})
          elif field_type == 'radio':
            # 单选组：text 是选项文本，value 是索引
            for idx, option in enumerate(opt):
              text = option.decode('utf-8', errors='ignore') if isinstance(option, bytes) else str(option)
              options.append({'text': text, 'value': str(idx)})
          elif field_type == 'checkbox':
            # 复选框：固定选项
            options = [
              {'text': '选中', 'value': 'Yes'},
              {'text': '未选中', 'value': 'Off'}
            ]
      
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
        'is_subfield': is_subfield,  # 添加子字段标识
        'subfield_info': subfield_info,  # 添加子字段详细信息
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
      # 处理复选框和单选按钮的值：去掉开头的 "/"
      if field_type in ['checkbox', 'radio'] and isinstance(field_value, str) and field_value.startswith('/'):
        field_value = field_value[1:]
      # 处理复选框和单选按钮的值：将 "On" 转换为 "Yes"
      if field_type in ['checkbox', 'radio'] and isinstance(field_value, str) and field_value == 'On':
        field_value = 'Yes'
      
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
      options = None
      if field_type in ['select', 'radio', 'checkbox'] and '/Opt' in obj:
        opt = obj['/Opt']
        if isinstance(opt, list):
          options = []
          if field_type in ['select', 'listbox']:
            # 下拉框/列表框：text 和 value 都是选项文本
            for option in opt:
              text = option.decode('utf-8', errors='ignore') if isinstance(option, bytes) else str(option)
              options.append({'text': text, 'value': text})
          elif field_type == 'radio':
            # 单选组：text 是选项文本，value 是索引
            for idx, option in enumerate(opt):
              text = option.decode('utf-8', errors='ignore') if isinstance(option, bytes) else str(option)
              options.append({'text': text, 'value': str(idx)})
          elif field_type == 'checkbox':
            # 复选框：固定选项
            options = [
              {'text': '选中', 'value': 'Yes'},
              {'text': '未选中', 'value': 'Off'}
            ]
      
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
        'is_subfield': False,  # 页面注释通常不是子字段
        'subfield_info': None,
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
      '请选择/Please select', '选择/Select',
      # 特殊字段识别：Language字段的选项列表模式
      'English German French Italian'
    ]
    
    # 特殊处理：检查是否为Language字段的选项列表
    if 'English' in line and 'German' in line and 'French' in line and 'Italian' in line:
      return True
    
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
    
    # 特殊处理：Language字段应该是listbox类型
    field_type = 'listbox' if field_name.lower() == 'language' else 'select'
    
    return {
      'name': field_name,
      'type': field_type,
      'value': '',
      'options': options,
      'page': page_num + 1,
      'position': None,
      'required': False
    }
  
  def _extract_select_options(self, line: str) -> List[str]:
    """提取选择框选项，支持多语言"""
    # 特殊处理：Language字段选项
    if 'English' in line and 'German' in line and 'French' in line and 'Italian' in line:
      return ['English', 'German', 'French', 'Italian']
    
    # 简体中文选项
    elif '□ 男 □ 女' in line:
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

  async def fill_form(self, file: UploadFile, fields: List[Dict[str, Any]], strict_validation: bool = True) -> str:
    """
    增强的PDF表单填充，支持多种字段类型和子字段处理
    
    支持的字段类型：
    - text: 文本字段
    - checkbox: 复选框 (值: "Yes"/"Off", "True"/"False", "1"/"0")
    - radio: 单选按钮 (值: 选项文本或索引)
    - select/dropdown: 下拉选择框 (值: 选项文本)
    - combobox: 组合框 (值: 选项文本或自定义文本)
    
    特殊功能：
    - 自动识别子字段并进行特殊处理
    - 智能字段类型转换
    
    Args:
      file: 原始PDF文件 (UploadFile对象)
      fields: 字段数据列表，格式: [{"name": "字段名", "value": "值", "type": "类型"}]
      strict_validation: 是否严格验证字段选项，默认为 True
      
    Returns:
      填充后的PDF文件路径
    """
    try:
      # 步骤1: 先解析PDF表单结构，识别子字段
      logger.info('步骤1: 解析PDF表单结构，识别子字段...')
      
      # 创建一个临时的文件副本用于解析
      import tempfile
      import shutil
      
      temp_parse_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
      content = await file.read()
      temp_parse_file.write(content)
      temp_parse_file.close()
      
      # 重新创建 UploadFile 对象用于解析
      class TempUploadFile:
        def __init__(self, filepath, filename):
          self.filepath = filepath
          self.filename = filename
          
        async def read(self):
          with open(self.filepath, 'rb') as f:
            return f.read()
      
      parse_file = TempUploadFile(temp_parse_file.name, file.filename)
      parsed_fields = await self.parse_form_fields(parse_file)
      
      # 创建字段结构映射
      field_structure = {}
      subfields = set()
      
      for parsed_field in parsed_fields:
        field_name = parsed_field.get('name', '')
        is_subfield = parsed_field.get('is_subfield', False)
        subfield_info = parsed_field.get('subfield_info')
        
        field_structure[field_name] = {
          'is_subfield': is_subfield,
          'subfield_info': subfield_info,
          'type': parsed_field.get('type', 'text'),
          'current_value': parsed_field.get('value', '')
        }
        
        if is_subfield:
          subfields.add(field_name)
          logger.info(f'识别到子字段: {field_name}')
      
      logger.info(f'解析完成，识别到 {len(subfields)} 个子字段: {list(subfields)}')
      
      # 步骤2: 处理字段类型和识别需要特殊处理的字段
      logger.info('步骤2: 处理字段值和类型...')
      
      enhanced_fields = []
      subfield_special_handling = {}
      
      for field in fields:
        field_name = field.get('name', '')
        field_value = field.get('value', '')
        # type get from field_structure
        field_type = field_structure.get(field_name, {}).get('type', 'text')  # 默认为文本类型
        
        if field_name:
          # 根据字段类型处理值
          processed_value = self._process_field_value(field_value, field_type, field_name)
          
          # 检查是否为子字段
          if field_name in subfields:
            logger.info(f'字段 {field_name} 是子字段，需要特殊处理')
            subfield_special_handling[field_name] = {
              'original_value': field_value,
              'processed_value': processed_value,
              'structure': field_structure.get(field_name, {})
            }
          
          enhanced_fields.append({
            'name': field_name,
            'value': processed_value
          })
          logger.debug(f'处理字段 {field_name} (类型: {field_type}, 子字段: {field_name in subfields}): "{field_value}" -> "{processed_value}"')
      
      # 步骤3: 使用改进的子字段填充逻辑
      if subfield_special_handling:
        logger.info(f'步骤3: 对 {len(subfield_special_handling)} 个子字段进行特殊处理...')
        # 优先使用 PyMuPDF 方法（最强大）
        try:
          output_path = await self._fill_subfields_pymupdf(
            temp_parse_file.name, 
            enhanced_fields, 
            subfield_special_handling,
            strict_validation
          )
        except Exception as e:
          logger.warning(f'PyMuPDF 子字段填充失败，尝试直接操作方法: {str(e)}')
          # 尝试直接PDF操作方法
          try:
            output_path = await self._fill_subfields_direct(
              temp_parse_file.name, 
              enhanced_fields, 
              subfield_special_handling,
              strict_validation
            )
          except Exception as e2:
            logger.warning(f'直接子字段填充失败，尝试改进方法: {str(e2)}')
            # 尝试改进方法
            try:
              output_path = await self._fill_subfields_improved(
                temp_parse_file.name, 
                enhanced_fields, 
                subfield_special_handling,
                strict_validation
              )
            except Exception as e3:
              logger.warning(f'所有子字段填充方法都失败，回退到标准方法: {str(e3)}')
              # 最后回退到标准方法
              from app.services.pdf_service_fillpdf import PDFServiceFillPDF
              pdf_service_fillpdf = PDFServiceFillPDF()
              fill_file = TempUploadFile(temp_parse_file.name, file.filename)
              output_path = await pdf_service_fillpdf.fill_form(fill_file, enhanced_fields, strict_validation)
      else:
        logger.info('步骤3: 使用标准填充方法（无子字段）...')
        # 使用标准填充
        from app.services.pdf_service_fillpdf import PDFServiceFillPDF
        pdf_service_fillpdf = PDFServiceFillPDF()
        
        # 重新创建 UploadFile
        fill_file = TempUploadFile(temp_parse_file.name, file.filename)
        output_path = await pdf_service_fillpdf.fill_form(fill_file, enhanced_fields, strict_validation)
      
      # 清理临时文件
      os.unlink(temp_parse_file.name)
      
      logger.info(f'使用增强方法填充PDF表单完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'增强填充PDF表单失败: {str(e)}')
      raise Exception(f'增强填充PDF表单失败: {str(e)}')
  
  def _process_field_value(self, value: str, field_type: str, field_name: str) -> str:
    """
    根据字段类型处理字段值
    
    Args:
      value: 原始值
      field_type: 字段类型
      field_name: 字段名（用于调试）
      
    Returns:
      处理后的值
    """
    if not value:
      return ''
    
    value_str = str(value).strip()
    
    # 处理不同字段类型
    if field_type.lower() == 'checkbox':
      # 复选框：转换为标准值
      if value_str.lower() in ['true', '1', 'yes', 'on', 'checked', '是', '选中']:
        return 'Yes'
      elif value_str.lower() in ['false', '0', 'no', 'off', 'unchecked', '否', '未选中']:
        return 'Off'
      else:
        # 保持原值，让fillpdf处理
        return value_str
    
    elif field_type.lower() in ['radio', 'radiobutton']:
      # 单选按钮：保持原值，通常是选项文本或索引
      return value_str
    
    elif field_type.lower() in ['select', 'dropdown', 'listbox']:
      # 下拉选择框：保持原值，应该是选项文本
      return value_str
    
    elif field_type.lower() in ['combobox', 'combo']:
      # 组合框：可以是选项文本或自定义文本
      return value_str
    
    elif field_type.lower() in ['text', 'textfield']:
      # 文本字段：保持原值
      return value_str
    
    else:
      # 未知类型：保持原值
      logger.debug(f'未知字段类型 {field_type} for {field_name}，保持原值')
      return value_str

  async def _fill_subfields_improved(self, input_file_path: str, enhanced_fields: List[Dict[str, Any]], 
                                     subfield_handling: Dict[str, Any], strict_validation: bool = True) -> str:
    """
    改进的子字段填充方法：使用 fillpdf 但预处理数据
    
    这个方法尝试通过预处理来让 fillpdf 能够处理子字段
    """
    try:
      from app.services.pdf_service_fillpdf import PDFServiceFillPDF
      
      logger.info('使用改进的子字段填充方法...')
      
      # 创建一个特殊的字段映射，针对子字段使用多种名称变体
      enhanced_fields_with_variants = []
      
      for field in enhanced_fields:
        field_name = field['name']
        field_value = field['value']
        
        # 添加原始字段
        enhanced_fields_with_variants.append({
          'name': field_name,
          'value': field_value
        })
        
        # 如果是子字段，添加各种可能的名称变体
        if field_name in subfield_handling:
          logger.info(f'为子字段 {field_name} 生成名称变体...')
          
          # 生成常见的子字段名称变体
          variants = [
            field_name,
            field_name.replace(' ', '_'),
            field_name.replace(' ', ''),
            field_name.replace(' ', '.'),
            field_name.upper(),
            field_name.lower(),
            f'{field_name}_0',  # 子字段索引
            f'{field_name}[0]', # 数组形式
            f'{field_name}.0',  # 点号形式
          ]
          
          for variant in variants:
            if variant != field_name:  # 避免重复
              enhanced_fields_with_variants.append({
                'name': variant,
                'value': field_value
              })
              logger.debug(f'添加子字段变体: {variant} = {field_value}')
      
      logger.info(f'原始字段数: {len(enhanced_fields)}, 包含变体后: {len(enhanced_fields_with_variants)}')
      
      # 使用 PDFServiceFillPDF 填充
      pdf_service_fillpdf = PDFServiceFillPDF()
      
      class TempUploadFile:
        def __init__(self, filepath, filename):
          self.filepath = filepath
          self.filename = os.path.basename(filename)
          
        async def read(self):
          with open(self.filepath, 'rb') as f:
            return f.read()
      
      fill_file = TempUploadFile(input_file_path, input_file_path)
      output_path = await pdf_service_fillpdf.fill_form(fill_file, enhanced_fields_with_variants, strict_validation)
      
      logger.info(f'改进子字段填充完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'改进子字段填充失败: {str(e)}')
      raise e


  async def _fill_subfields_pymupdf(self, input_file_path: str, enhanced_fields: List[Dict[str, Any]], 
                                     subfield_handling: Dict[str, Any], strict_validation: bool = True) -> str:
    """
    使用 PyMuPDF (fitz) 填充子字段
    
    PyMuPDF 在处理复杂PDF表单结构方面更强大
    """
    try:
      import fitz  # PyMuPDF
      
      logger.info('使用 PyMuPDF 填充子字段...')
      
      # 创建字段值映射
      field_values = {}
      for field in enhanced_fields:
        field_values[field['name']] = field['value']
      
      # 打开PDF文档
      doc = fitz.open(input_file_path)
      
      fill_count = 0
      total_attempts = 0
      
      # 遍历所有页面
      for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 获取页面上的表单字段
        for widget in page.widgets():
          field_name = widget.field_name
          total_attempts += 1
          
          # 直接匹配
          if field_name in field_values:
            new_value = field_values[field_name]
            logger.info(f'直接匹配填充字段: {field_name} -> {new_value}')
            
            try:
              # 设置字段值
              widget.field_value = str(new_value)
              widget.update()
              fill_count += 1
              
              # 特别处理子字段
              if field_name in subfield_handling:
                logger.info(f'✅ 成功填充子字段: {field_name} = {new_value}')
              else:
                logger.debug(f'✅ 成功填充字段: {field_name} = {new_value}')
                
            except Exception as e:
              logger.warning(f'填充字段 {field_name} 失败: {str(e)}')
          
          else:
            # 智能匹配：检查是否有包含关系的字段
            for target_field_name, target_value in field_values.items():
              if target_field_name in subfield_handling:  # 只对子字段进行智能匹配
                # 检查字段名包含关系
                if (target_field_name in field_name or 
                    field_name.replace('.', '').replace(' ', '') == target_field_name.replace(' ', '') or
                    target_field_name in field_name.replace('.', '')):
                  
                  logger.info(f'智能匹配填充子字段: "{field_name}" <- 目标: "{target_field_name}" -> {target_value}')
                  
                  try:
                    # 设置字段值
                    widget.field_value = str(target_value)
                    widget.update()
                    fill_count += 1
                    logger.info(f'✅ 智能匹配成功填充: {field_name} = {target_value}')
                    break  # 找到匹配后跳出
                  except Exception as e:
                    logger.warning(f'智能匹配填充字段 {field_name} 失败: {str(e)}')
      
      logger.info(f'PyMuPDF 处理完成: 尝试 {total_attempts} 个字段，成功填充 {fill_count} 个')
      
      # 生成输出文件
      output_filename = f'filled_pymupdf_{uuid.uuid4().hex}_{os.path.basename(input_file_path)}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 保存PDF
      doc.save(output_path)
      doc.close()
      
      logger.info(f'PyMuPDF 子字段填充完成: {output_path}')
      return output_path
      
    except ImportError:
      logger.error('PyMuPDF 库未安装，无法使用此方法')
      raise Exception('PyMuPDF 库未安装')
    except Exception as e:
      logger.error(f'PyMuPDF 子字段填充失败: {str(e)}')
      raise e

  async def _fill_subfields_direct(self, input_file_path: str, enhanced_fields: List[Dict[str, Any]], 
                                   subfield_handling: Dict[str, Any], strict_validation: bool = True) -> str:
    """
    直接操作PDF对象来填充子字段（低级方法）
    """
    try:
      import PyPDF2
      from PyPDF2.generic import TextStringObject
      import shutil
      
      logger.info('使用直接PDF操作填充子字段...')
      
      # 创建输出文件
      output_filename = f'filled_direct_{uuid.uuid4().hex}_{os.path.basename(input_file_path)}'
      output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
      
      # 先复制原文件
      shutil.copy2(input_file_path, output_path)
      
      # 创建字段值映射
      field_values = {}
      for field in enhanced_fields:
        field_values[field['name']] = field['value']
      
      # 直接修改PDF文件
      with open(output_path, 'r+b') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # 处理表单字段
        if pdf_reader.trailer and '/Root' in pdf_reader.trailer:
          root = pdf_reader.trailer['/Root'].get_object()
          if root and '/AcroForm' in root:
            acro_form = root['/AcroForm'].get_object()
            if acro_form and '/Fields' in acro_form:
              form_fields = acro_form['/Fields']
              
              fill_count = 0
              for field_ref in form_fields:
                field_obj = field_ref.get_object()
                field_name = field_obj.get('/T', '')
                if isinstance(field_name, bytes):
                  field_name = field_name.decode('utf-8', errors='ignore')
                
                # 检查是否需要填充这个字段
                if field_name in field_values:
                  new_value = field_values[field_name]
                  
                  # 特殊处理子字段
                  if field_name in subfield_handling:
                    logger.info(f'直接修改子字段: {field_name} -> {new_value}')
                    
                    # 尝试填充子字段
                    if '/Kids' in field_obj:
                      kids = field_obj['/Kids']
                      if kids and len(kids) > 0:
                        for i, kid_ref in enumerate(kids):
                          try:
                            kid_obj = kid_ref.get_object()
                            # 直接修改子字段对象的值
                            kid_obj['/V'] = TextStringObject(str(new_value))
                            logger.debug(f'直接修改子字段 {field_name}[{i}] = {new_value}')
                            fill_count += 1
                          except Exception as e:
                            logger.debug(f'修改子字段 {field_name}[{i}] 失败: {e}')
                    
                    # 同时尝试修改父字段
                    try:
                      field_obj['/V'] = TextStringObject(str(new_value))
                      logger.debug(f'同时修改父字段 {field_name} = {new_value}')
                    except Exception as e:
                      logger.debug(f'修改父字段 {field_name} 失败: {e}')
                      
                  else:
                    # 标准字段处理
                    try:
                      field_obj['/V'] = TextStringObject(str(new_value))
                      logger.debug(f'填充标准字段: {field_name} = {new_value}')
                      fill_count += 1
                    except Exception as e:
                      logger.warning(f'填充标准字段失败 {field_name}: {str(e)}')
              
              logger.info(f'直接修改完成，修改了 {fill_count} 个字段/子字段')
              
              # 重新写入文件
              pdf_file.seek(0)
              pdf_writer = PyPDF2.PdfWriter()
              
              # 复制所有页面（保持修改）
              for page in pdf_reader.pages:
                pdf_writer.add_page(page)
              
              # 清空文件并写入
              pdf_file.truncate()
              pdf_writer.write(pdf_file)
      
      logger.info(f'直接子字段填充完成: {output_path}')
      return output_path
      
    except Exception as e:
      logger.error(f'直接子字段填充失败: {str(e)}')
      raise e
