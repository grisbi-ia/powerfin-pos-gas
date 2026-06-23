# Deploy rápido — Subir cambios a producción

> Servidor: **192.168.1.25** · Usuario: **`app`** · OS: Debian 13

## ⚠️ Regla de oro

**Toda compilación se hace en desarrollo.** Producción solo recibe archivos y los ejecuta.

Nunca subas:
- `__pycache__/`, `*.pyc`, `.pytest_cache/` — caché Python
- `node_modules/`, `.svelte-kit/`, `build/` — dependencias y build de Node
- `.env`, `.git/` — configuración y repositorio
- `venv/`, `target/` (fuente) — entornos virtuales y compilación Java

---

## Flujo de deploy (2 etapas)

```
┌─────────────────────┐       ┌──────────────────────────────┐
│  Máquina desarrollo  │  rsync │  Servidor producción          │
│                       │ ─────→ │  /home/app/powerfin-deploy/   │  ← pre-deploy
│  deploy-to-server.sh │       │                              │
└─────────────────────┘       │  powerfin-gas deploy-all     │
                               │  (copia a /opt/powerfin/pos/) │
                               └──────────────────────────────┘
```

### Etapa 1 — Desde desarrollo (subir al pre-deploy)

```bash
# Subir solo lo que cambió
./scripts/deploy-to-server.sh frontend
./scripts/deploy-to-server.sh admin
./scripts/deploy-to-server.sh backend
./scripts/deploy-to-server.sh fusion      # compila + sube JAR

# O todo junto
./scripts/deploy-to-server.sh all
```

### Etapa 2 — Desde el servidor (aplicar cambios)

```bash
ssh app@192.168.1.25

powerfin-gas pending       # ver qué archivos llegaron
powerfin-gas deploy-all    # copiar a /opt/powerfin/pos/ y reiniciar
powerfin-gas status        # verificar health checks
```

---

## Comandos disponibles en el servidor

```bash
# Deploy
powerfin-gas deploy-frontend    powerfin-gas deploy-admin
powerfin-gas deploy-backend     powerfin-gas deploy-fusion
powerfin-gas deploy-all

# Control de servicios
powerfin-gas start-frontend     powerfin-gas stop-frontend      powerfin-gas restart-frontend
powerfin-gas start-admin        powerfin-gas stop-admin         powerfin-gas restart-admin
powerfin-gas start-backend      powerfin-gas stop-backend       powerfin-gas restart-backend
powerfin-gas start-fusion       powerfin-gas stop-fusion         powerfin-gas restart-fusion
powerfin-gas start-all          powerfin-gas stop-all            powerfin-gas restart-all

# Monitoreo
powerfin-gas status             powerfin-gas logs
powerfin-gas logs-tail 100      powerfin-gas pending
powerfin-gas clean all          powerfin-gas help
```

---

## Instalación inicial (primera vez en el servidor)

```bash
# Copiar el binario al servidor
scp scripts/powerfin-gas app@192.168.1.25:/tmp/
ssh app@192.168.1.25
sudo mv /tmp/powerfin-gas /usr/local/bin/powerfin-gas
sudo chmod +x /usr/local/bin/powerfin-gas

# Crear carpeta de pre-deploy
mkdir -p /home/app/powerfin-deploy/{frontend,admin,backend,fusion}
```

---

## Rollback rápido

Si algo sale mal y necesitás revertir:

```bash
# Restaurar código desde git
cd /opt/powerfin/pos && git checkout <tag-anterior>
# ... repetir rsync de cada componente
```

---

## Estructura en producción

```
/home/app/powerfin-deploy/    ← pre-deploy (buffer antes de aplicar)
├── frontend/
├── admin/
├── backend/
└── fusion/

/opt/powerfin/pos/             ← aplicación en ejecución
├── backend/
│   ├── venv/                  ← NO TOCAR
│   ├── .env                   ← NO TOCAR
│   └── app/                   ← código Python
├── fusion-bridge/
│   └── quarkus-app/           ← JAR compilado
├── pos/
│   ├── node_modules/          ← NO TOCAR
│   ├── .env                   ← NO TOCAR
│   └── src/                   ← código SvelteKit (POS)
└── admin/
    ├── node_modules/          ← NO TOCAR
    ├── .env                   ← NO TOCAR
    └── src/                   ← código SvelteKit (Admin)
```
