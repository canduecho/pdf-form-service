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

## API 接口

### 1. 解析 PDF 表单字段

```http
POST /api/parse-form
Content-Type: multipart/form-data

file: <PDF文件>
```

### 2. 填充 PDF 表单

```http
POST /api/fill-form
Content-Type: multipart/form-data

file: <PDF文件>
fields: <JSON格式的字段数据>
```

### 3. 创建示例表单

```http
GET /api/create-sample
```

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
| SECRET_KEY | - | 安全密钥 |

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

## 许可证

MIT License 