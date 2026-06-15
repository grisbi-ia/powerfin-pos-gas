# Deploy — Producción

> Servidor: **192.168.1.25** · Usuario linux: **`app`** · OS: Debian 13

## ⚠️ Toda compilación se hace en desarrollo

El VPS de producción **no tiene** Maven, Node build tools ni compiladores Java.
Solo recibe archivos y los ejecuta.

- **POS Frontend:** el `npm run dev` del servidor compila en caliente al recibir `src/`.
- **POS Backend:** Python es interpretado, solo necesita el código `.py`.
- **FusionBridge:** se compila con `./mvnw package` en la **máquina de desarrollo**
  y solo se copia el JAR (`target/quarkus-app/`) al VPS.

---

## Resumen de servicios

| Servicio | Puerto | Tecnología | Systemd unit |
|----------|--------|------------|-------------|
| POS Backend | :8080 | Python / FastAPI | `pos-backend` |
| FusionBridge | :8090 | Java 21 / Quarkus | `fusion-bridge` |
| POS Frontend | :5173 | SvelteKit (dev) | `pos-frontend` |

---

## Desplegar actualizaciones

### POS Frontend — SvelteKit (cambios UI)

```bash
rsync -av pos/src/ app@192.168.1.25:/opt/powerfin/pos/pos/src/
ssh app@192.168.1.25 sudo systemctl restart pos-frontend
```

### POS Backend — Python FastAPI

```bash
rsync -av pos_backend/app/ app@192.168.1.25:/opt/powerfin/pos/backend/app/
ssh app@192.168.1.25 sudo systemctl restart pos-backend
```

### FusionBridge — Java Quarkus

```bash
cd fusion-bridge && ./mvnw package -DskipTests
scp -r target/quarkus-app/* app@192.168.1.25:/opt/powerfin/pos/fusion-bridge/
ssh app@192.168.1.25 sudo systemctl restart fusion-bridge
```

### Los 3 juntos

```bash
# Compilar (solo si FusionBridge cambió)
cd fusion-bridge && ./mvnw package -DskipTests && cd ..

# Subir código
rsync -av pos/src/                   app@192.168.1.25:/opt/powerfin/pos/pos/src/
rsync -av pos_backend/app/           app@192.168.1.25:/opt/powerfin/pos/backend/app/
scp -r fusion-bridge/target/quarkus-app/* app@192.168.1.25:/opt/powerfin/pos/fusion-bridge/

# Reiniciar
ssh app@192.168.1.25 'sudo systemctl restart pos-frontend pos-backend fusion-bridge'
```

---

## Verificar estado

```bash
# Health checks
curl -s http://192.168.1.25:8080/health   # Backend
curl -s http://192.168.1.25:8090/health   # FusionBridge
curl -s -o /dev/null -w '%{http_code}' http://192.168.1.25:5173  # Frontend (200 = OK)

# Services
ssh app@192.168.1.25 'sudo systemctl status pos-backend pos-frontend fusion-bridge'

# Logs en vivo
ssh app@192.168.1.25 'sudo journalctl -u pos-backend -u pos-frontend -u fusion-bridge -f'
```

---

## Notas

- Si `app` no tiene `sudo`, usar `root` para los `systemctl restart`.
- FusionBridge solo se recompila si cambió código Java (`.java`).
- POS Frontend corre en modo `npm run dev` — los cambios se reflejan al reiniciar.
- Para backup de BD: `ssh app@192.168.1.25 'pg_dump -U postgres powerfin_gas' > backup_$(date +%Y%m%d).sql`
