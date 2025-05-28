FROM python:3.8

# ---------------------------
# 1. 设置国内Apt源，加速系统包安装
# ---------------------------
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian stable main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian stable-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security stable-security main contrib non-free" >> /etc/apt/sources.list && \
    rm -rf /etc/apt/sources.list.d/* && \
    apt-get update && \
    apt-get install -y curl gnupg && \
# ---------------------------
# 2. 安装Node.js 18（官方推荐方式）
# ---------------------------
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    node -v && npm -v && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ---------------------------
# 3. 用清华PyPI源加速pip，全局配置
# ---------------------------
RUN mkdir -p /root/.pip && \
    echo '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple' > /root/.pip/pip.conf

# 设置容器内工作目录
WORKDIR /app

# 复制所有项目文件到镜像
COPY . .

# ---------------------------
# 4. 升级pip、安装Python依赖（走清华PyPI源）
# ---------------------------
RUN pip install --upgrade pip && pip install -r requirements.txt

# 启动主程序
CMD ["python", "main.py"]
