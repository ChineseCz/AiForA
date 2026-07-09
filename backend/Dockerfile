# API 镜像：只装 API 依赖，绝不含 playwright/浏览器。
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 拷贝代码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

# 非 root 运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
