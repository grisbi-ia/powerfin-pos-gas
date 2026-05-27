# Testing Tools

## PowerFin Server Simulator

Servidor HTTP REST que emula los endpoints `/api/pos/*` de PowerFin ERP.
**Persiste en archivo JSON** — estado compartido entre todos los dispositivos.

```bash
python3 tools/powerfin_server.py --port 8080
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--port` | 8080 | Puerto HTTP |
| `--host` | 0.0.0.0 | Dirección de bind |

### Usuarios de prueba

| Usuario | PIN | Role |
|---------|-----|------|
| `carlos` | `1234` | DISPATCHER |
| `maria` | `1234` | DISPATCHER |
| `pedro` | `1234` | DISPATCHER |

### Verificar

```bash
curl http://localhost:8080/api/pos/config
curl -X POST http://localhost:8080/api/pos/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"carlos","pin":"1234"}'
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/pos/auth/login` | Login con PIN |
| GET | `/api/pos/config` | Layout, precios, métodos de pago |
| GET | `/api/pos/customers?q=` | Búsqueda de clientes |
| POST | `/api/pos/customers` | Registro de cliente nuevo |
| POST | `/api/pos/vehicles/lookup` | Búsqueda por placa |
| GET | `/api/pos/prices?customerId=&gradeId=` | Precio según lista |
| POST | `/api/pos/shifts/open` | Abrir turno |
| GET | `/api/pos/shifts/current` | Turno activo |
| POST | `/api/pos/shifts/{id}/close` | Cerrar turno |
| POST | `/api/pos/dispatches` | Crear orden de despacho |
| GET | `/api/pos/shifts/{id}/dispatches` | Órdenes del turno (reconciliación) |
| POST | `/api/pos/dispatches/{id}/complete` | Completar despacho |
| POST | `/api/pos/dispatches/{id}/collect` | Cobrar |
| POST | `/api/pos/dispatches/{id}/cancel` | Cancelar |

---

## Fusion Simulator

TCP server que emula el protocolo Wayne Fusion/Synergy para testing sin hardware real.

```bash
python3 tools/fusion_simulator.py --port 3012 --pumps 2
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--port` | 3012 | Puerto TCP donde escucha |
| `--pumps` | 2 | Número de surtidores simulados |

Cada surtidor tiene 4 mangueras (2 por lado).

## Probar conectividad

```bash
# ECHO keep-alive
echo "00012|5|2||ECHO||||^" | nc localhost 3012

# Estado de surtidores
echo "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^" | nc localhost 3012

# Autorizar despacho
echo "00071|5|2||POST|REQ_PUMP_PRESET_ID_001|||TY=MONEY|VA=50.00|HO=1@1.100|PAY_TY=EFECTIVO|PAY_IN=OV=OV-001~CLI=0912345678|FTS=YES|^" | nc localhost 3012
```

## Ciclo de vida simulado

```
IDLE → (preset) → AUTHORIZED → (1s) → STARTING → FUELLING
  → progreso cada 1.5s (5 updates)
  → IDLE + EVT_PUMP_NEW_TRANSACTION
```

El monto despachado es ~85% del preset (simula que el cliente no usó todo).

## Handshake de pago

```
REQ_PAYMENT_TRANSACTION_LOCK   → RES_PAYMENT_TRANSACTION_LOCK (ST=OK)
REQ_PAYMENT_CLEAR_SALE         → RES_PAYMENT_CLEAR_SALE (ST=OK)
REQ_PAYMENT_TRANSACTION_UNLOCK → RES_PAYMENT_TRANSACTION_UNLOCK (ST=OK)
```

## Para usar con FusionBridge

Configurar `application.properties`:

```properties
fusion.ip=127.0.0.1
fusion.port=3012
```
