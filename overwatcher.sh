#!/bin/bash
# Unified management script for OverwatcherPI

if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root (e.g. sudo ./overwatcher.sh <command>)"
  exit 1
fi

ACTION=$1
SERVICES="overwatcher overwatcher-sniffer overwatcher-dashboard overwatcher-caddy"
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

install_services() {
    echo "Installing systemd services..."
    
    # Generate Caddy service dynamically to match the current directory
    cat <<EOF > "$DIR/overwatcher-caddy.service"
[Unit]
Description=OverwatcherPI Caddy Reverse Proxy
After=network.target overwatcher-dashboard.service

[Service]
Type=simple
User=root
WorkingDirectory=$DIR/dashboard
ExecStart=/usr/bin/caddy run --config $DIR/dashboard/Caddyfile
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Copy all services
    cp "$DIR/overwatcher.service" /etc/systemd/system/
    cp "$DIR/overwatcher-sniffer.service" /etc/systemd/system/
    cp "$DIR/overwatcher-dashboard.service" /etc/systemd/system/
    cp "$DIR/overwatcher-caddy.service" /etc/systemd/system/
    
    # Reload and enable
    systemctl daemon-reload
    systemctl enable $SERVICES
    systemctl restart $SERVICES
    echo "All services installed and started successfully!"
}

if [ "$ACTION" == "install" ]; then
    install_services
    exit 0
fi

if [[ ! "$ACTION" =~ ^(start|stop|restart|status)$ ]]; then
    echo "Usage: sudo ./overwatcher.sh [start|stop|restart|status|install]"
    echo "  install : Copies unit files to systemd, enables them on boot, and starts them."
    echo "  start   : Starts all components."
    echo "  stop    : Stops all components."
    echo "  restart : Restarts all components."
    echo "  status  : Shows the running state of all components."
    exit 1
fi

echo "Executing '$ACTION' for all OverwatcherPI services..."
systemctl $ACTION $SERVICES

if [ "$ACTION" == "status" ]; then
    echo ""
    echo "=== OVERWATCHER COMPONENT STATUS ==="
    for svc in $SERVICES; do
        IS_ACTIVE=$(systemctl is-active $svc)
        if [ "$IS_ACTIVE" == "active" ]; then
            printf "%-30s \e[32m%s\e[0m\n" "$svc" "$IS_ACTIVE"
        else
            printf "%-30s \e[31m%s\e[0m\n" "$svc" "$IS_ACTIVE"
        fi
    done
    echo "===================================="
fi
