from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class FormField(BaseModel):
  """表单字段模型"""
  name: str = Field(..., description='字段名称')
  value: str = Field(..., description='字段值')
  field_type: Optional[str] = Field(None, description='字段类型')
  required: Optional[bool] = Field(False, description='是否必填')
  page: Optional[int] = Field(None, description='字段所在页码')

class FillFormRequest(BaseModel):
  """填充表单请求模型"""
  fields: List[FormField] = Field(..., description='表单字段列表')

class ParseFormResponse(BaseModel):
  """解析表单响应模型"""
  success: bool = Field(..., description='操作是否成功')
  message: str = Field(..., description='响应消息')
  fields: List[Dict[str, Any]] = Field(..., description='解析出的字段列表')
  field_count: int = Field(..., description='字段数量')

class HealthResponse(BaseModel):
  """健康检查响应模型"""
  status: str = Field(..., description='服务状态')
  service: str = Field(..., description='服务名称') 