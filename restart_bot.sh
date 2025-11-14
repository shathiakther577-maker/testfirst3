#!/bin/bash
# Скрипт для перезапуска бота

cd /root/whitecoin
source venv/bin/activate
export PYTHONPATH=/root/whitecoin:$PYTHONPATH

# Останавливаем старый процесс
pkill -f "start_bot.py" 2>/dev/null
sleep 2

# Запускаем новый
nohup python start_bot.py > /tmp/telegram_bot_final.log 2>&1 &

echo "Bot restarted. PID: $!"
sleep 3
ps aux | grep "start_bot" | grep python | grep -v grep

