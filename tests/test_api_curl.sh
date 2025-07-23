#!/bin/bash

echo "🧪 测试 PDF 表单服务 API"
echo "=========================="

# 检查服务是否运行
echo "🔍 检查服务状态..."
curl -s http://localhost:8000/health || {
    echo "❌ 服务未运行，请先启动服务：python start.py"
    exit 1
}

echo "✅ 服务正在运行"

# 创建测试数据
echo "📝 准备测试数据..."

# 多语言测试数据
cat > test_data.json << 'EOF'
[
  {
    "name": "Given Name",
    "type": "text",
    "value": "张三",
    "page": 1,
    "required": true
  },
  {
    "name": "Family Name", 
    "type": "text",
    "value": "李四",
    "page": 1,
    "required": true
  },
  {
    "name": "Address 1",
    "type": "text", 
    "value": "北京市朝阳区",
    "page": 1,
    "required": false
  },
  {
    "name": "Country",
    "type": "select",
    "value": "中国",
    "options": ["中国", "美国", "日本", "韩国"],
    "page": 1,
    "required": true
  },
  {
    "name": "Gender",
    "type": "radio",
    "value": "男",
    "options": ["男", "女"],
    "page": 1,
    "required": true
  },
  {
    "name": "Driving License",
    "type": "checkbox",
    "value": "是",
    "options": ["是", "否"],
    "page": 1,
    "required": false
  }
]
EOF

echo "✅ 测试数据已准备"

# 测试解析表单字段
echo ""
echo "🔍 测试解析表单字段..."
curl -X POST "http://localhost:8000/api/v1/parse-form" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@outputs/EDIT OoPdfFormExample.pdf" \
  -o parse_result.json

if [ $? -eq 0 ]; then
    echo "✅ 解析成功"
    echo "📋 解析结果："
    cat parse_result.json | python -m json.tool
else
    echo "❌ 解析失败"
fi

# 测试填充表单
echo ""
echo "🖊️ 测试填充表单..."
curl -X POST "http://localhost:8000/api/v1/fill-form" \
  -H "accept: application/pdf" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@outputs/EDIT OoPdfFormExample.pdf" \
  -F "form_data=@test_data.json" \
  --output filled_form.pdf

if [ $? -eq 0 ]; then
    echo "✅ 填充成功"
    echo "📄 填充后的文件：filled_form.pdf"
    ls -la filled_form.pdf
else
    echo "❌ 填充失败"
fi

# 清理临时文件
echo ""
echo "🧹 清理临时文件..."
rm -f test_data.json parse_result.json

echo ""
echo "🎉 测试完成！" 