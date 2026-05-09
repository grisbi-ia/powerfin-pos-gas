# Flujos Operativos — Despachador en la Gasolinera

## Flujo 1 — Login y apertura de turno

```
Despachador abre Chrome en su celular
Va a https://pos.gasolinera.com
(guardado como app en la pantalla de inicio)

┌─────────────────────────────────────┐
│  Powerfin POS  —  GASOLINERA            │
│                                     │
│  Usuario:   [carlos            ]    │
│                                     │
│  PIN:  ● ● ● ●                      │
│  ┌──┐ ┌──┐ ┌──┐                    │
│  │1 │ │2 │ │3 │                    │
│  ├──┤ ├──┤ ├──┤                    │
│  │4 │ │5 │ │6 │                    │
│  ├──┤ ├──┤ ├──┤                    │
│  │7 │ │8 │ │9 │                    │
│  ├──┤ ├──┤ ├──┤                    │
│  │  │ │0 │ │⌫ │                    │
│  └──┘ └──┘ └──┘                    │
│                                     │
│  [   INGRESAR   ]                   │
└─────────────────────────────────────┘

→ Sistema detecta que no hay turno activo
→ Redirige a apertura de turno

┌─────────────────────────────────────┐
│  Abrir Turno                        │
│                                     │
│  Carlos Sarmiento                   │
│  Lunes 21 Abril 2024  06:03 AM      │
│                                     │
│  Selecciona tu isla:                │
│  ┌──────────┐   ┌──────────┐        │
│  │  ISLA 1  │   │  ISLA 2  │        │
│  │ Surt. 1  │   │ Surt. 3  │        │
│  │ Surt. 2  │   │ Surt. 4  │        │
│  └──────────┘   └──────────┘        │
│                                     │
│  Efectivo inicial:  [$     0.00]    │
│                                     │
│  [   ABRIR TURNO   ]                │
└─────────────────────────────────────┘
```

---

## Flujo 2 — Venta completa (flujo principal)

### Pantalla principal

```
┌──────────────────────────────────────────┐
│  Carlos S.  │  Turno 06:03  │  🟢 Online │
├──────────────────────────────────────────┤
│                                          │
│  ┌────────────────┐  ┌────────────────┐  │
│  │  SURTIDOR 1    │  │  SURTIDOR 2    │  │
│  │  🟢 Disponible │  │  🟢 Disponible │  │
│  └────────────────┘  └────────────────┘  │
│                                          │
│  Ventas: 0  │  Total: $0.00             │
│  [Historial]  [Caja]  [+ Cubrir]        │
└──────────────────────────────────────────┘
```

### Nueva venta (toca surtidor 1)

```
┌──────────────────────────────────────────┐
│  ← Surtidor 1                            │
├──────────────────────────────────────────┤
│  Cliente:                                │
│  [🔍 Buscar placa, cédula, nombre...  ]  │
│  [Sin identificar (Consumidor Final)]    │
│                                          │
│  Pistola:  [● 1]  [ 2]                  │
│                                          │
│  SUPER  —  Precio: $1.200/litro          │
│                                          │
│  Monto:                                  │
│  [$       50.00       ]                  │
│  [$5] [$10] [$20] [$50] [$100]          │
│                                          │
│  Pago: [EFECTIVO  ▼]                     │
│                                          │
│  [   AUTORIZAR DESPACHO   ]              │
└──────────────────────────────────────────┘
```

### Con cliente identificado (VIP)

```
Cliente encontrado:
┌──────────────────────────────────────────┐
│  Juan Pérez  ·  0912345678               │
│  Placa: ABC-1234   ·   🌟 VIP            │
│  Precio aplicado: $1.100/litro           │
└──────────────────────────────────────────┘
```

### Despachador toca AUTORIZAR

```
Powerfin POS hace dos llamadas en secuencia:
  1. POST /api/pos/dispatches → PowerFin registra → OV-001
  2. POST /api/dispatch/authorize → FusionBridge envía preset al Fusion

→ Fusion responde ST=AUTHORIZED
→ SSE llega al Powerfin POS: DISPENSER_STATUS=AUTHORIZED

┌──────────────────────────────────────────┐
│  Surtidor 1  │  🟡 AUTORIZADO            │
│                                          │
│  Juan Pérez  ·  ABC-1234  ·  VIP         │
│  Hasta: $50.00  ·  $1.100/litro          │
│                                          │
│  Cliente puede levantar la pistola       │
│                                          │
│  [Cancelar preset]                       │
└──────────────────────────────────────────┘
```

### Cliente despacha (SSE actualiza automáticamente)

```
→ Cliente levanta pistola → Fusion: ST=FUELLING
→ SSE: DISPENSER_STATUS=FUELLING

┌──────────────────────────────────────────┐
│  Surtidor 1  │  🟠 DESPACHANDO           │
│                                          │
│  SUPER  ·  $1.100/litro                  │
│                                          │
│  ████████████████████░░░░  75%           │
│  Volumen:   34.091 litros                │
│  Monto:     $37.50  /  $50.00            │
│                                          │
└──────────────────────────────────────────┘
```

### Despacho completo

```
→ Cliente cuelga pistola → Fusion: EVT_PUMP_NEW_TRANSACTION
→ FusionBridge: Lock → ClearSale → Unlock en Fusion
→ FusionBridge notifica a PowerFin → factura SRI
→ SSE: SALE_COMPLETED

┌──────────────────────────────────────────┐
│  ✅ Despacho completado                  │
│                                          │
│  SUPER          45.455 litros            │
│  Precio         $1.100/litro             │
│  ─────────────────────────────          │
│  TOTAL          $50.00                   │
│  Pago           EFECTIVO                 │
│                                          │
│  Juan Pérez  ·  ABC-1234                 │
│  Factura: 001-001-000001234  ✅           │
│                                          │
│  ─────── ¿El cliente desea ticket? ───── │
│  [ 🖨 SÍ, IMPRIMIR ]  [ ✗ NO, GRACIAS ] │
└──────────────────────────────────────────┘
```

### Si el despachador toca "SÍ, IMPRIMIR"

```
Powerfin POS: POST /api/print → FusionBridge
FusionBridge: genera ESC/POS → socket TCP → impresora 192.168.1.31:9100
La impresora de la isla imprime el ticket físico.

┌──────────────────────────────────────────┐
│  ✅ Ticket impreso                       │
│                                          │
│  [   Nueva venta   ]                     │
└──────────────────────────────────────────┘
```

---

## Flujo 3 — Venta sin identificar cliente

Igual al Flujo 2, pero el despachador toca **[Sin identificar]**.
El sistema usa el cliente genérico "CONSUMIDOR FINAL" de PowerFin.
La factura sale a nombre de consumidor final.
El ticket se puede imprimir igualmente.

---

## Flujo 4 — Cierre de turno

```
Despachador toca [Cerrar turno]

Powerfin POS verifica que no hay órdenes activas (AUTHORIZED o FUELLING).
Si las hay, no permite cerrar hasta que terminen.

┌──────────────────────────────────────────┐
│  Cierre de Turno                         │
│  Carlos Sarmiento                        │
│  06:03 → 14:08  (8h 05min)              │
├──────────────────────────────────────────┤
│  RESUMEN DEL TURNO                       │
│                                          │
│  Despachos:      47                      │
│  Volumen total:  1,234.567 litros        │
│  Total ventas:   $1,481.48               │
│                                          │
│  EFECTIVO:   $890.50                     │
│  TARJETA:    $450.00                     │
│  QR:         $140.98                     │
│                                          │
│  Efectivo esperado: $890.50              │
│  Efectivo en caja:  [$890.50]            │
│  Diferencia:        $0.00  ✅            │
│                                          │
│  [🖨 Imprimir reporte de turno]          │
│  [   CERRAR TURNO   ]                    │
└──────────────────────────────────────────┘

Al confirmar:
  → POST /api/pos/shifts/{id}/close → PowerFin cierra el turno
  → Powerfin POS redirige a login
  → Sesión cerrada
```

---

## Flujo 5 — Cubrir surtidor adicional

```
Despachador toca [+ Cubrir]

┌──────────────────────────────────────────┐
│  Cubrir surtidor adicional               │
├──────────────────────────────────────────┤
│  ┌──────────────────────────────────┐    │
│  │  🟢 Surtidor 3 — Disponible     │    │
│  │     Isla 2 (sin despachador)    │    │
│  └──────────────────────────────────┘    │
│  ┌──────────────────────────────────┐    │
│  │  🟢 Surtidor 4 — Disponible     │    │
│  │     Isla 2 (sin despachador)    │    │
│  └──────────────────────────────────┘    │
│  [Cancelar]                              │
└──────────────────────────────────────────┘

Selecciona Surtidor 3 → ahora ve 3 surtidores en su pantalla principal.
Cada venta registrada con su usuario.
```

---

## Flujo 6 — Movimiento de caja

```
Despachador toca [Caja] → [Ingreso] o [Egreso]

┌──────────────────────────────────────────┐
│  Ingreso de caja                         │
│                                          │
│  Monto:   [$     100.00     ]            │
│  Motivo:  [Cambio inicial   ]            │
│                                          │
│  [   REGISTRAR   ]                       │
└──────────────────────────────────────────┘

POST /api/pos/cash-movements → PowerFin registra el movimiento.
```

---

## Estados del surtidor en la app

| Estado Fusion | Color          | Texto en app      | ¿Puede vender? |
| ------------- | -------------- | ----------------- | -------------- |
| IDLE          | 🟢 Verde       | Disponible        | ✅ sí          |
| CALLING       | 🔵 Azul        | Cliente esperando | ✅ sí          |
| AUTHORIZED    | 🟡 Amarillo    | Autorizado        | ❌ no          |
| FUELLING      | 🟠 Naranja     | Despachando       | ❌ no          |
| PAUSED        | 🟣 Morado      | Pausado           | ❌ no          |
| STOPPED       | 🔴 Rojo        | Detenido          | ❌ no          |
| ERROR         | 🔴 Rojo oscuro | Error             | ❌ no          |
| CLOSED        | ⚫ Gris        | Cerrado           | ❌ no          |

---

## Políticas de impresión

| Política | Comportamiento                                                         |
| -------- | ---------------------------------------------------------------------- |
| `ALWAYS` | Imprime automáticamente al completar cada despacho, sin preguntar      |
| `ASK`    | Muestra botones "¿Desea ticket?" — despachador decide según el cliente |
| `NEVER`  | No imprime — solo factura digital por correo (si cliente tiene email)  |

La política se configura en la variable de entorno `PRINTER_POLICY` del FusionBridge
y el Powerfin POS la consulta al arrancar via `GET /api/print/policy`.
