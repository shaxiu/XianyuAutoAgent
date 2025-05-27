#!/bin/bash
# 会话状态自动更新cron脚本
#
# 使用方法:
# 1. 确保此脚本有执行权限: chmod +x cron_update_sessions.sh
# 2. 将脚本添加到crontab中，例如每小时执行一次:
#    0 * * * * /path/to/cron_update_sessions.sh
#
# 或者您也可以手动运行此脚本。

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/cron_update_sessions.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 记录执行时间
echo "$(date): 开始执行会话状态更新..." >> "$LOG_FILE"

# 执行Python脚本
cd "$PROJECT_ROOT"
python3 "$SCRIPT_DIR/update_sessions.py" --hours 1 >> "$LOG_FILE" 2>&1

# 记录执行结果
if [ $? -eq 0 ]; then
    echo "$(date): 会话状态更新成功完成" >> "$LOG_FILE"
else
    echo "$(date): 会话状态更新失败，退出代码: $?" >> "$LOG_FILE"
fi

# 为脚本添加执行权限
chmod +x "$SCRIPT_DIR/cron_update_sessions.sh"

echo "$(date): 执行结束" >> "$LOG_FILE"
echo "--------------------" >> "$LOG_FILE" 