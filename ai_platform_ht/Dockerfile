# ==========================================
# 阶段 1：构建与编译阶段 (Builder)
# 目的：配置环境，将 Python 源码编译为字节码，并剔除原始文件
# ==========================================
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# 安装基础依赖
RUN apt update && apt install -y --no-install-recommends \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. 解压 conda 环境 (必须在这个阶段解压，以保证使用完全一致的 Python 版本进行编译)
COPY ttxz.tar.gz /tmp/ttxz.tar.gz
RUN mkdir -p /opt/ttxz && \
    tar -xzf /tmp/ttxz.tar.gz -C /opt/ttxz && \
    rm /tmp/ttxz.tar.gz

ENV PATH="/opt/ttxz/bin:$PATH"
RUN conda-unpack

# 2. 拷贝代码并进行编译
COPY . /app

# 3. 核心保护：将 .py 编译为 .pyc，并彻底删除所有 .py 源码和多余的压缩包
# -b 参数会将 .pyc 文件生成在原 .py 文件的同级目录下
RUN rm -f /app/ttxz.tar.gz && \
    python -m compileall -b . && \
    find . -name "*.py" -type f -delete && \
    find . -name "__pycache__" -type d -exec rm -rf {} +


# ==========================================
# 阶段 2：最终运行环境 (Final)
# 目的：只包含运行必须的环境和编译后的字节码，剥离调试工具
# ==========================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# 仅安装运行所需的基础依赖和 Chromium 浏览器 (支持 ARM64)
# 因为 Ubuntu 24.04 默认只有 snap 版 chromium，我们使用 xtradeb/apps PPA 安装原生的 deb 版本
RUN apt update && apt install -y --no-install-recommends \
    libsndfile1 \
    ca-certificates \
    software-properties-common \
    && add-apt-repository ppa:xtradeb/apps -y \
    && apt update && apt install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    && ln -s /usr/bin/chromedriver /usr/bin/chromium-browser || true \
    && ln -s /usr/bin/chromium /usr/bin/google-chrome || true \
    && rm -rf /var/lib/apt/lists/*

# 1. 从 builder 阶段直接拷贝处理好的 conda 环境
COPY --from=builder /opt/ttxz /opt/ttxz

# 2. 从 builder 阶段拷贝已经删除源码、仅剩 .pyc 的代码目录
COPY --from=builder /app /app

WORKDIR /app
ENV PATH="/opt/ttxz/bin:$PATH"

# 3. 权限优化：创建非 root 用户并配置权限
# 防止攻击者通过某种方式进去后拥有最高权限
RUN useradd -m appuser && chown -R appuser:appuser /app

# 4. 防 exec 优化：删除容器内常见的 shell
# 注意：删除 shell 后，后续将无法再使用 RUN 指令，所以必须放在最后一步
# RUN rm -f /bin/bash /bin/sh

# 切换到普通用户
USER appuser

# 5. 设置默认运行命令 (注意入口文件后缀变成了 .pyc)
CMD ["python", "main.pyc"]