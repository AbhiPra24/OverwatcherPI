#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ ! -f "$SCRIPT_DIR/dashboard.pid" ]; then
    echo "Dashboard is not running (no PID file found)."
    exit 0
fi

PID=$(cat "$SCRIPT_DIR/dashboard.pid")

if kill -0 $PID 2>/dev/null; then
    echo "Stopping dashboard (PID $PID)..."
    kill $PID
    sleep 2
    if kill -0 $PID 2>/dev/null; then
        kill -9 $PID
    fi
    echo "Stopped."
else
    echo "Dashboard was not running (stale PID file)."
fi

rm -f "$SCRIPT_DIR/dashboard.pid"
