# Wayne Fusion Simulator

Simulador TCP del protocolo Wayne Fusion/Synergy (FCC). Emula 4 surtidores con
el protocolo completo pipe-delimited `^`. Sin dependencias — solo Node.js.

## Instalación

```bash
# Copiar al servidor
scp fusion-simulator/ root@192.168.1.10:/opt/fusion-simulator/

# Instalar systemd unit
sudo cp /opt/fusion-simulator/fusion-simulator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fusion-simulator
sudo systemctl start fusion-simulator
```

## Uso directo

```bash
node server.js              # Puerto 3011 (default)
node server.js --port 3012  # Puerto personalizado
```

## Estados del surtidor

```
IDLE ──PRESET──► AUTHORIZED ──(4s)──► STARTING ──(2s)──► FUELLING ──(6s)──► IDLE
                     ▲                                            │
                     └── CLEAR_PRESET ────────────────────────────┘
```

Durante FUELLING se emiten `EVT_PUMP_DELIVERY_PROGRESS` cada 1.5s con
volumen/monto acumulado.

## Pruebas rápidas

```bash
# 1. ECHO (keep-alive)
echo -n "00012|5|2||ECHO||||^" | nc localhost 3011

# 2. Estado de todos los surtidores
echo -n "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^" | nc localhost 3011

# 3. Ciclo completo de venta (suscribirse + autorizar)
{
  echo "00040|5|2||SUBSCRIBE|EVT_PUMP_STATUS_CHANGE_ID_000||||^"
  sleep 0.5
  echo "00068|5|2||POST|REQ_PUMP_PRESET_ID_001|||TY=MONEY|VA=20.00|HO=1|PAY_TY=EFECTIVO|PAY_IN=OV=TEST-001|^"
  sleep 15
} | nc localhost 3011

# 4. Cancelar venta
echo -n "00034|5|2||POST|REQ_PUMP_CLEAR_PRESET_ID_001||||^" | nc localhost 3011

# 5. Handshake de pago (después del SALE_COMPLETED)
echo -n "00046|5|2||POST|REQ_PAYMENT_TRANSACTION_LOCK|||SA=100|LID=OV-001|^" | nc localhost 3011
echo -n "00050|5|2||POST|REQ_PAYMENT_CLEAR_SALE|||SA=100|TY=EFECTIVO|LID=OV-001|^" | nc localhost 3011
echo -n "00048|5|2||POST|REQ_PAYMENT_TRANSACTION_UNLOCK|||SA=100|LID=OV-001|^" | nc localhost 3011
```

## Surtidores configurados

| ID | Nombre | Pistolas | Grados |
|----|--------|----------|--------|
| 1  | Surtidor 1 | 8 | SUPER (1,5), EXTRA (2,6), DIESEL (3,7) |
| 2  | Surtidor 2 | 8 | SUPER (1,5), EXTRA (2,6), DIESEL (3,7) |
| 3  | Surtidor 3 | 4 | SUPER (1,4), DIESEL (2), EXTRA (3) |
| 4  | Surtidor 4 | 4 | SUPER (1,4), DIESEL (2), EXTRA (3) |

Precios: SUPER=$1.150, EXTRA=$0.950, DIESEL=$0.750

## Trama completa de una venta

```
SURTIDOR 1 — Preset $20, Pistola 1 (SUPER, $1.150/L), Efectivo

t=0.0s  [SUSCRIBIR]  ← EVT_PUMP_STATUS_CHANGE (IDLE)
t=1.0s  [PRESET]     POST REQ_PUMP_PRESET_ID_001 TY=MONEY VA=20.00 HO=1
t=1.0s  [RESPUESTA]  → EVT_PUMP_STATUS_CHANGE (AUTHORIZED, MONEY_PRESET)
t=5.0s               → EVT_PUMP_STATUS_CHANGE (STARTING)
t=7.0s               → EVT_PUMP_STATUS_CHANGE (FUELLING)
t=8.5s               → EVT_PUMP_DELIVERY_PROGRESS (AM=7.40, VO=8.696)
t=10.0s              → EVT_PUMP_DELIVERY_PROGRESS (AM=14.78, VO=17.391)
t=11.5s              → EVT_PUMP_DELIVERY_PROGRESS (AM=20.00, VO=17.391)
t=13.0s              → EVT_PUMP_STATUS_CHANGE (IDLE)
t=13.0s              → EVT_PUMP_NEW_TRANSACTION (SA=100, VO=17.391, AM=20.00)
                     
                     [Handshake de pago]
                     POST REQ_PAYMENT_TRANSACTION_LOCK SA=100 LID=OV-001
                     ← RES_PAYMENT_TRANSACTION_LOCK ST=OK
                     POST REQ_PAYMENT_CLEAR_SALE SA=100 TY=EFECTIVO
                     ← RES_PAYMENT_CLEAR_SALE ST=OK
                     POST REQ_PAYMENT_TRANSACTION_UNLOCK SA=100
                     ← RES_PAYMENT_TRANSACTION_UNLOCK ST=OK
```
