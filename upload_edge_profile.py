#!/usr/bin/env python3
"""上传 Edge profile 到服务器"""
import paramiko
import sys
from pathlib import Path

HOST = "124.222.169.60"
USER = "ubuntu"
PASSWORD = "1308Huang"
LOCAL_FILE = "backend/edge_profile.tar.gz"
REMOTE_PATH = "/data/app/backend/edge_profile.tar.gz"

def upload():
    local_path = Path(LOCAL_FILE)
    if not local_path.exists():
        print(f"错误：本地文件不存在 {local_path.absolute()}")
        sys.exit(1)

    size_mb = local_path.stat().st_size / 1024 / 1024
    print(f"准备上传 {LOCAL_FILE} ({size_mb:.2f} MB) 到 {HOST}:{REMOTE_PATH}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print("连接服务器...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)

        sftp = ssh.open_sftp()
        print("开始上传...")

        def progress(transferred, total):
            pct = (transferred / total) * 100
            print(f"\r上传进度: {pct:.1f}% ({transferred}/{total} bytes)", end="")

        sftp.put(str(local_path), REMOTE_PATH, callback=progress)
        print("\n上传成功！")

        sftp.close()
        ssh.close()

    except Exception as e:
        print(f"\n上传失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    upload()
