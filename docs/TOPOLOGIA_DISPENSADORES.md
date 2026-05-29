# Topología de dispensadores — NEOGAS

> Explicación con referencia física: armario, lado, pistola.

---

## Vocabulario

| Término POS | Término Synergy | Qué es físicamente |
|-------------|----------------|-------------------|
| **Dispenser** (dispenserId) | — | El **armario completo**, todo el mueble |
| — | **Pump** (fusionPumpId) | Un **lado del armario**. Cada lado = 1 pump en el Synergy |
| **Hose** (hoseId) | **Hose** (fusionHoseId) | La **pistola/manguera** que se agarra para echar combustible |

---

## Topología real de la estación

### Isla 1

```
┌─────────────────────┐
│   ARMARIO DIESEL    │  ← dispenserId = 1
│                     │
│  🟢 LADO A          │  ← Pump 1  (fusionPumpId=1)
│     pistola DIESEL  │  ← Hose 1  (fusionHoseId=1)
│                     │
│  🟢 LADO B          │  ← Pump 2  (fusionPumpId=2)
│     pistola DIESEL  │  ← Hose 1  (fusionHoseId=1)
└─────────────────────┘

┌──────────────────────────┐
│   ARMARIO GASOLINA       │  ← dispenserId = 2
│                          │
│  🟡🟠 LADO A             │  ← Pump 3  (fusionPumpId=3)
│     pistola 1 = EXTRA    │  ← Hose 1  (fusionHoseId=1)
│     pistola 2 = SUPER    │  ← Hose 2  (fusionHoseId=2)
│                          │
│  🟡🟠 LADO B             │  ← Pump 4  (fusionPumpId=4)
│     pistola 1 = EXTRA    │  ← Hose 1  (fusionHoseId=1)
│     pistola 2 = SUPER    │  ← Hose 2  (fusionHoseId=2)
└──────────────────────────┘
```

### Isla 2

```
┌─────────────────────┐
│   ARMARIO DIESEL    │  ← dispenserId = 3
│                     │
│  🟢 LADO A          │  ← Pump 5  (fusionPumpId=5)
│     pistola DIESEL  │  ← Hose 1  (fusionHoseId=1)
│                     │
│  🟢 LADO B          │  ← Pump 6  (fusionPumpId=6)
│     pistola DIESEL  │  ← Hose 1  (fusionHoseId=1)
└─────────────────────┘

┌──────────────────────────┐
│   ARMARIO GASOLINA       │  ← dispenserId = 4
│                          │
│  🟡 LADO A               │  ← Pump 7  (fusionPumpId=7)
│     pistola 1 = EXTRA    │  ← Hose 1  (fusionHoseId=1)
│                          │
│  🟡 LADO B               │  ← Pump 8  (fusionPumpId=8)
│     pistola 1 = EXTRA    │  ← Hose 1  (fusionHoseId=1)
└──────────────────────────┘
```

---

## Mapeo de IDs

| Armario | Lado | Combustible | dispenserId | fusionPumpId | fusionHoseId | hoseId |
|---------|------|-------------|:-----------:|:------------:|:------------:|:------:|
| DIESEL I1 | A | DIESEL | 1 | 1 | 1 | 1 |
| DIESEL I1 | B | DIESEL | 1 | 2 | 1 | 2 |
| GASOLINA I1 | A | EXTRA | 2 | 3 | 1 | 3 |
| GASOLINA I1 | A | SUPER | 2 | 3 | 2 | 4 |
| GASOLINA I1 | B | EXTRA | 2 | 4 | 1 | 5 |
| GASOLINA I1 | B | SUPER | 2 | 4 | 2 | 6 |
| DIESEL I2 | A | DIESEL | 3 | 5 | 1 | 7 |
| DIESEL I2 | B | DIESEL | 3 | 6 | 1 | 8 |
| GASOLINA I2 | A | EXTRA | 4 | 7 | 1 | 9 |
| GASOLINA I2 | B | EXTRA | 4 | 8 | 1 | 10 |

---

## Cómo funciona el match al completar un despacho

Cuando el Synergy termina una venta, emite `EVT_PUMP_NEW_TRANSACTION` con:

| Parámetro Fusion | Significado físico |
|-----------------|-------------------|
| `PM` (pump) | "qué lado del armario" |
| `HO` (hose) | "qué pistola de ese lado" |

### Ejemplo concreto

El cajero toca en el POS: **Isla 2, GASOLINA, lado B, pistola EXTRA**.

| Paso | Quién | Qué hace |
|------|-------|----------|
| 1 | POS | Crea orden con `fusionPumpId=8, fusionHoseId=1` |
| 2 | FusionBridge | Envía PRESET a Pump 8, Hose 1 |
| 3 | Cliente | Despacha EXTRA por el lado B de la isla 2 |
| 4 | Synergy | Emite `NEW_TRANSACTION`: **PM=8, HO=1** |
| 5 | POS | `completeOrder(fusionPumpId=8, fusionHoseId=1)` → busca orden con esos IDs → ✅ encontrada |
| 6 | POS | Muestra **"Cobrar"** en el lado B de GASOLINA Isla 2 |

### Match para cualquier topología

```
completeOrder(fusionPumpId, fusionHoseId)
  ↓
Busca en pendingOrders:
  "orden con fusionPumpId=X Y fusionHoseId=Y Y estado='FUELLING'"
  ↓
✅ Match exacto: fusionPumpId + fusionHoseId son únicos por pistola física
```

Si un pump tiene 2 pistolas (ej: EXTRA y SUPER en GASOLINA I1 lado A), el `fusionHoseId` distingue cuál de las dos se despachó. Sin ese campo, se completaría la orden equivocada.

---

## Visualización en el POS

```
orderByHose: Map<"dispenserId-hoseId", PendingOrder>

  "1-1"  →  orden del lado A del DIESEL Isla 1
  "1-2"  →  orden del lado B del DIESEL Isla 1
  "2-3"  →  orden de EXTRA del lado A de GASOLINA Isla 1
  "2-4"  →  orden de SUPER del lado A de GASOLINA Isla 1
  ...
  "4-10" →  orden de EXTRA del lado B de GASOLINA Isla 2
```

Cada manguera visible en el POS tiene una clave única `dispenserId-hoseId`.

---

## Relación PowerFin ↔ Synergy

```
PowerFin ERP                          Wayne Synergy
┌──────────────────┐                 ┌──────────────────┐
│ dispenserId = 1   │                │                  │
│ name = "DIESEL I1"│                │  Pump 1 (1 hose) │
│                  │                 │  Pump 2 (1 hose) │
│ dispenserId = 2   │                │  Pump 3 (2 hoses)│
│ name = "GASOL I1" │                │  Pump 4 (2 hoses)│
│                  │                 │  Pump 5 (1 hose) │
│ dispenserId = 3   │                │  Pump 6 (1 hose) │
│ name = "DIESEL I2"│                │  Pump 7 (1 hose) │
│                  │                 │  Pump 8 (1 hose) │
│ dispenserId = 4   │                │                  │
│ name = "GASOL I2" │                │                  │
└──────────────────┘                 └──────────────────┘
         │                                    │
         └──── fusionPumpId / fusionHoseId ───┘
                    (mapeo en config)
```
