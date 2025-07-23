from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger
import os
from pathlib import Path
import aiofiles
import io

from app.services.pdf_service import PDFService
from app.services.pdf_service_fillpdf import PDFServiceFillPDF
from app.models.request_models import FillFormRequest
from app.utils.config import settings
from app.utils.logger import setup_logger

# 设置日志
setup_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
  """应用生命周期管理"""
  # 启动时执行
  logger.info('PDF表单处理服务启动中...')
  
  # 确保必要的目录存在
  os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
  os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
  
  logger.info('服务启动完成')
  
  yield
  
  # 关闭时执行
  logger.info('PDF表单处理服务关闭中...')

# 创建FastAPI应用
app = FastAPI(
  title='PDF表单处理服务',
  description='高性能PDF表单字段解析和填充API服务',
  version='1.0.0',
  lifespan=lifespan
)

# 配置CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*'],
)

# 初始化PDF服务
pdf_service = PDFService()  # 用于解析字段
pdf_service_fillpdf = PDFServiceFillPDF()  # 用于填充表单

@app.get('/')
async def root():
  """根路径，返回服务信息"""
  return {
    'message': 'PDF表单处理服务',
    'version': '1.0.0',
    'endpoints': {
      'parse_form': '/api/v1/parse-form',
      'fill_form': '/api/v1/fill-form'
    }
  }

@app.get('/health')
async def health_check():
  """健康检查接口"""
  return {'status': 'healthy', 'service': 'pdf-form-service'}

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
    
    # 解析PDF表单字段 - 使用PDFService获取详细字段信息
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
  file: UploadFile = File(...)
):
  """
  填充PDF表单
  
  Args:
    file: 原始PDF表单文件
    form_data: 表单数据，包含字段名和值的映射
    
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
    output_path = await pdf_service_fillpdf.fill_form(file, fields_data)
    
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
    async with aiofiles.open(sample_form_path, 'rb') as f:
      content = await f.read()
    
    file = UploadFile(
      filename='Form.pdf',
      file=io.BytesIO(content),
      content_type='application/pdf'
    )
    
    # 解析PDF表单字段
    fields = await pdf_service_fillpdf.parse_form_fields(file)
    
    logger.info(f'示例PDF表单解析完成，发现 {len(fields)} 个字段')
    
    return {
      'success': True,
      'message': '示例PDF表单解析成功',
      'fields': fields,
      'field_count': len(fields)
    }
    
  except Exception as e:
    logger.error(f'解析示例PDF表单失败: {str(e)}')
    raise HTTPException(status_code=500, detail=f'解析示例PDF表单失败: {str(e)}')

if __name__ == '__main__':
  uvicorn.run(
    'app.main:app',
    host=settings.HOST,
    port=settings.PORT,
    reload=settings.DEBUG,
    log_level='info'
  ) 