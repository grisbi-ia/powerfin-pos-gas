#!/bin/bash
# start.sh — Arrancar todos los servicios Powerfin POS
# Uso: ./start.sh [servicio]
#   sin args      → arranca todo
#   pos           → solo POS frontend
#   bridge        → solo FusionBridge
#   backend       → solo POS Backend (FastAPI :8080)
#   stop          → detiene todo

set -e
cd "$(dirname "$0")"

stop_all() {
    echo "Deteniendo servicios..."
    pkill -f "powerfin_server.py" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "quarkus" 2>/dev/null || true
    pkill -f "fusion-bridge" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    sleep 1
    echo "✓ Servicios detenidos"
}

start_backend() {
    echo -n "POS Backend (8080)... "
    cd pos_backend
    source venv/bin/activate
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8080 --log-level warning > /tmp/pos_backend.log 2>&1 &
    cd ..
    for i in $(seq 1 5); do
        sleep 1
        if curl -s http://localhost:8080/health > /dev/null 2>&1; then
            echo "✓"
            return
        fi
    done
    echo "✗ Error al iniciar"
}

start_bridge() {
    echo -n "FusionBridge (8090)... "
    cd fusion-bridge
    FUSION_IP=192.168.1.20 ./mvnw quarkus:dev > /tmp/fusionbridge.log 2>&1 &
    cd ..
    for i in $(seq 1 20); do
        sleep 2
        if curl -s http://localhost:8090/health > /dev/null 2>&1; then
            echo "✓ (${i}x2s)"
            return
        fi
    done
    echo "✗ Timeout"
}

start_pos() {
    echo -n "POS (5173)... "
    cd pos
    npx vite dev --host 0.0.0.0 &
    cd ..
    sleep 4
    if curl -s http://localhost:5173/ > /dev/null 2>&1; then
        echo "✓"
    else
        echo "✗ Error al iniciar"
    fi
}

status() {
    echo ""
    echo "=== Estado de servicios ==="
    curl -s -o /dev/null -w "PowerFin (8080):    %{http_code}\n" http://localhost:8080/api/pos/config 2>/dev/null || echo "PowerFin (8080):    down"
    curl -s -o /dev/null -w "FusionBridge (8090): %{http_code}\n" http://localhost:8090/health 2>/dev/null || echo "FusionBridge (8090): down"
    curl -s -o /dev/null -w "POS (5173):         %{http_code}\n" http://localhost:5173/ 2>/dev/null || echo "POS (5173):         down"
    echo ""
    echo "POS URL: http://192.168.1.113:5173"
    echo "Login:   carlos / 1234"
}

case "${1:-all}" in
    stop)
        stop_all
        ;;
    status)
        status
        ;;
    powerfin)
        echo "⚠️  'powerfin' es obsoleto — usa 'backend'"
        start_backend
        status
        ;;
    backend)
        start_backend
        status
        ;;
    bridge)
        start_bridge
        status
        ;;
    pos)
        start_pos
        status
        ;;
    all)
        stop_all 2>/dev/null
        echo "Arrancando todos los servicios..."
        start_backend
        start_pos
        # FusionBridge arranca aparte (tarda más)
        echo ""
        echo "Para FusionBridge ejecuta:  ./start.sh bridge"
        status
        ;;
    *)
        echo "Uso: ./start.sh [all|pos|bridge|powerfin|stop|status]"
        ;;
esac
