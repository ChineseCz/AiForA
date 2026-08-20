#!/bin/bash
# 上传数据库备份到云服务器

SERVER_IP="124.222.169.60"
SERVER_USER="ubuntu"
FILE="natapp_backup.sql.gz"

echo "开始上传 $FILE 到服务器..."
scp "$FILE" "${SERVER_USER}@${SERVER_IP}:/tmp/"

if [ $? -eq 0 ]; then
    echo "✅ 上传成功！"
    echo ""
    echo "文件已上传到 /tmp/natapp_backup.sql.gz"
    echo "下一步：SSH 登录到服务器"
    echo "ssh ${SERVER_USER}@${SERVER_IP}"
    echo ""
    echo "然后执行："
    echo "sudo mkdir -p /data"
    echo "sudo mv /tmp/natapp_backup.sql.gz /data/"
else
    echo "❌ 上传失败，请检查网络或使用 WinSCP 手动上传"
fi
