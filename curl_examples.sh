#!/bin/bash

# PDF表单服务 API 调用示例
# 使用方法: bash curl_examples.sh

BASE_URL="http://localhost:8000"

echo "🚀 PDF表单服务 API 调用示例"
echo "================================"
echo ""

# 1. 健康检查
echo "1️⃣ 健康检查"
echo "curl -X GET \"$BASE_URL/health\""
curl -X GET "$BASE_URL/health"
echo ""
echo ""

# 2. 获取服务信息
echo "2️⃣ 获取服务信息"
echo "curl -X GET \"$BASE_URL/\""
curl -X GET "$BASE_URL/"
echo ""
echo ""

# 3. 解析PDF表单字段
echo "3️⃣ 解析PDF表单字段"
echo "curl -X POST \"$BASE_URL/api/v1/parse-form\" \\"
echo "  -H \"accept: application/json\" \\"
echo "  -H \"Content-Type: multipart/form-data\" \\"
echo "  -F \"file=@sample_form.pdf\""
echo ""
echo "注意: 需要先准备一个 sample_form.pdf 文件"
echo ""

# 4. 填充PDF表单
echo "4️⃣ 填充PDF表单"
echo "curl -X POST \"$BASE_URL/api/v1/fill-form\" \\"
echo "  -H \"accept: application/pdf\" \\"
echo "  -H \"Content-Type: multipart/form-data\" \\"
echo "  -F \"file=@sample_form.pdf\" \\"
echo "  -F 'form_data={\"fields\":[{\"name\":\"姓名\",\"value\":\"张三\"},{\"name\":\"邮箱\",\"value\":\"zhangsan@example.com\"}]}' \\"
echo "  --output filled_form.pdf"
echo ""
echo "注意: 需要先准备一个 sample_form.pdf 文件"
echo ""

# 5. 创建示例表单（如果接口存在）
echo "5️⃣ 创建示例表单"
echo "curl -X GET \"$BASE_URL/api/create-sample\" \\"
echo "  --output sample_form.pdf"
echo ""
echo ""

echo "📝 使用说明:"
echo "1. 确保服务已启动: python main.py"
echo "2. 准备测试用的 PDF 文件"
echo "3. 根据需要修改 BASE_URL 地址"
echo "4. 运行单个命令或整个脚本"
echo ""
echo "🔧 高级用法:"
echo "- 添加 -v 参数查看详细请求信息"
echo "- 添加 -H \"Authorization: Bearer token\" 进行认证"
echo "- 使用 -d 参数发送 JSON 数据" 