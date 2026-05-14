# Fusion Simulator

TCP server que emula el protocolo Wayne Fusion/Synergy para testing sin hardware real.

## Uso

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
