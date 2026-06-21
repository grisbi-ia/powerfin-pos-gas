#!/usr/bin/env bash
#
# deploy-to-server.sh — Subir cambios al pre-deploy del servidor de producción
# Desde: máquina de desarrollo (donde está el código fuente)
# Hacia: app@192.168.1.25:/home/app/powerfin-deploy/
#
# USO:
#   ./scripts/deploy-to-server.sh frontend   → sube pos/src/
#   ./scripts/deploy-to-server.sh backend    → sube pos_backend/app/
#   ./scripts/deploy-to-server.sh fusion     → compila y sube JAR
#   ./scripts/deploy-to-server.sh all        → los 3
#
# Luego en el servidor:
#   powerfin-gas pending       → ver qué llegó
#   powerfin-gas deploy-all    → aplicar
#   powerfin-gas status        → verificar
#
set -euo pipefail

# Resolver raíz del repo (el script está en scripts/)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

#LOCAL
##SERVER="app@192.168.1.25"

#REMOTE
SERVER="app@100.97.47.123"

PRE_DEPLOY="/home/app/powerfin-deploy"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()  { echo -e "${GREEN}✅ $1${NC}"; }
info(){ echo -e "${CYAN}→ $1${NC}"; }
warn(){ echo -e "${YELLOW}⚠️  $1${NC}"; }

# ── Asegurar que existen las carpetas en el servidor ────────────────
ensure_dirs() {
    ssh "$SERVER" "mkdir -p $PRE_DEPLOY/frontend $PRE_DEPLOY/backend $PRE_DEPLOY/fusion"
}

# ── Frontend ────────────────────────────────────────────────────────
deploy_frontend() {
    info "Subiendo frontend a $SERVER:$PRE_DEPLOY/frontend/"

    ensure_dirs
    rsync -av \
        --exclude='node_modules/' \
        --exclude='.svelte-kit/' \
        --exclude='build/' \
        --exclude='.env' \
        --exclude='.git/' \
        pos/src/ "$SERVER:$PRE_DEPLOY/frontend/"

    ok "Frontend subido al pre-deploy"
}

# ── Backend ─────────────────────────────────────────────────────────
deploy_backend() {
    info "Subiendo backend a $SERVER:$PRE_DEPLOY/backend/"

    ensure_dirs
    rsync -av \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache/' \
        --exclude='venv/' \
        --exclude='.env' \
        --exclude='.git/' \
        --exclude='*.log' \
        pos_backend/app/ "$SERVER:$PRE_DEPLOY/backend/"

    ok "Backend subido al pre-deploy"
}

# ── FusionBridge ────────────────────────────────────────────────────
deploy_fusion() {
    info "Compilando FusionBridge..."
    cd fusion-bridge
    ./mvnw package -DskipTests -q
    cd ..
    ok "FusionBridge compilado"

    info "Subiendo FusionBridge JAR a $SERVER:$PRE_DEPLOY/fusion/"
    ensure_dirs
    scp -r fusion-bridge/target/quarkus-app/* "$SERVER:$PRE_DEPLOY/fusion/"

    ok "FusionBridge subido al pre-deploy"
}

# ── Main ────────────────────────────────────────────────────────────
case "${1:-}" in
    frontend)
        deploy_frontend
        ;;
    backend)
        deploy_backend
        ;;
    fusion)
        deploy_fusion
        ;;
    all)
        deploy_frontend
        deploy_backend
        deploy_fusion
        echo ""
        info "Todo listo. En el servidor ejecutá:"
        echo "  powerfin-gas pending       ← ver qué llegó"
        echo "  powerfin-gas deploy-all    ← aplicar cambios"
        echo "  powerfin-gas status        ← verificar"
        ;;
    *)
        echo "Uso: $0 [frontend|backend|fusion|all]"
        echo ""
        echo "  1. $0 frontend    → sube pos/src/"
        echo "  2. $0 backend     → sube pos_backend/app/"
        echo "  3. $0 fusion      → compila y sube JAR"
        echo "  4. $0 all         → los 3 juntos"
        echo ""
        echo "  Luego en el servidor:"
        echo "    powerfin-gas pending"
        echo "    powerfin-gas deploy-all"
        echo "    powerfin-gas status"
        exit 1
        ;;
esac
