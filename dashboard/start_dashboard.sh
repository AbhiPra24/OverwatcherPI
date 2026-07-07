#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ -f "$SCRIPT_DIR/dashboard.pid" ]; then
    if kill -0 $(cat "$SCRIPT_DIR/dashboard.pid") 2>/dev/null; then
        echo "Dashboard is already running (PID $(cat "$SCRIPT_DIR/dashboard.pid"))."
        exit 1
    fi
fi

source "$SCRIPT_DIR/venv/bin/activate"

nohup streamlit run "$SCRIPT_DIR/app.py" --server.address 0.0.0.0 --server.port 8501 --server.headless true > "$SCRIPT_DIR/dashboard.log" 2>&1 &
PID=$!
echo $PID > "$SCRIPT_DIR/dashboard.pid"

LAN_IP=$(hostname -I | awk '{print $1}')
echo "Dashboard started in background (PID $PID)."
echo "Access it on your LAN at: http://$LAN_IP:8501"
