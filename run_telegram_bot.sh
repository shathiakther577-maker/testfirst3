#!/bin/bash
cd /root/whitecoin
source venv/bin/activate
export PYTHONPATH=/root/whitecoin:$PYTHONPATH
python handlers/telegram_polling.py

