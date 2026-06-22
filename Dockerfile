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

# pip 换阿里云 PyPI 镜像（大包不再走国际源 pypi.org）
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

# CPU-only torch：本部署是 CPU 推理（BGE-M3/RapidOCR），无需 CUDA。
# 默认 PyPI 的 linux torch 是 CUDA 版，会拖 ~8GB（torch+nvidia-cu12+triton）撑爆磁盘。
# 先从上海交大 pytorch 镜像装 2.5.1+cpu（~190MB），其依赖走阿里云 PyPI；
# 它满足 requirements.txt 的 torch==2.5.1，后续不再拉 CUDA 版。
RUN pip install --no-cache-dir "torch==2.5.1+cpu" \
      --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cpu \
      --extra-index-url https://mirrors.aliyun.com/pypi/simple/ \
      --trusted-host mirror.sjtu.edu.cn --trusted-host mirrors.aliyun.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads

# P0-11 · 仅启动应用；DB 迁移由部署流程独立一次性执行（deploy.sh 的 `run --rm backend
# alembic upgrade head`），不再耦合进 CMD——避免多副本并发抢 DDL 锁 + 迁移失败把容器拖进
# restart 循环。
# P0-6 · workers 默认 1：2核4G 单机同时跑 pg+redis+backend+celery，且 backend/celery 各自
# 加载 BGE-M3(~1.5-2G/进程)，2 worker × 模型副本必 OOM。worker 数经 env 可调。
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-1}
