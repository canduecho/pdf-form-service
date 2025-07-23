#!/usr/bin/env python3
"""
PDF表单服务启动文件
"""

import uvicorn
from app.main import app
from app.utils.config import settings

if __name__ == '__main__':
  uvicorn.run(
    'app.main:app',
    host=settings.HOST,
    port=settings.PORT,
    reload=settings.DEBUG,
    log_level='info'
  ) 