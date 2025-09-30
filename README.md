# PDF表单服务

一个基于 FastAPI 的 PDF 表单处理服务，支持解析和填充 PDF 表单字段。

## 功能特性

- 解析 PDF 表单字段
- 填充 PDF 表单
- 创建示例表单
- 支持多种字段类型：
  - 文本字段 (text)
  - 复选框 (checkbox)
  - 选择框 (select/dropdown)
  - 单选按钮 (radio)
  - 必填字段标记

## 安装和配置

### 1. 克隆项目

```bash
git clone <repository-url>
cd pdf-form-service
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

**方法一：使用设置脚本（推荐）**

```bash
python setup.py
```

**方法二：手动配置**

复制环境变量示例文件：

```bash
cp env.example .env
```

编辑 `.env` 文件，根据需要修改配置：

```bash
# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 文件路径配置
UPLOAD_DIR=uploads
OUTPUT_DIR=outputs
TEMP_DIR=temp

# 文件大小限制 (MB)
MAX_FILE_SIZE=50

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# 安全配置
SECRET_KEY=your-secret-key-here-change-this-in-production
```

### 4. 测试配置（可选）

验证配置是否正确从 `.env` 文件读取：

```bash
python test_config.py
```

### 5. 运行服务

```bash
python main.py
```

或者使用 uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### podman 安装
```bash
podman build -t 132.148.160.89/library/wcl/pdf-form-service:latest . 
podman push --tls-verify=false 132.148.160.89/library/wcl/pdf-form-service:latest
```


## API 接口

### 1. 解析 PDF 表单字段

**接口地址**: `POST /api/v1/parse-form`

**请求格式**: `multipart/form-data`

**参数**:
- `file`: PDF 文件

**示例**:
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form' \
--header 'Content-Type: application/json' \
--form 'file=@"/D:/Doc/pdf-form/EDIT OoPdfFormExample.pdf"'
```

**响应示例**:
```json
{
  "success": true,
  "message": "PDF表单解析成功",
  "fields": [
    {
      "name": "Given Name Text Box",
      "label": null,
      "type": "text",
      "value": "",
      "options": null,
      "button_info": null,
      "attributes": {
        "max_length": 40
      },
      "page": 1,
      "position": {
        "x": 165.7,
        "y": 453.7,
        "width": 150.0,
        "height": 14.2
      },
      "required": false
    }
  ],
  "field_count": 17
}
```

### 2. 填充 PDF 表单

**接口地址**: `POST /api/v1/fill-form`

**请求格式**: `multipart/form-data`

**参数**:
- `file`: 原始 PDF 表单文件
- `form_data`: JSON 格式的字段数据

**示例**:
```bash
curl --location 'http://{ip}:8000/api/v1/fill-form' \
--header 'accept: application/pdf' \
--form 'file=@"/D:/Doc/pdf-form/Form.pdf"' \
--form 'form_data="{\"fields\":[{\"name\":\"FullName\",\"value\":\"张三\"},{\"name\":\"ID\",\"value\":\"110101199001011234\"},{\"name\":\"Gender\",\"value\":\"1\"},{\"name\":\"Married\",\"value\":\"Yes\"},{\"name\":\"City\",\"value\":\"New York\"},{\"name\":\"Language\",\"value\":\"English\"},{\"name\":\"Notes\",\"value\":\"这是一个测试填写的内容\"}]}"'
```

**响应**: 返回填充后的 PDF 文件

### 3. 使用 fillpdf 库解析表单字段

**接口地址**: `POST /api/v1/parse-form-fillpdf`

**请求格式**: `multipart/form-data`

**参数**:
- `file`: PDF 文件

**说明**: 使用 fillpdf 库解析字段，返回简化的字段信息

### 4. 创建示例表单

**接口地址**: `GET /api/v1/parse-form-sample`

**说明**: 创建并解析示例 PDF 表单字段

### 5. 健康检查

**接口地址**: `GET /health`

**响应示例**:
```json
{
  "status": "healthy",
  "service": "pdf-form-service"
}
```

## 使用说明

### 基本使用流程

1. **解析表单字段**: 首先调用解析接口获取 PDF 表单中的所有字段信息
2. **准备字段数据**: 根据解析结果准备要填充的字段数据
3. **填充表单**: 调用填充接口将数据写入 PDF 表单

### 字段数据格式

填充表单时，`form_data` 参数需要包含以下格式的 JSON 数据：

```json
{
  "fields": [
    {
      "name": "字段名称",
      "value": "字段值"
    }
  ]
}
```

### 字段类型说明

- **文本字段**: 直接填写文本值
- **复选框**: 使用 "Yes"/"No" 或 "On"/"Off"
- **选择框**: 填写选项值
- **单选按钮**: 填写选项值

### 注意事项

1. 字段名称必须与 PDF 表单中的字段名称完全匹配
2. 建议先调用解析接口获取准确的字段名称
3. 文件大小限制为 50MB
4. 只支持 PDF 格式文件

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| HOST | 0.0.0.0 | 服务器监听地址 |
| PORT | 8000 | 服务器端口 |
| DEBUG | false | 调试模式 |
| UPLOAD_DIR | uploads | 上传文件目录 |
| OUTPUT_DIR | outputs | 输出文件目录 |
| TEMP_DIR | temp | 临时文件目录 |
| MAX_FILE_SIZE | 50 | 最大文件大小 (MB) |
| LOG_LEVEL | INFO | 日志级别 |
| LOG_FILE | logs/app.log | 日志文件路径 |


### 安全注意事项

1. **生产环境**：务必修改 `SECRET_KEY` 为强密码
2. **文件权限**：确保上传和输出目录有适当的读写权限
3. **网络安全**：在生产环境中使用 HTTPS 和适当的防火墙配置

## 开发

### 项目结构

```
pdf-form-service/
├── main.py              # 应用启动文件
├── app/                 # 应用主目录
│   ├── __init__.py      # 应用包初始化
│   ├── main.py          # FastAPI应用主文件
│   ├── utils/           # 工具模块
│   │   ├── __init__.py
│   │   ├── config.py    # 配置管理
│   │   └── logger.py    # 日志配置
│   ├── services/        # 业务逻辑服务
│   │   ├── __init__.py
│   │   └── pdf_service.py # PDF处理服务
│   └── models/          # 数据模型
│       ├── __init__.py
│       └── request_models.py
├── requirements.txt     # 依赖包
├── .env                 # 环境变量 (不提交到版本控制)
├── env.example          # 环境变量示例
├── setup.py             # 环境设置脚本
├── test_config.py       # 配置测试脚本
└── README.md           # 项目说明
```

### 日志

日志文件位于 `logs/app.log`，可以通过 `LOG_LEVEL` 环境变量控制日志级别。

## 相关文档

- [API 详细文档](./API_DOCUMENTATION.md) - 完整的 API 输入输出格式说明
- [API Documentation (English)](./API_DOCUMENTATION_EN.md) - Complete API documentation in English
- [CURL 示例](./API_CURL_EXAMPLES.md) - 详细的 CURL 调用示例

## 许可证

MIT License 