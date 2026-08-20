#!/usr/bin/env python3
"""带自动重试的 SCP 上传脚本"""
import os
import sys
import subprocess
import time

SERVER = "ubuntu@124.222.169.60"
LOCAL_FILE = "natapp_backup.sql.gz"
REMOTE_PATH = "/tmp/natapp_backup.sql.gz"
MAX_RETRIES = 10

def get_remote_size():
    """获取服务器上已上传的字节数"""
    cmd = f'ssh {SERVER} "stat -c %s {REMOTE_PATH} 2>/dev/null || echo 0"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return int(result.stdout.strip())

def upload_chunk(skip_bytes):
    """从指定位置继续上传"""
    local_size = os.path.getsize(LOCAL_FILE)
    if skip_bytes >= local_size:
        print(f"✅ 文件已完整上传！")
        return True

    print(f"📤 从 {skip_bytes / 1024 / 1024:.1f}MB 继续上传...")

    # 用 dd 跳过已上传部分，通过 SSH 追加到远程文件
    cmd = (
        f'dd if={LOCAL_FILE} bs=1M skip={skip_bytes // (1024*1024)} 2>/dev/null | '
        f'ssh {SERVER} "dd of={REMOTE_PATH} bs=1M seek={skip_bytes // (1024*1024)} 2>/dev/null"'
    )

    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    local_size = os.path.getsize(LOCAL_FILE)
    print(f"📦 本地文件大小: {local_size / 1024 / 1024:.1f}MB")

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n===== 尝试 {attempt}/{MAX_RETRIES} =====")

        remote_size = get_remote_size()
        print(f"🌐 服务器已有: {remote_size / 1024 / 1024:.1f}MB")

        if remote_size >= local_size:
            print("✅ 上传完成！")
            return 0

        if upload_chunk(remote_size):
            # 验证上传结果
            time.sleep(1)
            final_size = get_remote_size()
            if final_size >= local_size:
                print("✅ 上传并验证成功！")
                return 0

        print("⚠️  连接中断，5秒后重试...")
        time.sleep(5)

    print("❌ 达到最大重试次数，请检查网络")
    return 1

if __name__ == "__main__":
    sys.exit(main())
