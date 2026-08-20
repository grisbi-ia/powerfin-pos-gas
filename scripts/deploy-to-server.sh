#!/usr/bin/env bash
#
# deploy-to-server.sh — Subir cambios al pre-deploy del servidor de producción
# Desde: máquina de desarrollo (donde está el código fuente)
# Hacia: app@100.97.47.123 (Tailscale) o app@192.168.1.25 (LAN oficina):/home/app/powerfin-deploy/
#
# USO:
#   ./scripts/deploy-to-server.sh frontend         → sube pos/src/ (por Tailscale)
#   ./scripts/deploy-to-server.sh frontend local   → sube pos/src/ (por LAN oficina)
#   ./scripts/deploy-to-server.sh admin      → sube admin/src/
#   ./scripts/deploy-to-server.sh backend    → sube pos_backend/app/
#   ./scripts/deploy-to-server.sh fusion     → compila y sube JAR
#   ./scripts/deploy-to-server.sh all        → los 4
#
# Host por defecto: REMOTE (Tailscale). Alternativas:
#   ./scripts/deploy-to-server.sh <target> local     → IP LAN oficina (192.168.1.25)
#   DEPLOY_HOST=local ./scripts/deploy-to-server.sh <target>
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

# ── Servidor de producción — 2 rutas de acceso ────────────────────
# REMOTE → Tailscale (100.97.47.123): desde cualquier lugar
# LOCAL  → LAN oficina (192.168.1.25): usar si Tailscale está caído y estás en la oficina
REMOTE_SERVER="app@100.97.47.123"
LOCAL_SERVER="app@192.168.1.25"

# Selección de host: argumento opcional (local|remote) o env DEPLOY_HOST
DEPLOY_HOST="${DEPLOY_HOST:-remote}"

resolve_server() {
    case "$1" in
        local)  SERVER="$LOCAL_SERVER" ;;
        remote) SERVER="$REMOTE_SERVER" ;;
        *) echo "Host inválido: '$1' (usa 'local' o 'remote')" >&2; exit 1 ;;
    esac
}

# ── Verificación de conectividad antes de subir ───────────────────
check_connectivity() {
    info "Verificando conexión con $SERVER ..."
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" true 2>/dev/null; then
        warn "No se pudo conectar a $SERVER"
        if [ "$DEPLOY_HOST" = "remote" ]; then
            echo "  → ¿Tailscale está caído? Si estás en la oficina usá la IP local:"
            echo "      ./scripts/deploy-to-server.sh ${TARGET:-<target>} local"
        else
            echo "  → Verificá que estés en la red de la oficina (192.168.1.x)."
        fi
        exit 1
    fi
    ok "Conexión OK ($SERVER)"
}

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
    ssh "$SERVER" "mkdir -p $PRE_DEPLOY/frontend $PRE_DEPLOY/admin $PRE_DEPLOY/backend $PRE_DEPLOY/fusion"
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

    # Also sync alembic migrations (separate from app/)
    rsync -av \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        pos_backend/alembic/ "$SERVER:$PRE_DEPLOY/backend/alembic/"
    rsync -av pos_backend/alembic.ini "$SERVER:$PRE_DEPLOY/backend/"
    rsync -av pos_backend/requirements.txt "$SERVER:$PRE_DEPLOY/backend/"

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

# ── Admin ────────────────────────────────────────────────────
deploy_admin() {
    info "Subiendo admin a $SERVER:$PRE_DEPLOY/admin/"

    ensure_dirs
    rsync -av \
        --exclude='node_modules/' \
        --exclude='.svelte-kit/' \
        --exclude='build/' \
        --exclude='.env' \
        --exclude='.git/' \
        admin/src "$SERVER:$PRE_DEPLOY/admin/"
    # También subir package.json y config files para el build
    rsync -av \
        admin/package.json \
        admin/package-lock.json \
        admin/svelte.config.js \
        admin/vite.config.ts \
        admin/tsconfig.json \
        admin/postcss.config.js \
        admin/tailwind.config.js \
        "$SERVER:$PRE_DEPLOY/admin/"

    ok "Admin subido al pre-deploy"
}

# ── Main ────────────────────────────────────────────────────────────
TARGET="${1:-}"
HOST_ARG="${2:-$DEPLOY_HOST}"
resolve_server "$HOST_ARG"
DEPLOY_HOST="$HOST_ARG"  # host efectivo (para mensajes de ayuda)

usage() {
    echo "Uso: $0 [frontend|admin|backend|fusion|all] [local|remote]"
    echo ""
    echo "  1. $0 frontend    → sube pos/src/"
    echo "  2. $0 admin       → sube admin/src/ + config"
    echo "  3. $0 backend     → sube pos_backend/app/"
    echo "  4. $0 fusion      → compila y sube JAR"
    echo "  5. $0 all         → los 4 juntos"
    echo ""
    echo "  Host (opcional, por defecto remote/Tailscale):"
    echo "    $0 frontend local   → IP LAN oficina 192.168.1.25 (Tailscale caído)"
    echo "    DEPLOY_HOST=local $0 frontend   → lo mismo por variable de entorno"
    echo ""
    echo "  Luego en el servidor:"
    echo "    powerfin-gas pending"
    echo "    powerfin-gas deploy-all"
    echo "    powerfin-gas status"
}

if [ -z "$TARGET" ]; then
    usage
    exit 1
fi

check_connectivity

case "$TARGET" in
    frontend)
        deploy_frontend
        ;;
    admin)
        deploy_admin
        ;;
    backend)
        deploy_backend
        ;;
    fusion)
        deploy_fusion
        ;;
    all)
        deploy_frontend
        deploy_admin
        deploy_backend
        deploy_fusion
        echo ""
        info "Todo listo. En el servidor ejecutá:"
        echo "  powerfin-gas pending       ← ver qué llegó"
        echo "  powerfin-gas deploy-all    ← aplicar cambios"
        echo "  powerfin-gas status        ← verificar"
        ;;
    *)
        usage
        exit 1
        ;;
esac
