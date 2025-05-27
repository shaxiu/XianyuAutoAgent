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
import logging
import socket
import signal
import platform

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_data_directories():
    """确保数据目录存在"""
    data_dir = Path(__file__).parent.parent / "data"
    logs_dir = Path(__file__).parent.parent / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    logger.info(f"确保数据目录存在: {data_dir}, {logs_dir}")

def check_port_available(port):
    """检查端口是否可用"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        available = True
    except socket.error:
        available = False
    finally:
        s.close()
    return available

def kill_process_on_port(port):
    """杀死占用指定端口的进程"""
    try:
        if platform.system() == "Windows":
            # Windows系统
            cmd = f"netstat -ano | findstr :{port}"
            result = subprocess.check_output(cmd, shell=True).decode('utf-8')
            if 'LISTENING' in result:
                pid = result.strip().split()[-1]
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    logger.info(f"已终止占用端口 {port} 的进程 (PID: {pid})")
                    return True
                except:
                    logger.warning(f"无法终止进程 {pid}")
                    return False
        else:
            # Unix系统 (Linux/Mac)
            cmd = f"lsof -i :{port} -t"
            try:
                pid = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
                if pid:
                    os.kill(int(pid), signal.SIGKILL)
                    logger.info(f"已终止占用端口 {port} 的进程 (PID: {pid})")
                    return True
            except:
                pass
    except Exception as e:
        logger.error(f"释放端口时出错: {e}")
    return False

def main():
    API_PORT = 8090
    
    # 获取当前脚本所在目录
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    
    # 确保数据目录存在
    ensure_data_directories()
    
    # 检查端口是否可用
    if not check_port_available(API_PORT):
        logger.warning(f"端口 {API_PORT} 已被占用，尝试释放...")
        if not kill_process_on_port(API_PORT):
            logger.error(f"无法释放端口 {API_PORT}，请手动关闭占用该端口的应用后重试")
            return
        # 等待端口释放
        time.sleep(1)
    
    # API目录
    api_dir = current_dir / "api"
    
    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    
    # 启动API服务器
    logger.info("正在启动API服务器...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--host", "127.0.0.1", f"--port={API_PORT}"],
        cwd=api_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
    )
    
    # 等待API服务器启动，增加等待时间
    time.sleep(5)
    
    # 检查API服务器是否成功启动
    if api_process.poll() is not None:
        logger.error("API服务器启动失败!")
        stderr = api_process.stderr.read()
        logger.error(f"错误信息: {stderr}")
        return
    
    # 使用请求检查API是否可访问
    try:
        import requests
        for i in range(3):  # 尝试3次
            try:
                response = requests.get(f"http://127.0.0.1:{API_PORT}/")
                if response.status_code == 200:
                    logger.info("API服务器已成功启动并可访问")
                    break
            except requests.exceptions.ConnectionError:
                logger.info(f"API服务器尚未就绪，等待中... ({i+1}/3)")
                time.sleep(2)
    except ImportError:
        logger.warning("未安装requests库，跳过API可访问性检查")
    
    logger.info(f"API服务器已启动，访问地址: http://127.0.0.1:{API_PORT}")
    logger.info(f"API文档地址: http://127.0.0.1:{API_PORT}/docs")
    
    # 打开浏览器
    logger.info("正在打开管理后台...")
    webbrowser.open("http://localhost:3000")
    
    try:
        # 保持脚本运行并实时监控API服务器输出
        for line in iter(api_process.stdout.readline, ''):
            print(line, end='')
    except KeyboardInterrupt:
        logger.info("正在关闭服务...")
        api_process.terminate()
        logger.info("管理后台已关闭")

if __name__ == "__main__":
    main() 