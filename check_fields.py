#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查PDF字段选项
"""

import os
import sys
import asyncio
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pdf_service import PDFService

async def check_fields():
    """检查PDF字段选项"""
    logger.info("=== 检查PDF字段选项 ===")
    
    # 创建服务实例
    service = PDFService()
    
    # 使用现有的测试PDF
    pdf_path = 'outputs/test_basic.pdf'
    
    # 创建临时的 UploadFile 对象
    with open(pdf_path, 'rb') as f:
        content = f.read()
    
    from io import BytesIO
    from fastapi import UploadFile
    file_obj = BytesIO(content)
    upload_file = UploadFile(
        filename=os.path.basename(pdf_path),
        file=file_obj
    )
    
    try:
        # 解析字段
        fields = await service.parse_form_fields(upload_file)
        logger.info(f'解析到 {len(fields)} 个字段')
        
        # 显示字段信息
        for field in fields:
            field_name = field.get('name', 'Unknown')
            field_type = field.get('type', 'Unknown')
            options = field.get('options', [])
            logger.info(f'字段: {field_name}, 类型: {field_type}, 选项: {options}')
        
    except Exception as e:
        logger.error(f'解析字段失败: {e}')

async def main():
    # 设置日志
    logger.remove()
    logger.add(sys.stderr, level='INFO', format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>')
    
    await check_fields()
    
    logger.success("字段检查完成！")

if __name__ == '__main__':
    asyncio.run(main())
