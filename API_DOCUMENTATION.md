# PDF 表单服务 API 文档

## 概述

PDF 表单服务提供完整的 PDF 表单处理功能，包括字段解析、表单填充等操作。

**基础 URL**: `http://{ip}:8000`

## 通用响应格式

所有 API 响应都遵循以下格式：

### 成功响应
```json
{
  "success": true,
  "message": "操作成功消息",
  "data": {...}  // 具体数据
}
```

### 错误响应
```json
{
  "detail": "错误描述信息"
}
```

## API 接口详情

### 1. 健康检查

**接口地址**: `GET /health`

**描述**: 检查服务运行状态

**请求参数**: 无

**响应示例**:
```json
{
  "status": "healthy",
  "service": "pdf-form-service"
}
```

---

### 2. 获取服务信息

**接口地址**: `GET /`

**描述**: 获取服务基本信息和可用接口

**请求参数**: 无

**响应示例**:
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

---

### 3. 解析 PDF 表单字段

**接口地址**: `POST /api/v1/parse-form`

**描述**: 解析 PDF 表单中的所有字段信息

**请求格式**: `multipart/form-data`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | PDF 文件 |

**请求示例**:
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form' \
--header 'Content-Type: application/json' \
--form 'file=@"/path/to/form.pdf"'
```

**响应格式**:
```json
{
  "success": true,
  "message": "PDF表单解析成功",
  "fields": [
    {
      "name": "字段名称",
      "label": "字段标签",
      "type": "字段类型",
      "value": "当前值",
      "options": ["选项1", "选项2"],
      "button_info": null,
      "attributes": {
        "max_length": 40,
        "flags": 393216,
        "flag_meanings": {
          "read_only": false,
          "required": false,
          "combo": true,
          "edit": true
        }
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

**字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| name | string | 字段名称（内部标识符） |
| label | string | 字段标签（用户友好名称） |
| type | string | 字段类型：text/checkbox/radio/select/listbox/button |
| value | string | 字段当前值 |
| options | array | 选项列表（适用于选择框、单选按钮） |
| button_info | object | 按钮信息（适用于按钮类型） |
| attributes | object | 字段属性（最大长度、标志等） |
| page | integer | 字段所在页码 |
| position | object | 字段位置信息 |
| required | boolean | 是否必填 |

**错误响应**:
```json
{
  "detail": "只支持PDF文件"
}
```

---

### 4. 填充 PDF 表单

**接口地址**: `POST /api/v1/fill-form`

**描述**: 将数据填充到 PDF 表单中，返回一份填好的 PDF 表单文件

**请求格式**: `multipart/form-data`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | 原始 PDF 表单文件 |
| form_data | string | 是 | JSON 格式的字段数据 |

**请求示例**:
```bash
curl --location 'http://{ip}:8000/api/v1/fill-form' \
--header 'accept: application/pdf' \
--form 'file=@"/path/to/form.pdf"' \
--form 'form_data="{\"fields\":[{\"name\":\"FullName\",\"value\":\"张三\"},{\"name\":\"ID\",\"value\":\"110101199001011234\"},{\"name\":\"Gender\",\"value\":\"1\"},{\"name\":\"Married\",\"value\":\"Yes\"},{\"name\":\"City\",\"value\":\"New York\"},{\"name\":\"Language\",\"value\":\"English\"},{\"name\":\"Notes\",\"value\":\"这是一个测试填写的内容\"}]}"' \
--output filled_form.pdf
```

**form_data 格式**:
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

**响应格式**: 
- **Content-Type**: `application/pdf`
- **Body**: 填充后的 PDF 文件内容
- **文件名**: `filled_{原始文件名}`

**说明**: 
- 接口会保持原始 PDF 表单的结构和格式
- 只填充指定的字段，其他字段保持原样
- 返回的 PDF 文件可以直接下载或保存

**错误响应**:
```json
{
  "detail": "只支持PDF文件"
}
```

```json
{
  "detail": "请提供有效的表单数据"
}
```

---

### 5. 使用 fillpdf 库解析表单字段

**接口地址**: `POST /api/v1/parse-form-fillpdf`

**描述**: 使用 fillpdf 库解析 PDF 表单字段（简化版本）

**请求格式**: `multipart/form-data`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | PDF 文件 |

**请求示例**:
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form-fillpdf' \
--header 'Content-Type: application/json' \
--form 'file=@"/path/to/form.pdf"'
```

**响应格式**:
```json
{
  "success": true,
  "message": "PDF表单解析成功",
  "fields": [
    {
      "name": "字段名称",
      "type": "text",
      "value": "当前值",
      "options": null,
      "button_info": null,
      "attributes": {},
      "page": 1,
      "position": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "required": false
    }
  ],
  "field_count": 8
}
```

---

### 6. 创建示例表单

**接口地址**: `GET /api/v1/parse-form-sample`

**描述**: 创建并解析示例 PDF 表单字段

**请求参数**: 无

**响应格式**: 与解析接口相同

---

## 字段类型详细说明

### 文本字段 (text)
- **说明**: 单行或多行文本输入
- **属性**: `max_length` - 最大字符数
- **示例值**: `"张三"`, `"这是一个测试文本"`

### 复选框 (checkbox)
- **说明**: 布尔值选择框
- **有效值**: `"Yes"`, `"No"`, `"On"`, `"Off"`
- **示例值**: `"Yes"`

### 单选按钮 (radio)
- **说明**: 单选项选择
- **属性**: `options` - 可用选项列表
- **示例值**: `"1"` (对应选项列表中的值)

### 选择框 (select)
- **说明**: 下拉选择框
- **属性**: `options` - 可用选项列表
- **示例值**: `"New York"` (对应选项列表中的值)

### 列表框 (listbox)
- **说明**: 多选列表框
- **属性**: `options` - 可用选项列表
- **示例值**: `["选项1", "选项2"]`

### 按钮 (button)
- **说明**: 表单按钮
- **属性**: `button_info` - 按钮信息
- **通常不用于数据填充**

## 错误代码说明

| HTTP 状态码 | 错误类型 | 说明 |
|-------------|----------|------|
| 400 | Bad Request | 请求参数错误（如文件格式不支持） |
| 500 | Internal Server Error | 服务器内部错误 |

## 使用示例

### 完整工作流程

1. **解析表单字段**
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form' \
--form 'file=@"/path/to/form.pdf"'
```

2. **准备填充数据**
```json
{
  "fields": [
    {"name": "FullName", "value": "张三"},
    {"name": "ID", "value": "110101199001011234"},
    {"name": "Gender", "value": "1"},
    {"name": "Married", "value": "Yes"},
    {"name": "City", "value": "New York"},
    {"name": "Language", "value": "English"},
    {"name": "Notes", "value": "这是一个测试填写的内容"}
  ]
}
```

3. **填充表单**
```bash
curl --location 'http://{ip}:8000/api/v1/fill-form' \
--header 'accept: application/pdf' \
--form 'file=@"/path/to/form.pdf"' \
--form 'form_data="{\"fields\":[{\"name\":\"FullName\",\"value\":\"张三\"}]}"' \
--output filled_form.pdf
```

**结果**: 获得一份填好的 PDF 表单文件 `filled_form.pdf`

## 注意事项

1. **文件格式**: 只支持 PDF 格式文件
2. **文件大小**: 最大 50MB
3. **字段名称**: 必须与 PDF 表单中的字段名称完全匹配
4. **编码**: 所有文本数据使用 UTF-8 编码
5. **时区**: 服务器使用 UTC 时区 