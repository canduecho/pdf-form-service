# PDF 表单填写使用指南

## 概述

本指南介绍如何使用 `fillpdf` 库来填写 PDF 表单。我们已经成功实现了对 `outputs/Form.pdf` 文件的填写功能，包括正确处理不同类型的字段。

## 环境要求

- Python 3.12+
- 虚拟环境 `.venv`
- `fillpdf` 库

## 安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装 fillpdf 库
pip install -r requirements.txt
```

## 文件说明

### 1. `fill_pdf_success.py` - 基础填写脚本
最简单的 PDF 填写脚本，直接使用正确的字段值。

### 2. `pdf_form_filler_practical.py` - 实用工具类
提供完整的 PDF 表单填写功能，包括：
- 字段验证
- 数据验证
- 复选框处理
- 示例数据生成
- 错误处理

### 3. `tests/` - 测试目录
包含所有测试文件：
- `test_pdf_filling.py` - PDF 填写功能测试
- `test_config.py` - 配置测试
- `test_api.sh` - API 测试脚本
- `test_api_curl.sh` - CURL API 测试脚本

### 4. `run_tests.py` - 测试运行脚本
运行 tests 目录中的所有测试。

## 使用方法

### 方法一：使用基础脚本

```python
# 直接运行基础脚本
python fill_pdf_success.py
```

### 方法二：使用工具类

```python
from pdf_form_filler_practical import PDFFormFiller

# 创建填写器
filler = PDFFormFiller('outputs/Form.pdf')

# 准备表单数据
form_data = {
    'FullName': '张三',
    'ID': '110101199001011234',
    'Gender': '1',  # 0=女，1=男
    'Married': 'Yes',  # 复选框字段，使用 Yes/No
    'City': 'New York',  # 选项: ['New York', 'London', 'Berlin', 'Paris', 'Rome']
    'Language': 'English',  # 选项: ['English', 'German', 'French', 'Italian']
    'Notes': '这是一个测试填写的内容'
}

# 填写表单
success = filler.fill_form(form_data, 'outputs/Form_filled.pdf')
```

### 方法三：使用示例数据

```python
from pdf_form_filler_practical import PDFFormFiller

# 创建填写器
filler = PDFFormFiller('outputs/Form.pdf')

# 生成示例数据
sample_data = filler.create_sample_data()

# 填写表单
success = filler.fill_form(sample_data, 'outputs/Form_filled.pdf')
```

### 方法四：运行测试

```bash
# 运行所有测试
python run_tests.py

# 运行特定测试
cd tests
python test_pdf_filling.py
```

## 表单字段说明

### 字段列表
- `FullName`: 姓名（文本输入）
- `ID`: 身份证号（文本输入）
- `Gender`: 性别（选择字段）
  - 选项: `['0', '1']`
  - 0 = 女，1 = 男
- `Married`: 婚姻状态（复选框字段）
  - 支持的值: `['Yes', 'No', 'True', 'False', '1', '0', 'on', 'off', 'checked', 'unchecked']`
  - 推荐使用: `'Yes'` 或 `'No'`
- `City`: 城市（选择字段）
  - 选项: `['New York', 'London', 'Berlin', 'Paris', 'Rome']`
- `Language`: 语言（选择字段）
  - 选项: `['English', 'German', 'French', 'Italian']`
- `Notes`: 备注（文本输入）
- `ResetButton`: 重置按钮（不需要填写）

### 字段类型说明

#### 1. 文本字段
- 可以输入任意文本
- 示例: `FullName`, `ID`, `Notes`

#### 2. 选择字段
- 必须使用预定义的选项值
- 示例: `Gender`, `City`, `Language`

#### 3. 复选框字段
- 支持多种布尔值表示
- 示例: `Married`
- 推荐使用 `'Yes'` 和 `'No'`

#### 4. 按钮字段
- 不需要填写
- 示例: `ResetButton`

## 复选框字段处理

### 问题说明
之前 `Married` 字段无法正确填写，是因为我们错误地将其当作选择字段处理。实际上它是一个复选框字段，可以接受多种布尔值表示。

### 解决方案
工具类现在能够：
1. 识别复选框字段
2. 自动转换布尔值
3. 支持多种复选框值格式

### 支持的复选框值
```python
# 选中状态
'Yes', 'True', '1', 'on', 'checked'

# 未选中状态  
'No', 'False', '0', 'off', 'unchecked'
```

### 使用示例
```python
# 方法一：使用字符串
form_data = {
    'Married': 'Yes'  # 选中
}

# 方法二：使用布尔值
form_data = {
    'Married': True  # 自动转换为 'Yes'
}

# 方法三：使用数字
form_data = {
    'Married': 1  # 自动转换为 'Yes'
}
```

## 错误处理

### 常见错误

1. **字段不存在**
   ```
   字段 FullName 不存在，跳过
   ```

2. **选项值无效**
   ```
   字段 Gender 的值 "男" 不在选项 ['0', '1'] 中
   使用默认值: 0
   ```

3. **复选框值处理**
   ```
   复选框字段 Married 使用值: Yes
   ```

4. **文件不存在**
   ```
   PDF 文件不存在: outputs/Form.pdf
   ```

### 解决方案

1. 检查字段名称是否正确
2. 使用正确的选项值
3. 对于复选框，使用 `'Yes'` 或 `'No'`
4. 确保 PDF 文件路径正确

## 输出文件

填写完成后，会在 `outputs/` 目录下生成以下文件：
- `Form_filled.pdf`: 基础脚本生成的填写文件
- `Form_filled_with_tool.pdf`: 工具类生成的填写文件

## 代码示例

### 获取字段信息

```python
# 获取所有字段名称
field_names = filler.get_field_names()
print(field_names)

# 获取字段详细信息
field_info = filler.get_all_field_info()
for field_name, info in field_info.items():
    print(f'{field_name}: {info}')
```

### 验证表单数据

```python
# 验证表单数据
form_data = {
    'FullName': '张三',
    'Gender': '男',  # 错误的值
    'Married': True,  # 布尔值会自动转换
    'City': '北京'  # 无效值
}

validated_data = filler.validate_form_data(form_data)
# 输出: {'FullName': '张三', 'Gender': '0', 'Married': 'Yes', 'City': 'New York'}
```

### 自定义填写

```python
# 自定义表单数据
custom_data = {
    'FullName': '李四',
    'ID': '110101199002022345',
    'Gender': '0',  # 女性
    'Married': 'No',  # 未婚
    'City': 'London',
    'Language': 'German',
    'Notes': '自定义填写内容'
}

# 填写表单
success = filler.fill_form(custom_data, 'outputs/custom_filled.pdf')
```

## 注意事项

1. **字段选项**: 选择字段必须使用预定义的选项值
2. **复选框字段**: 使用 `'Yes'` 或 `'No'` 最可靠
3. **文件路径**: 确保输入和输出文件路径正确
4. **编码**: 支持中文字符输入
5. **文件大小**: 填写后的文件大小约为 12KB

## 故障排除

### 问题：复选框无法选中
**原因**: 使用了错误的值格式
**解决**: 使用 `'Yes'` 或 `'No'`

### 问题：选择字段填写失败
**原因**: 字段值不在允许的选项中
**解决**: 检查字段选项，使用正确的值

### 问题：文件不存在
**原因**: PDF 文件路径错误
**解决**: 检查文件路径是否正确

### 问题：字段不匹配
**原因**: 字段名称错误
**解决**: 使用 `get_field_names()` 获取正确的字段名称

## 扩展功能

### 批量处理

```python
import os
from pdf_form_filler_practical import PDFFormFiller

# 批量填写多个表单
pdf_files = ['form1.pdf', 'form2.pdf', 'form3.pdf']
form_data = {
    'FullName': '张三',
    'ID': '110101199001011234',
    'Gender': '1',
    'Married': 'Yes',
    # ... 其他字段
}

for pdf_file in pdf_files:
    if os.path.exists(pdf_file):
        filler = PDFFormFiller(pdf_file)
        output_file = f'filled_{pdf_file}'
        success = filler.fill_form(form_data, output_file)
        print(f'{pdf_file}: {"成功" if success else "失败"}')
```

### 数据验证

```python
# 添加数据验证规则
def validate_id_number(id_number):
    """验证身份证号格式"""
    if len(id_number) != 18:
        return False
    # 添加更多验证逻辑
    return True

# 在填写前验证数据
if validate_id_number(form_data['ID']):
    success = filler.fill_form(form_data, output_path)
else:
    print('身份证号格式错误')
```

## 项目结构

```
pdf-form-service/
├── requirements.txt              # 项目依赖
├── pdf_form_filler_practical.py  # 实用 PDF 填写工具
├── fill_pdf_success.py           # 基础填写脚本
├── run_tests.py                  # 测试运行脚本
├── PDF_FORM_FILLING_GUIDE.md     # 使用指南
├── tests/                        # 测试目录
│   ├── __init__.py              # Python 包初始化
│   ├── test_pdf_filling.py      # PDF 填写功能测试
│   ├── test_config.py           # 配置测试
│   ├── test_api.sh              # API 测试脚本
│   └── test_api_curl.sh         # CURL API 测试脚本
├── outputs/                      # 输出目录
│   ├── Form.pdf                 # 原始表单
│   ├── Form_filled.pdf          # 填写结果
│   └── Form_filled_with_tool.pdf # 工具填写结果
├── app/                         # 应用目录
├── .venv/                       # 虚拟环境
└── ...                          # 其他项目文件
```

## 总结

通过使用 `fillpdf` 库，我们成功实现了 PDF 表单的自动填写功能，包括正确处理复选框字段。工具类提供了完整的字段验证、数据验证和错误处理功能，可以安全可靠地填写各种 PDF 表单。

主要特点：
- ✅ 支持文本、选择和复选框字段
- ✅ 自动字段验证和类型识别
- ✅ 智能布尔值转换
- ✅ 错误处理和日志记录
- ✅ 示例数据生成
- ✅ 中文支持
- ✅ 类型提示和文档
- ✅ 完整的测试套件
- ✅ 清晰的项目结构

### 修复的问题
- ✅ 修复了 Married 复选框字段无法正确填写的问题
- ✅ 添加了复选框字段的自动识别和处理
- ✅ 支持多种复选框值格式
- ✅ 改进了数据验证逻辑
- ✅ 整理了项目结构，将测试文件移到 tests 目录 