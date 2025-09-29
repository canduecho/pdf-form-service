#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用标准PyPDF2方法的PDF表单处理服务
"""

import os
import uuid
import tempfile
from typing import List, Dict, Any, Optional
from loguru import logger
from fastapi import UploadFile
from pathlib import Path

from app.utils.config import settings


class PDFServicePyPDF:
    """使用标准PyPDF2方法的PDF表单处理服务"""
    
    def __init__(self):
        self.ensure_directories()
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    async def parse_form_fields(self, file: UploadFile) -> List[Dict[str, Any]]:
        """
        使用标准PyPDF2方法解析PDF表单字段
        
        Args:
            file: 上传的PDF文件 (UploadFile对象)
            
        Returns:
            字段列表，每个字段包含名称、类型、值、选项等信息
        """
        try:
            import PyPDF2
            from io import BytesIO
            
            content = await file.read()
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            fields = []
            
            # 方法1: 使用标准的get_fields()方法
            try:
                form_fields = pdf_reader.get_fields()
                if form_fields:
                    logger.info(f'使用get_fields()找到 {len(form_fields)} 个字段')
                    
                    for field_name, field_obj in form_fields.items():
                        field_info = self._extract_field_from_object(field_name, field_obj)
                        if field_info:
                            fields.append(field_info)
                            
            except Exception as e:
                logger.warning(f'get_fields()方法失败: {str(e)}')
            
            # 方法2: 如果get_fields()失败，尝试从页面注释中提取
            if not fields:
                logger.info('尝试从页面注释中提取字段...')
                for page_num, page in enumerate(pdf_reader.pages):
                    if '/Annots' in page:
                        annotations = page['/Annots']
                        if annotations:
                            for annotation in annotations:
                                try:
                                    annot_obj = annotation.get_object()
                                    if annot_obj.get('/Subtype') == '/Widget':
                                        field_info = self._extract_field_from_annotation(annot_obj, page_num)
                                        if field_info:
                                            fields.append(field_info)
                                except Exception as e:
                                    logger.debug(f'处理注释失败: {str(e)}')
                                    continue
            
            # 方法3: 如果以上都失败，回退到文本提取方法
            if not fields:
                logger.info('回退到文本提取方法...')
                fields = self._extract_fields_from_text(pdf_reader)
            
            logger.info(f'最终解析到 {len(fields)} 个表单字段')
            return fields
            
        except Exception as e:
            logger.error(f'解析PDF表单字段失败: {str(e)}')
            raise Exception(f'解析PDF表单字段失败: {str(e)}')
    
    def _extract_field_from_object(self, field_name: str, field_obj) -> Optional[Dict[str, Any]]:
        """从PyPDF2字段对象中提取字段信息"""
        try:
            # 字段类型检测
            field_type = 'text'  # 默认
            options = []
            
            # 获取字段类型 (/FT)
            if hasattr(field_obj, 'get') and '/FT' in field_obj:
                ft = field_obj['/FT']
                if ft == '/Ch':  # Choice字段
                    # 检查是否为组合框或列表框
                    if '/Ff' in field_obj:
                        ff = field_obj['/Ff']
                        if isinstance(ff, int):
                            if ff & 131072:  # 组合框标志
                                field_type = 'combobox'
                            else:
                                field_type = 'listbox'
                    else:
                        field_type = 'select'
                    
                    # 提取选项 (/Opt)
                    if '/Opt' in field_obj:
                        opt = field_obj['/Opt']
                        if hasattr(opt, '__iter__'):
                            for option in opt:
                                if hasattr(option, 'decode'):
                                    options.append(option.decode('utf-8', errors='ignore'))
                                else:
                                    options.append(str(option))
                
                elif ft == '/Btn':  # 按钮字段
                    if '/Ff' in field_obj:
                        ff = field_obj['/Ff']
                        if isinstance(ff, int):
                            if ff & 32768:  # 单选按钮
                                field_type = 'radio'
                            elif ff & 65536:  # 推按钮
                                field_type = 'button'
                            else:
                                field_type = 'checkbox'
                    else:
                        field_type = 'checkbox'
                
                elif ft == '/Tx':  # 文本字段
                    field_type = 'text'
                
                elif ft == '/Sig':  # 签名字段
                    field_type = 'signature'
            
            # 获取字段值
            field_value = ''
            if hasattr(field_obj, 'get') and '/V' in field_obj:
                value = field_obj['/V']
                if hasattr(value, 'decode'):
                    field_value = value.decode('utf-8', errors='ignore')
                else:
                    field_value = str(value) if value else ''
            
            # 获取默认值
            default_value = ''
            if hasattr(field_obj, 'get') and '/DV' in field_obj:
                dv = field_obj['/DV']
                if hasattr(dv, 'decode'):
                    default_value = dv.decode('utf-8', errors='ignore')
                else:
                    default_value = str(dv) if dv else ''
            # filter button field
            if field_type == 'button':
                return None
            
            return {
                'name': field_name,
                'label': '',
                'type': field_type,
                'value': field_value,
                # 'default_value': default_value,
                "button_info":None,
                'options': options,
                'page': 1,  # PyPDF2的get_fields()不提供页面信息
                'position': None,
                'required': False,
                'attributes': {},
                'is_subfield': False,
                'subfield_info': None
            }
            
        except Exception as e:
            logger.warning(f'提取字段 {field_name} 信息失败: {str(e)}')
            return None
    
    def _extract_field_from_annotation(self, annot_obj, page_num: int) -> Optional[Dict[str, Any]]:
        """从页面注释中提取字段信息"""
        try:
            # 获取字段名
            field_name = ''
            if '/T' in annot_obj:
                name = annot_obj['/T']
                if hasattr(name, 'decode'):
                    field_name = name.decode('utf-8', errors='ignore')
                else:
                    field_name = str(name)
            
            if not field_name:
                return None
            
            # 使用相同的逻辑提取字段信息
            return self._extract_field_from_object(field_name, annot_obj)
            
        except Exception as e:
            logger.debug(f'从注释提取字段失败: {str(e)}')
            return None
    
    def _extract_fields_from_text(self, pdf_reader) -> List[Dict[str, Any]]:
        """从PDF文本中提取可能的字段（回退方法）"""
        fields = []
        
        try:
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if ':' in line and len(line) < 100:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            field_name = parts[0].strip()
                            field_value = parts[1].strip()
                            
                            if field_name and not field_name.isdigit():
                                fields.append({
                                    'name': field_name,
                                    'type': 'text',
                                    'value': field_value,
                                    'default_value': '',
                                    'options': [],
                                    'page': page_num + 1,
                                    'position': None,
                                    'required': False,
                                    'attributes': {},
                                    'is_subfield': False,
                                    'subfield_info': None
                                })
        
        except Exception as e:
            logger.warning(f'从文本提取字段失败: {str(e)}')
        
        return fields
    
    async def fill_form(self, file: UploadFile, fields: List[Dict[str, Any]], strict_validation: bool = True) -> str:
        """
        使用PyPDF2标准方法填充PDF表单
        
        Args:
            file: 原始PDF文件 (UploadFile对象)
            fields: 字段数据列表
            strict_validation: 是否严格验证字段选项，默认为 True
            
        Returns:
            填充后的PDF文件路径
        """
        try:
            import PyPDF2
            from io import BytesIO
            
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
            
            logger.info(f'准备填充字段: {list(field_values.keys())}')
            
            # 生成输出文件名
            output_filename = f'filled_pypdf_{uuid.uuid4().hex}_{file.filename}'
            output_path = os.path.join(settings.OUTPUT_DIR, output_filename)
            
            # 使用PyPDF2标准方法填充
            with open(temp_input_path, 'rb') as input_file:
                reader = PyPDF2.PdfReader(input_file)
                writer = PyPDF2.PdfWriter()
                
                # 复制所有页面
                for page in reader.pages:
                    writer.add_page(page)
                
                # 使用update_page_form_field_values填充表单
                if writer.pages:
                    try:
                        # 尝试不同的参数组合，因为不同版本的PyPDF2支持不同的参数
                        try:
                            writer.update_page_form_field_values(
                                writer.pages[0],  # 假设表单在第一页
                                field_values,
                                auto_regenerate=False
                            )
                        except TypeError:
                            # 如果auto_regenerate参数不存在，尝试不带此参数
                            writer.update_page_form_field_values(
                                writer.pages[0],
                                field_values
                            )
                        logger.info(f'使用update_page_form_field_values成功填充')
                    except Exception as e:
                        logger.warning(f'update_page_form_field_values失败: {str(e)}')
                        # 如果失败，尝试逐个更新字段
                        self._fill_fields_individually(writer, field_values)
                
                # 保存填充后的PDF
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
            
            # 清理临时文件
            os.remove(temp_input_path)
            
            logger.info(f'使用PyPDF2标准方法填充PDF表单完成: {output_path}')
            return output_path
            
        except Exception as e:
            logger.error(f'填充PDF表单失败: {str(e)}')
            raise Exception(f'填充PDF表单失败: {str(e)}')
    
    def _fill_fields_individually(self, writer, field_values: Dict[str, str]):
        """逐个填充字段（备用方法）"""
        try:
            # 这里可以实现逐个字段填充的逻辑
            # 暂时跳过，因为update_page_form_field_values是标准方法
            logger.info('逐个字段填充方法（未实现）')
        except Exception as e:
            logger.warning(f'逐个填充字段失败: {str(e)}') 