#!/usr/bin/env python3
"""带自动重试的 SFTP 上传脚本（纯 Python，无需外部命令）"""
import os
import sys
import time
import getpass

try:
    import paramiko
except ImportError:
    print("❌ 缺少 paramiko 库，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

SERVER = "124.222.169.60"
USERNAME = "ubuntu"
LOCAL_FILE = "natapp_backup_new.sql.gz"
REMOTE_PATH = "/tmp/natapp_backup.sql.gz"
MAX_RETRIES = 20
CHUNK_SIZE = 1024 * 1024  # 1MB per chunk

def upload_with_resume(sftp, local_path, remote_path):
    """断点续传上传"""
    local_size = os.path.getsize(local_path)

    # 检查远程文件大小
    try:
        remote_size = sftp.stat(remote_path).st_size
        print(f"🌐 服务器已有: {remote_size / 1024 / 1024:.1f}MB / {local_size / 1024 / 1024:.1f}MB")
    except FileNotFoundError:
        remote_size = 0
        print(f"📦 本地文件大小: {local_size / 1024 / 1024:.1f}MB")

    if remote_size >= local_size:
        print("✅ 文件已完整上传！")
        return True

    # 从断点继续上传
    print(f"📤 从 {remote_size / 1024 / 1024:.1f}MB 继续上传...")

    with open(local_path, 'rb') as local_file:
        local_file.seek(remote_size)  # 跳到断点位置

        with sftp.open(remote_path, 'ab') as remote_file:  # 追加模式
            uploaded = remote_size
            start_time = time.time()

            while uploaded < local_size:
                chunk = local_file.read(CHUNK_SIZE)
                if not chunk:
                    break

                remote_file.write(chunk)
                uploaded += len(chunk)

                # 显示进度
                percent = uploaded / local_size * 100
                speed = uploaded / (time.time() - start_time) / 1024 / 1024
                print(f"\r进度: {percent:.1f}% ({uploaded / 1024 / 1024:.1f}MB) - {speed:.2f}MB/s", end='', flush=True)

    print()
    return True

def main():
    if not os.path.exists(LOCAL_FILE):
        print(f"❌ 本地文件不存在: {LOCAL_FILE}")
        return 1

    password = getpass.getpass(f"请输入 {USERNAME}@{SERVER} 的密码: ")

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n===== 尝试 {attempt}/{MAX_RETRIES} =====")

        try:
            # 建立 SSH 连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(SERVER, username=USERNAME, password=password, timeout=30)

            # 建立 SFTP 会话
            sftp = ssh.open_sftp()

            # 上传
            if upload_with_resume(sftp, LOCAL_FILE, REMOTE_PATH):
                # 验证最终大小
                local_size = os.path.getsize(LOCAL_FILE)
                remote_size = sftp.stat(REMOTE_PATH).st_size

                if remote_size == local_size:
                    print(f"✅ 上传成功并验证通过！")
                    sftp.close()
                    ssh.close()
                    return 0
                else:
                    print(f"⚠️  大小不匹配，继续重试...")

            sftp.close()
            ssh.close()

        except Exception as e:
            print(f"\n❌ 错误: {e}")
            print("⚠️  5秒后重试...")
            time.sleep(5)

    print("\n❌ 达到最大重试次数")
    return 1

if __name__ == "__main__":
    sys.exit(main())
