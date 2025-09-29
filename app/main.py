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
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.services.pdf_service import PDFService
from app.services.pdf_service_fillpdf import PDFServiceFillPDF
from app.services.pdf_service_pypdf import PDFServicePyPDF
from app.services.pdf_service_enhanced_fillpdf import PDFServiceEnhancedFillPDF
from app.utils.config import settings

# 创建服务实例
pdf_service = PDFService()  # 原有的增强解析服务
pdf_service_fillpdf = PDFServiceFillPDF()  # 原始fillpdf库服务
pdf_service_pypdf = PDFServicePyPDF()  # 标准PyPDF2服务
pdf_service_enhanced_fillpdf = PDFServiceEnhancedFillPDF()  # 增强版fillpdf服务

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
async def parse_pdf_form(
  file: UploadFile = File(...),
  engine: str = Form("enhanced_fillpdf")
):
  """
  解析PDF表单字段
  
  Args:
    file: 上传的PDF文件
    engine: 解析引擎选择，可选值：
      - "standard": 使用标准PyPDF2方法（推荐，兼容性最好）
      - "enhanced": 使用增强解析引擎（支持文本识别）
      - "fillpdf": 使用原始fillpdf库解析
      - "enhanced_fillpdf": 使用增强版fillpdf库解析（支持子字段）
    
  Returns:
    JSON格式的字段列表
  """
  try:
    logger.info(f'开始解析PDF表单: {file.filename}, 引擎: {engine}')
    
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
      raise HTTPException(status_code=400, detail='只支持PDF文件')
    
    # 选择解析引擎
    if engine == "standard":
      logger.info('使用标准PyPDF2引擎解析表单')
      fields = await pdf_service_pypdf.parse_form_fields(file)
    elif engine == "enhanced": 
      logger.info('使用增强引擎解析表单')
      fields = await pdf_service.parse_form_fields(file)
    elif engine == "fillpdf":
      logger.info('使用原始fillpdf引擎解析表单')
      fields = await pdf_service_fillpdf.parse_form_fields(file)
    elif engine == "enhanced_fillpdf":
      logger.info('使用增强版fillpdf引擎解析表单（支持子字段）')
      try:
        fields = await pdf_service_enhanced_fillpdf.parse_form_fields(file)
        logger.info(f'增强版fillpdf引擎解析成功，发现 {len(fields)} 个字段')
      except Exception as e:
        logger.warning(f'增强版fillpdf引擎解析失败: {str(e)}')
        logger.info('自动切换到standard引擎进行解析')
        try:
          # 重置文件指针到开始位置
          await file.seek(0)
          fields = await pdf_service_pypdf.parse_form_fields(file)
          logger.info(f'standard引擎解析成功，发现 {len(fields)} 个字段')
          # 更新引擎名称以反映实际使用的引擎
          engine = 'enhanced_fillpdf_fallback_to_standard'
        except Exception as fallback_e:
          logger.error(f'standard引擎也解析失败: {str(fallback_e)}')
          # 抛出fallback错误而不是原始错误
          raise fallback_e
    else:
      raise HTTPException(status_code=400, detail=f'不支持的引擎类型: {engine}')
    
    logger.info(f'PDF表单解析完成，发现 {len(fields)} 个字段')
    
    return {
      'success': True,
      'message': f'PDF表单解析成功 (引擎: {engine})',
      'engine': engine,
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
  strict_validation: bool = Form(True),
  engine: str = Form("enhanced_fillpdf")
):
  """
  填充PDF表单
  
  Args:
    file: 原始PDF表单文件
    form_data: 表单数据，包含字段名和值的映射
    strict_validation: 是否严格验证字段选项，默认为 True
    engine: 填充引擎选择，可选值：
      - "standard": 使用标准PyPDF2方法（推荐，兼容性最好）
      - "enhanced": 使用增强引擎（支持子字段处理）  
      - "fillpdf": 使用原始fillpdf库（传统方法）
      - "enhanced_fillpdf": 使用增强版fillpdf库（支持所有字段类型和子字段）
    
  Returns:
    填充后的PDF文件
  """
  try:
    logger.info(f'开始填充PDF表单: {file.filename}, 引擎: {engine}')
    
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
    
    # 选择填充引擎
    if engine == "standard":
      # 使用标准PyPDF2方法 - 兼容性最好（推荐）
      logger.info('使用标准PyPDF2引擎填充表单（兼容性最好）')
      output_path = await pdf_service_pypdf.fill_form(file, fields_data, strict_validation)
    elif engine == "enhanced":
      # 使用增强型引擎 - 支持多种字段类型和子字段
      logger.info('使用增强引擎填充表单（支持子字段处理）')
      output_path = await pdf_service.fill_form(file, fields_data, strict_validation)
    elif engine == "fillpdf":
      # 使用原始 fillpdf 引擎 - 传统选项
      logger.info('使用原始fillpdf引擎填充表单（传统模式）')
      output_path = await pdf_service_fillpdf.fill_form(file, fields_data, strict_validation)
    elif engine == "enhanced_fillpdf":
      # 使用增强版 fillpdf 引擎 - 支持所有字段类型和子字段
      logger.info('使用增强版fillpdf引擎填充表单（支持所有字段类型和子字段）')
      try:
        output_path = await pdf_service_enhanced_fillpdf.fill_form(file, fields_data, strict_validation)
        logger.info(f'增强版fillpdf引擎填充成功: {output_path}')
      except Exception as e:
        logger.warning(f'增强版fillpdf引擎填充失败: {str(e)}')
        logger.info('自动切换到standard引擎进行填充')
        try:
          # 重置文件指针到开始位置
          await file.seek(0)
          output_path = await pdf_service_pypdf.fill_form(file, fields_data, strict_validation)
          logger.info(f'standard引擎填充成功: {output_path}')
          # 更新引擎名称以反映实际使用的引擎
          engine = 'enhanced_fillpdf_fallback_to_standard'
        except Exception as fallback_e:
          logger.error(f'standard引擎也填充失败: {str(fallback_e)}')
          # 抛出fallback错误而不是原始错误
          raise fallback_e
    else:
      raise HTTPException(status_code=400, detail=f'不支持的引擎类型: {engine}')
    
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
    port=settings.PORT,
    reload=True,
    log_level='info'
  )
