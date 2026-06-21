FROM python:3.11-slim

WORKDIR /app

# 大陆构建提速 + 可复现：apt 换阿里云 Debian 镜像（兼容 bullseye 旧 sources.list
# 与 bookworm deb822 debian.sources 两种格式）。镜像加速器只管拉镜像层、不管 build 内 apt。
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# pip 换阿里云 PyPI 镜像（torch 等大包不再走国际源 pypi.org）
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads

# Run DB migrations then start the server
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
