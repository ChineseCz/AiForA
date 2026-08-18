# 统一镜像：API + Worker（含 browser 队列）。
# 自建 playwright 环境（不依赖官方镜像，国内网络友好）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 安装 playwright 依赖的系统库（参考官方 Dockerfile）
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium 运行时依赖
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libxshmfence1 \
    # 字体支持（中文渲染）
    fonts-liberation fonts-noto-color-emoji fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用层缓存
COPY requirements.txt ./
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 装 playwright + 下载 chromium（约 300MB）
RUN pip install "playwright>=1.40" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn \
    && playwright install chromium --with-deps

# 拷贝代码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
