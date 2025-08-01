import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from loguru import logger
import uvicorn

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.pdf_service import PDFService
from app.services.pdf_service_fillpdf import PDFServiceFillPDF
from app.utils.config import settings

# 创建服务实例
pdf_service = PDFService()  # 用于解析表单字段
pdf_service_fillpdf = PDFServiceFillPDF()  # 用于填充表单

@asynccontextmanager
async def lifespan(app: FastAPI):
  """应用生命周期管理"""
  # 启动时
  logger.info('应用启动中...')
  
  # 确保必要的目录存在
  directories = [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR]
  for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True)
  
  logger.info('应用启动完成')
  yield
  
  # 关闭时
  logger.info('应用关闭中...')

# 创建FastAPI应用
app = FastAPI(
  title='PDF表单处理服务',
  description='提供PDF表单解析和填充功能',
  version='1.0.0',
  lifespan=lifespan
)

@app.get('/')
async def root():
  """根路径"""
  return {
    'message': 'PDF表单处理服务',
    'version': '1.0.0',
    'endpoints': {
      'parse_form': '/api/v1/parse-form',
      'fill_form': '/api/v1/fill-form',
      'parse_form_sample': '/api/v1/parse-form-sample'
    }
  }

@app.get('/health')
async def health_check():
  """健康检查"""
  return {'status': 'healthy'}

@app.post('/api/v1/parse-form')
async def parse_pdf_form(file: UploadFile = File(...)):
  """
  解析PDF表单字段
  
  Args:
    file: 上传的PDF文件
    
  Returns:
    JSON格式的字段列表
  """
  try:
    logger.info(f'开始解析PDF表单: {file.filename}')
    
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
      raise HTTPException(status_code=400, detail='只支持PDF文件')
    
    # 解析PDF表单字段
    fields = await pdf_service.parse_form_fields(file)
    
    logger.info(f'PDF表单解析完成，发现 {len(fields)} 个字段')
    
    return {
      'success': True,
      'message': 'PDF表单解析成功',
      'fields': fields,
      'field_count': len(fields)
    }
    
  except Exception as e:
    logger.error(f'解析PDF表单失败: {str(e)}')
    raise HTTPException(status_code=500, detail=f'解析PDF表单失败: {str(e)}')

@app.post('/api/v1/fill-form')
async def fill_pdf_form(
  form_data: str = Form(...),
  file: UploadFile = File(...),
  strict_validation: bool = Form(True)
):
  """
  填充PDF表单
  
  Args:
    file: 原始PDF表单文件
    form_data: 表单数据，包含字段名和值的映射
    strict_validation: 是否严格验证字段选项，默认为 True
    
  Returns:
    填充后的PDF文件
  """
  try:
    logger.info(f'开始填充PDF表单: {file.filename}')
    
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
      raise HTTPException(status_code=400, detail='只支持PDF文件')
    
    # 解析 JSON 字符串
    import json
    form_data_obj = json.loads(form_data)
    
    if not form_data_obj or 'fields' not in form_data_obj:
      raise HTTPException(status_code=400, detail='请提供有效的表单数据')
    
    # 转换字段数据格式
    fields_data = form_data_obj['fields']
    
    # 填充PDF表单 - 使用PDFServiceFillPDF进行填充
    output_path = await pdf_service_fillpdf.fill_form(file, fields_data, strict_validation)
    
    logger.info(f'PDF表单填充完成: {output_path}')
    
    # 返回填充后的PDF文件
    return FileResponse(
      path=output_path,
      filename=f'filled_{file.filename}',
      media_type='application/pdf'
    )
    
  except json.JSONDecodeError as e:
    logger.error(f'JSON解析失败: {str(e)}')
    raise HTTPException(status_code=400, detail=f'JSON格式错误: {str(e)}')
  except Exception as e:
    logger.error(f'填充PDF表单失败: {str(e)}')
    raise HTTPException(status_code=500, detail=f'填充PDF表单失败: {str(e)}')

@app.post('/api/v1/parse-form-sample')
async def parse_pdf_form_fillpdf(file: UploadFile = File(...)):
  """
  使用fillpdf库解析PDF表单字段
  
  Args:
    file: 上传的PDF文件
    
  Returns:
    JSON格式的字段列表
  """
  try:
    logger.info(f'开始使用fillpdf解析PDF表单: {file.filename}')
    
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
      raise HTTPException(status_code=400, detail='只支持PDF文件')
    
    # 使用fillpdf解析PDF表单字段
    fields = await pdf_service_fillpdf.parse_form_fields(file)
    
    logger.info(f'PDF表单解析完成，发现 {len(fields)} 个字段')
    
    return {
      'success': True,
      'message': 'PDF表单解析成功',
      'fields': fields,
      'field_count': len(fields)
    }
    
  except Exception as e:
    logger.error(f'解析PDF表单失败: {str(e)}')
    raise HTTPException(status_code=500, detail=f'解析PDF表单失败: {str(e)}')

@app.get('/api/v1/parse-form-sample')
async def parse_sample_form():
  """
  解析示例PDF表单字段（使用fillpdf库）
  
  Returns:
    JSON格式的字段列表
  """
  try:
    logger.info('开始解析示例PDF表单')
    
    # 创建示例表单
    sample_form_path = await pdf_service_fillpdf.create_sample_form()
    
    # 将文件路径转换为 UploadFile 对象
    with open(sample_form_path, 'rb') as f:
      from io import BytesIO
      file_content = f.read()
      file_obj = BytesIO(file_content)
      upload_file = UploadFile(
        filename='sample_form.pdf',
        file=file_obj,
        content_type='application/pdf'
      )
    
    # 解析表单字段
    fields = await pdf_service_fillpdf.parse_form_fields(upload_file)
    
    logger.info(f'示例PDF表单解析完成，发现 {len(fields)} 个字段')
    
    return {
      'success': True,
      'message': '示例PDF表单解析成功',
      'fields': fields,
      'field_count': len(fields),
      'sample_form_path': sample_form_path
    }
    
  except Exception as e:
    logger.error(f'解析示例PDF表单失败: {str(e)}')
    raise HTTPException(status_code=500, detail=f'解析示例PDF表单失败: {str(e)}')

if __name__ == '__main__':
  uvicorn.run(
    'app.main:app',
    host='0.0.0.0',
    port=8001,
    reload=True,
    log_level='info'
  )
