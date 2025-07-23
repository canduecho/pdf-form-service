# PDF表单服务 API curl 调用示例

## 🚀 快速开始

### 1. 启动服务
```bash
python main.py
```

### 2. 测试服务是否运行
```bash
curl -X GET "http://localhost:8000/health"
```

## 📋 API 接口调用示例

### 1. 健康检查
```bash
curl -X GET "http://localhost:8000/health"
```

**响应示例:**
```json
{
  "status": "healthy",
  "service": "pdf-form-service"
}
```

### 2. 获取服务信息
```bash
curl -X GET "http://localhost:8000/"
```

**响应示例:**
```json
{
  "message": "PDF表单处理服务",
  "version": "1.0.0",
  "endpoints": {
    "parse_form": "/api/v1/parse-form",
    "fill_form": "/api/v1/fill-form"
  }
}
```

### 3. 解析PDF表单字段

#### 基本调用
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf"
```

#### 带详细信息的调用
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  -v
```

**响应示例:**
```json
{
  "success": true,
  "message": "PDF表单解析成功",
  "fields": [
    {
      "name": "姓名",
      "type": "text",
      "value": "",
      "page": 1,
      "position": {
        "x": 100,
        "y": 200,
        "width": 150,
        "height": 20
      },
      "required": false
    }
  ],
  "field_count": 1
}
```

### 4. 填充PDF表单

#### 基本调用
```bash
curl -X POST "http://localhost:8000/api/v1/fill-form" \
  -H "accept: application/pdf" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  -F 'form_data={"fields":[{"name":"姓名","value":"张三"},{"name":"邮箱","value":"zhangsan@example.com"}]}' \
  --output filled_form.pdf
```

#### 使用JSON文件
```bash
# 创建表单数据文件
cat > form_data.json << EOF
{
  "fields": [
    {
      "name": "姓名",
      "value": "张三"
    },
    {
      "name": "邮箱", 
      "value": "zhangsan@example.com"
    },
    {
      "name": "电话",
      "value": "13800138000"
    }
  ]
}
EOF

# 调用API
curl -X POST "http://localhost:8000/api/v1/fill-form" \
  -H "accept: application/pdf" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  -F "form_data=@form_data.json" \
  --output filled_form.pdf
```

## 🔧 高级用法

### 1. 查看详细请求信息
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  -v
```

### 2. 设置超时时间
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  --max-time 30
```

### 3. 保存响应头信息
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  -D response_headers.txt
```

### 4. 使用代理
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_form.pdf" \
  --proxy "http://proxy.example.com:8080"
```

## 🐛 错误处理

### 1. 文件类型错误
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.txt"
```

**响应:**
```json
{
  "detail": "只支持PDF文件"
}
```

### 2. 缺少文件
```bash
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data"
```

**响应:**
```json
{
  "detail": [
    {
      "loc": ["body", "file"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## 📝 测试脚本

### 完整测试流程
```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "🧪 开始API测试..."

# 1. 健康检查
echo "1. 健康检查..."
curl -s -X GET "$BASE_URL/health" | jq '.'

# 2. 获取服务信息
echo "2. 获取服务信息..."
curl -s -X GET "$BASE_URL/" | jq '.'

# 3. 解析PDF表单（如果有测试文件）
if [ -f "sample_form.pdf" ]; then
  echo "3. 解析PDF表单..."
  curl -s -X POST "$BASE_URL/api/v1/parse-form" \
    -H "accept: application/json" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@sample_form.pdf" | jq '.'
else
  echo "3. 跳过PDF解析测试（缺少sample_form.pdf文件）"
fi

echo "✅ 测试完成"
```

## 🎯 实用技巧

### 1. 使用 jq 格式化JSON响应
```bash
curl -s -X GET "http://localhost:8000/health" | jq '.'
```

### 2. 保存响应到文件
```bash
curl -s -X GET "http://localhost:8000/" > response.json
```

### 3. 批量测试
```bash
for i in {1..10}; do
  echo "测试 $i"
  curl -s -X GET "http://localhost:8000/health"
  sleep 1
done
```

### 4. 监控API性能
```bash
curl -w "@curl-format.txt" -X GET "http://localhost:8000/health"
```

创建 `curl-format.txt`:
```
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
``` 