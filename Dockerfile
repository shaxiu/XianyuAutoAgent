FROM python:3.10-alpine AS builder

WORKDIR /app

# 只安装构建所需的依赖
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    build-base \
    curl

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 第二阶段：最终镜像
FROM python:3.10-alpine

# 添加元数据标签
LABEL maintainer="coderxiu<coderxiu@qq.com>"
LABEL description="闲鱼AI客服机器人"
LABEL version="1.0"

# 设置时区和编码
ENV TZ=Asia/Shanghai \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 只安装运行时必要的包
RUN apk add --no-cache \
    tzdata \
    nodejs \
    npm \
    && npm install -g npm@10.2.4 \
    && npm cache clean --force \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo Asia/Shanghai > /etc/timezone \
    # 减小apk缓存
    && rm -rf /var/cache/apk/*

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 创建必要的目录
RUN mkdir -p data prompts

# 复制示例提示词文件并重命名为正式文件
COPY prompts/classify_prompt.txt prompts/classify_prompt.txt
COPY prompts/price_prompt.txt prompts/price_prompt.txt
COPY prompts/tech_prompt.txt prompts/tech_prompt.txt
COPY prompts/default_prompt.txt prompts/default_prompt.txt

# 只复制绝对必要的文件
COPY main.py XianyuAgent.py XianyuApis.py context_manager.py ./
COPY utils/ utils/
COPY static/ static/

# 容器启动时运行的命令
CMD ["python", "main.py"]
