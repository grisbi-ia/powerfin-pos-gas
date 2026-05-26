#!/bin/bash
# Diagnóstico de flujo de estados: Simulador → FusionBridge → SSE → POS
# Muestra en tiempo real los eventos SSE y el estado REST en paralelo.

BRIDGE_URL="http://localhost:8090"
SIM_HOST="localhost"
SIM_PORT="3011"
DURATION=${1:-15}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  DIAGNÓSTICO DE FLUJO DE ESTADOS                           ║"
echo "║  Monitoreando ${DURATION}s tras enviar PRESET al simulador      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 1. Verificar que FusionBridge está conectado
echo "── 1. Verificando conexión FusionBridge ↔ Simulador ──"
HEALTH=$(curl -s "${BRIDGE_URL}/api/dispensers" 2>/dev/null)
if echo "$HEALTH" | grep -q "dispenserId"; then
    echo "   ✅ FusionBridge responde OK"
    FUSION_CONNECTED=$(echo "$HEALTH" | grep -o '"fusionConnected":[^,}]*' | cut -d: -f2)
    echo "   Fusion conectado: ${FUSION_CONNECTED}"
else
    echo "   ❌ FusionBridge NO responde. ¿Está corriendo quarkus:dev?"
    echo "   Respuesta: ${HEALTH}"
fi
echo ""

# 2. Estado inicial de los surtidores via REST
echo "── 2. Estado inicial (REST /api/dispensers) ──"
curl -s "${BRIDGE_URL}/api/dispensers" | python3 -m json.tool 2>/dev/null | head -30
echo ""

# 3. Enviar PRESET al simulador via TCP
echo "── 3. Enviando PRESET al simulador (Surtidor 1, manguera 1, \$20) ──"
PRESET_MSG="00073|5|2||POST|REQ_PUMP_PRESET_ID_001|||HO=1@1.150|GR=1|TY=MONEY|VA=20|PAY_TY=EFECTIVO|PAY_IN=OV=test~CLI=ABC123|^"
echo "   Enviando: ${PRESET_MSG}"
echo -n "${PRESET_MSG}" | nc -w 1 ${SIM_HOST} ${SIM_PORT}
echo ""
echo ""

# 4. Monitorear estado REST cada 500ms
echo "── 4. Monitoreo REST cada 500ms (${DURATION}s) ──"
echo "   (buscando cambios en status de surtidores)"
echo ""
PREV_STATUS=""
for i in $(seq 1 $((DURATION * 2))); do
    RESP=$(curl -s "${BRIDGE_URL}/api/dispensers" 2>/dev/null)
    # Extraer solo los estados
    STATUSES=$(echo "$RESP" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for d in data.get('dispensers',[]):
    print(f\"  Sur{d['dispenserId']}: {d['status']:12s} sub={d.get('subStatus',''):16s} preset=\${d.get('presetAmount',0):.2f}\")
" 2>/dev/null)
    if [ "$STATUSES" != "$PREV_STATUS" ]; then
        TIMESTAMP=$(date +%H:%M:%S.%3N)
        echo "   [${TIMESTAMP}]"
        echo "$STATUSES"
        PREV_STATUS="$STATUSES"
    fi
    sleep 0.5
done
echo ""

# 5. Intentar escuchar SSE por 3 segundos
echo "── 5. Escuchando eventos SSE (3s) ──"
timeout 3 curl -s -N "${BRIDGE_URL}/api/events" 2>/dev/null | while IFS= read -r line; do
    if [ -n "$line" ]; then
        echo "   SSE: ${line}"
    fi
done
echo ""

echo "── Diagnóstico completo ──"
