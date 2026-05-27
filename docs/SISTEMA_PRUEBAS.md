# Sistema de Pruebas — Powerfin POS

> Guía para probar el ciclo completo de venta sin hardware real.
> Usa un simulador TCP que emula el Wayne Fusion/Synergy.

---

## Arquitectura de pruebas

```
┌──────────────────┐     TCP :3012     ┌──────────────┐     REST :8090     ┌──────────────┐
│ Fusion Simulator │ ◄──────────────► │ FusionBridge  │ ◄────────────────► │ Powerfin POS │
│ (Python)         │                   │ (Quarkus)     │                    │ (SvelteKit)  │
│                  │                   │               │                    │              │
│ Emula surtidores │                   │ Puente TCP    │                    │ Interfaz     │
│ y protocolo      │                   │ a REST + SSE  │                    │ táctil PWA   │
└──────────────────┘                   └───────┬───────┘                    └──────┬───────┘
                                              │                                    │
                                              │ REST :8080                         │
                                              ▼                                    ▼
                                        ┌──────────────────────────────────────────┐
                                        │           PowerFin ERP (mock)            │
                                        │   APIs simuladas en TypeScript           │
                                        │   Login, clientes, turnos, despachos     │
                                        └──────────────────────────────────────────┘
```

**3 sistemas independientes, cada uno con UNA responsabilidad.**

---

## Requisitos

| Componente | Requiere | Verificar con |
|------------|----------|---------------|
| Fusion Simulator | Python 3 | `python3 --version` |
| FusionBridge | Java 21+, Maven | `java -version`, `./mvnw --version` |
| Powerfin POS | Node 20+ | `node --version` |

---

## Paso 1 — Iniciar el simulador Fusion (Terminal 1)

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
python3 tools/fusion_simulator.py --port 3012 --pumps 2
```

**Qué hace:** Abre un servidor TCP en `0.0.0.0:3012` que habla el protocolo Fusion nativo.
Emula 2 surtidores, cada uno con 4 mangueras (2 por lado).

**Salida esperada:**
```
╔══════════════════════════════════════════════╗
║   ⛽ FusionBridge SIMULATOR                  ║
║   Listening on 0.0.0.0:3012                 ║
║   Simulated pumps: 2                        ║
║   Hoses per pump:  4                        ║
║   Fueling duration: 8.0s                    ║
╚══════════════════════════════════════════════╝
```

**Parámetros opcionales:**
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--port 3012` | 3012 | Puerto TCP donde escucha |
| `--pumps 2` | 2 | Cantidad de surtidores simulados |

**Ciclo de despacho simulado:** 8 segundos total
- `0s` → AUTHORIZED
- `1s` → STARTING
- `2.5s` → FUELLING progreso 20%
- `4s` → FUELLING progreso 40%
- `5.5s` → FUELLING progreso 60%
- `7s` → FUELLING progreso 80%
- `8s` → IDLE + EVT_PUMP_NEW_TRANSACTION

El monto despachado es ~85% del preset (simula que el cliente no usó todo el monto).

---

## Paso 2 — Iniciar FusionBridge (Terminal 2)

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas/fusion-bridge
FUSION_IP=127.0.0.1 FUSION_PORT=3012 ./mvnw quarkus:dev
```

**Qué hace:** Arranca FusionBridge en modo desarrollo. Conecta al simulador en `127.0.0.1:3012`.
Expone REST y SSE en `http://0.0.0.0:8090`.

**Salida esperada:**
```
Listening on: http://0.0.0.0:8090
```

**Salida del simulador (Terminal 1):**
```
⚡ Client connected: 127.0.0.1:XXXXX
  ← ECHO
```

**Variables de entorno que controlan FusionBridge:**

| Variable | Default | Para simulación | Descripción |
|----------|---------|-----------------|-------------|
| `FUSION_IP` | `192.168.1.20` | `127.0.0.1` | IP del Fusion/Synergy |
| `FUSION_PORT` | `3011` | `3012` | Puerto TCP del Fusion |
| `POWERFIN_URL` | `http://localhost:8080` | — | URL del PowerFin ERP |
| `POWERFIN_API_KEY` | — | — | API key para PowerFin |
| `PRINTER_POLICY` | `ASK` | — | ALWAYS / ASK / NEVER |
| `PRINTER_ISLAND1_IP` | `192.168.1.31` | — | IP impresora isla 1 |
| `PRINTER_ISLAND2_IP` | `192.168.1.32` | — | IP impresora isla 2 |

**Modo producción (sin hot-reload):**
```bash
cd fusion-bridge
./mvnw package -DskipTests
FUSION_IP=127.0.0.1 FUSION_PORT=3012 java -jar target/quarkus-app/quarkus-run.jar
```

---

## Paso 3 — Iniciar Powerfin POS (Terminal 3)

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas/pos
export PATH=$HOME/.n/bin:$PATH
npm run dev -- --host
```

**Qué hace:** Arranca el servidor de desarrollo SvelteKit con acceso desde la red local.
El `--host` permite acceder desde celulares/tablets en la misma red.

**Salida esperada:**
```
VITE vX.X.X  ready in XXX ms
➜  Local:   http://localhost:5173/
➜  Network: http://192.168.1.XX:5173/
```

**Abrir en el navegador:** `http://localhost:5173`

**Credenciales de prueba:**
- Usuario: `carlos`
- PIN: `1234`

**Datos de prueba (placas):**
| Placa | Dueño | Precio |
|-------|-------|--------|
| `ABC1234` | Juan Carlos Pérez | VIP $1.100/L |
| `XYZ5678` | Transportes Andinos | STANDARD $1.500/L |
| `ZZZ9999` | — | No encontrado |

---

## Paso 4 — Ejecutar el Escenario 1 (venta normal)

```
1. Login: carlos / 1234
2. Abrir turno (efectivo inicial $0)
3. Dashboard: tocar Lado A del Surtidor 1
4. Wizard: seleccionar "Pistola 1 · Gasolina Super"
5. Wizard: ingresar placa "ABC1234" → Buscar
6. Wizard: confirmar "Juan Carlos Pérez (VIP)"
7. Wizard: seleccionar "Por Monto"
8. Wizard: ingresar $50.00 → Autorizar Despacho
9. Wizard: "✅ Autorizado. Volver al Inicio"
10. Dashboard: Lado A muestra 🟡 Autorizado
11. Esperar 8 segundos (simulación de despacho)
12. Dashboard: Lado A muestra 🟢 "Cobrar $XX.XX"
13. Tocar Lado A → wizard modo cobro
14. Seleccionar "Efectivo" → Confirmar Cobrar
15. ¿Ticket? → SÍ
16. ✅ Venta completada → Nueva Venta
```

---

## Verificaciones manuales

### Health de FusionBridge
```bash
curl -s http://localhost:8090/health | python3 -m json.tool
```

### Estado de surtidores
```bash
curl -s http://localhost:8090/api/dispensers | python3 -m json.tool
```

### SSE eventos en tiempo real
```bash
curl -N http://localhost:8090/api/events
```

### Probar simulador directamente (sin FusionBridge)
```bash
# ECHO
echo "00012|5|2||ECHO||||^" | nc localhost 3012

# Estado de surtidores
echo "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^" | nc localhost 3012

# Autorizar despacho
echo "00071|5|2||POST|REQ_PUMP_PRESET_ID_001|||TY=MONEY|VA=50.00|HO=1@1.100|PAY_TY=EFECTIVO|PAY_IN=OV=OV-001~CLI=0912345678|FTS=YES|^" | nc localhost 3012
```

---

## Ejecutar tests

### FusionBridge
```bash
cd fusion-bridge
./mvnw test
# 35 tests
```

### Powerfin POS
```bash
cd pos
export PATH=$HOME/.n/bin:$PATH
npm run test
# 41 tests

npm run check
# TypeScript + Svelte check
```

---

## Mapeo de puertos

| Puerto | Servicio | Descripción |
|--------|----------|-------------|
| 3011 | Fusion real | Wayne Synergy (hardware) |
| 3012 | Fusion Simulator | Emulador para pruebas |
| 8080 | PowerFin ERP | Backend de negocio |
| 8090 | FusionBridge | Puente REST/SSE |
| 5173 | Powerfin POS | SvelteKit dev server |
| 9100 | Impresora Isla 1 | ESC/POS térmica |
