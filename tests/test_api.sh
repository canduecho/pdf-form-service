#!/bin/bash

# PDF表单服务 API 测试脚本
# 使用方法: bash test_api.sh

BASE_URL="http://localhost:8000"

echo "🧪 PDF表单服务 API 测试"
echo "========================"
echo ""

# 检查服务是否运行
echo "🔍 检查服务状态..."
if curl -s -f "$BASE_URL/health" > /dev/null; then
  echo "✅ 服务正在运行"
else
  echo "❌ 服务未运行，请先启动服务: python main.py"
  exit 1
fi

echo ""

# 1. 健康检查
echo "1️⃣ 健康检查"
response=$(curl -s -X GET "$BASE_URL/health")
echo "响应: $response"
echo ""

# 2. 获取服务信息
echo "2️⃣ 获取服务信息"
response=$(curl -s -X GET "$BASE_URL/")
echo "响应: $response"
echo ""

# 3. 测试文件上传（如果有测试文件）
if [ -f "sample_form.pdf" ]; then
  echo "3️⃣ 测试PDF表单解析"
  response=$(curl -s -X POST "$BASE_URL/api/v1/parse-form" \
    -H "accept: application/json" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@sample_form.pdf")
  echo "响应: $response"
else
  echo "3️⃣ 跳过PDF解析测试（缺少 sample_form.pdf 文件）"
  echo "   提示: 可以创建一个简单的PDF文件进行测试"
fi

echo ""
echo "✅ 测试完成"
echo ""
echo "📝 更多测试命令请查看 API_CURL_EXAMPLES.md" 