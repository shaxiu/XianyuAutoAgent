#!/bin/bash

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

echo "虚拟环境设置完成，所有依赖已安装"
