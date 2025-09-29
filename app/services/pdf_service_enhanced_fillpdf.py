"""
增强版fillpdf PDF表单处理服务
使用自定义增强的fillpdf库，支持特殊子字段结构
"""

import os
import uuid
from typing import List, Dict, Any
from fastapi import UploadFile
from loguru import logger

from app.utils.config import settings
from app.custom_fillpdf import get_form_fields, write_fillable_pdf


class PDFServiceEnhancedFillPDF:
    """增强版fillpdf PDF表单处理服务"""
    

    def __init__(self):
        self.name = "Enhanced FillPDF Service v3"
        self._field_positions_cache = {}  # 缓存字段位置信息

        logger.info(f'初始化 {self.name}')
    
    async def parse_form_fields(self, file: UploadFile) -> List[Dict[str, Any]]:
        """
        解析PDF表单字段（增强版，支持子字段）
        
        Args:
            file: 上传的PDF文件
            
        Returns:
            字段列表
        """
        try:
            # 保存临时文件
            temp_input_path = os.path.join(settings.TEMP_DIR, f'parse_{uuid.uuid4().hex}_{file.filename}')
            
            # 读取文件内容
            content = await file.read()
            
            # 检查文件内容是否为空
            if not content:
                raise Exception('上传的文件为空')
            
            with open(temp_input_path, 'wb') as f:
                f.write(content)
            
            # 使用增强版fillpdf解析字段
            fillpdf_fields = get_form_fields(temp_input_path)
            
            # 提取增强信息
            enhanced_info = fillpdf_fields.pop('_enhanced_info', {})
            
            logger.info(f'增强fillpdf库解析到 {len(fillpdf_fields)} 个字段: {list(fillpdf_fields.keys())}')
            
            # 转换为标准格式，支持多种字段类型
            fields = []
            for field_name, field_value in fillpdf_fields.items():
                # 默认字段信息
                field_type = 'text'
                field_options = []
                is_subfield = False
                subfield_info = None
                
                # 使用增强信息来确定字段类型  
                if field_name in enhanced_info:
                    field_info = enhanced_info[field_name]
                    ft = field_info.get('type')
                    has_options = field_info.get('has_options', False)
                    has_kids = field_info.get('has_kids', False)
                    options = field_info.get('options', [])
                    flags = field_info.get('flags')
                    
                    # 使用增强信息中的实际值（而不是fillpdf返回的值）
                    if field_info.get('value'):
                        field_value = field_info.get('value')
                        
                        # 处理值格式（匹配enhanced引擎）
                        field_value = self._process_field_value(field_value, ft)
                    
                    # 根据PDF字段类型映射到我们的类型系统（支持combobox/listbox）
                    if ft == '/Tx':
                        field_type = 'text'
                    elif ft == '/Btn':
                        # 检查按钮类型，过滤掉push button
                        if flags and isinstance(flags, int):
                            if flags & 65536:  # Push button flag
                                field_type = 'button'  # 标记为button，稍后过滤
                            elif flags & 32768:  # Radio button flag
                                field_type = 'radio'
                                # 为radio字段创建选项（匹配enhanced引擎）
                                if has_options and options:
                                    # Radio字段：text是选项文本，value是索引
                                    field_options = []
                                    for idx, opt in enumerate(options):
                                        value = has_kids[idx]["/AP"]["/N"].keys()[0].replace("/", "")
                                        field_options.append({'text': opt, 'value': value})
                            else:
                                field_type = 'checkbox'
                                # 为checkbox字段创建固定选项（匹配enhanced引擎）
                                field_options = [
                                    {'text': '选中', 'value': 'Yes'},
                                    {'text': '未选中', 'value': 'Off'}
                                ]
                        else:
                            field_type = 'checkbox'
                            # 为checkbox字段创建固定选项
                            field_options = [
                                {'text': '选中', 'value': 'Yes'},
                                {'text': '未选中', 'value': 'Off'}
                            ]
                    elif ft == '/Ch':
                        # 选择字段：需要根据标志位区分select和listbox（匹配enhanced引擎）
                        if has_options:
                            if flags and isinstance(flags, int):
                                if flags & 131072:  # 0x20000 组合框标志
                                    field_type = 'select'  # enhanced引擎将combobox识别为select
                                else:
                                    field_type = 'listbox'
                            else:
                                field_type = 'select'  # 默认
                            # 转换选项格式以匹配enhanced引擎
                            field_options = [{'text': opt, 'value': opt} for opt in options] if options else []
                        else:
                            field_type = 'text'
                    elif ft == '/Sig':
                        field_type = 'signature'
                    elif ft is None and has_kids:
                        field_type = 'text'  # 父字段，通常是文本类型
                        is_subfield = True
                        subfield_info = {
                            'has_kids': True,
                            'parent_field': field_name
                        }
                
                # 确保field_value是字符串
                field_value = field_value if field_value else ''
                
                # 构建attributes（匹配enhanced引擎）
                field_attributes = {}
                if field_name in enhanced_info:
                    field_info = enhanced_info[field_name]
                    
                    # 添加最大长度（对于文本字段）
                    max_length = field_info.get('max_length')
                    if field_type == 'text' and max_length:
                        field_attributes['max_length'] = max_length
                    
                    # 添加标志位信息
                    if flags and isinstance(flags, int):
                        field_attributes['flags'] = flags
                        field_attributes['flag_meanings'] = self._parse_field_flags(flags)
                
                # 如果没有attributes，设为None（匹配enhanced引擎）
                if not field_attributes:
                    field_attributes = None
                
                # 跳过button类型字段（匹配enhanced引擎）
                if field_type == 'button':
                    logger.debug(f'跳过按钮字段: {field_name}')
                    continue
                
                # 使用简单的页面推断逻辑
                page_num = self._infer_page_number(field_name)
                
                field = {
                    'name': field_name,
                    'label': None,  # 添加label字段
                    'type': field_type,
                    'value': field_value,
                    'options': field_options if field_options else None,  # 匹配enhanced引擎格式
                    'button_info': None,
                    'attributes': field_attributes,
                    'is_subfield': is_subfield,
                    'subfield_info': subfield_info,
                    'page': page_num,
                    'position': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                    'required': False
                }
                fields.append(field)
            
            # 清理临时文件
            os.remove(temp_input_path)
            
            return fields
            
        except Exception as e:
            logger.error(f'使用增强fillpdf解析PDF表单字段失败: {str(e)}')
            raise Exception(f'解析PDF表单字段失败: {str(e)}')
    
    async def fill_form(self, file: UploadFile, fields: List[Dict[str, Any]], strict_validation: bool = True) -> str:
        """
        填充PDF表单（增强版，支持子字段）
        
        Args:
            file: 上传的PDF文件
            fields: 要填充的字段数据
            strict_validation: 是否严格验证
            
        Returns:
            填充后的PDF文件路径
        """
        try:
            # 保存输入文件
            temp_input_path = os.path.join(settings.TEMP_DIR, f'input_{uuid.uuid4().hex}_{file.filename}')
            content = await file.read()
            
            with open(temp_input_path, 'wb') as f:
                f.write(content)
            
            # 转换字段数据为fillpdf格式
            field_values = {}
            for field in fields:
                field_name = field.get('name')
                field_value = field.get('value', '')
                if field_name:
                    field_values[field_name] = str(field_value)
            
            logger.info(f'转换后的字段数据: {list(field_values.keys())}')
            
            # 生成输出文件路径
            output_filename = f'filled_enhanced_{uuid.uuid4().hex}_{file.filename}'
            output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
            
            # 使用增强版fillpdf填充表单
            write_fillable_pdf(temp_input_path, output_path, field_values)
            
            logger.info(f'使用增强fillpdf成功填充，支持子字段: {output_path}')
            
            # 清理临时文件
            os.remove(temp_input_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f'使用增强fillpdf填充PDF表单失败: {str(e)}')
            # 清理可能存在的临时文件
            try:
                if 'temp_input_path' in locals():
                    os.remove(temp_input_path)
            except:
                pass
            raise Exception(f'填充PDF表单失败: {str(e)}')
    


    def _infer_page_number(self, field_name: str) -> int:
        """
        简化版本：所有字段都返回页面1
        """
        return 1

       

    async def create_sample_form(self) -> str:
        """
        创建示例表单（复用原有逻辑）
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfbase import pdfform
            from reportlab.lib.colors import black, white
            
            sample_form_path = os.path.join(settings.OUTPUT_DIR, 'enhanced_sample_form.pdf')
            
            c = canvas.Canvas(sample_form_path, pagesize=letter)
            c.setTitle("Enhanced Sample Form")
            
            # 添加标题
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 750, "Enhanced Sample PDF Form")
            
            # 添加文本字段
            c.setFont("Helvetica", 12)
            c.drawString(50, 700, "Name:")
            c.acroForm.textfield(name='name', tooltip='Enter your name',
                               x=120, y=695, borderStyle='inset',
                               width=200, height=20, textColor=black, fillColor=white)
            
            c.drawString(50, 650, "Email:")
            c.acroForm.textfield(name='email', tooltip='Enter your email',
                               x=120, y=645, borderStyle='inset',
                               width=200, height=20, textColor=black, fillColor=white)
            
            # 添加测试子字段（模拟复杂结构）
            c.drawString(50, 600, "Contact No:")
            c.acroForm.textfield(name='contact no', tooltip='Enter contact number',
                               x=120, y=595, borderStyle='inset',
                               width=200, height=20, textColor=black, fillColor=white)
            
            c.save()
            
            logger.info(f'创建增强示例表单: {sample_form_path}')
            return sample_form_path
            
        except Exception as e:
            logger.error(f'创建增强示例表单失败: {str(e)}')
            raise Exception(f'创建示例表单失败: {str(e)}')
    
    def _parse_field_flags(self, flags: int) -> Dict[str, bool]:
        """
        解析字段标志的含义（匹配enhanced引擎）
        
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
    
    def _process_field_value(self, value: str, field_type: str) -> str:
        """
        处理字段值格式（匹配enhanced引擎）
        
        Args:
            value: 原始值
            field_type: PDF字段类型 (/Tx, /Btn, /Ch等)
            
        Returns:
            处理后的值
        """
        if not value:
            return ''
        
        value_str = str(value).strip()
        
        # 处理按钮字段（复选框和单选按钮）：去掉开头的 "/"
        if field_type == '/Btn' and isinstance(value_str, str) and value_str.startswith('/'):
            value_str = value_str[1:]
        
        # 处理按钮字段：将 "On" 转换为 "Yes"
        if field_type == '/Btn' and isinstance(value_str, str) and value_str == 'On':
            value_str = 'Yes'
        
        return value_str 