#!/usr/bin/env python3
"""
闲鱼AutoAgent管理后台启动脚本
"""
import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def main():
    # 获取当前脚本所在目录
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    
    # API目录
    api_dir = current_dir / "api"
    
    # 启动API服务器
    print("正在启动API服务器...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=api_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # 等待API服务器启动
    time.sleep(2)
    if api_process.poll() is not None:
        print("API服务器启动失败!")
        stderr = api_process.stderr.read().decode('utf-8')
        print(f"错误信息: {stderr}")
        return
    
    print("API服务器已启动，访问地址: http://localhost:8000")
    print("API文档地址: http://localhost:8000/docs")
    
    # 打开浏览器
    print("正在打开管理后台...")
    webbrowser.open("http://localhost:3000")
    
    try:
        # 保持脚本运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在关闭服务...")
        api_process.terminate()
        print("管理后台已关闭")

if __name__ == "__main__":
    main() 