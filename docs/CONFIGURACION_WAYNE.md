# Configuración Wayne Synergy — Procedimiento de cambios

## Principio fundamental

Los cambios hechos en la GUI del Wayne Fusion **se guardan en la base de datos interna inmediatamente**. Sin embargo, la propagación al dispensador **depende del tipo de parámetro**:

### Parámetros que REQUIEREN reinicialización

Afectan al **Transaction Engine** de cada bomba. Solo se cargan cuando el dispensador se conecta/reconecta.

| Parámetro | Ejemplo |
|-----------|---------|
| Authorization Timeout (ATO) | `Forecourt Manager → General` |
| Retries | `Pump N → Transaction Engine` |
| Process zero sale | `Pump N → Transaction Engine` |
| Service Mode (Self/Full) | `Pump N → Service Mode` |

### Parámetros que se propagan EN CALIENTE (sin reiniciar)

Se aplican automáticamente a las bombas, sin necesidad de reinicialización.

| Parámetro | Ejemplo |
|-----------|---------|
| Precio de combustible | `Grades → Grade N → Price Level 1` |
| Nombre/descripción de grado | `Grades → Grade N → Description` |

```
┌──────────────────────────────────────────────────────────┐
│  Synergy Fusion                                          │
│                                                          │
│  ┌──────────────┐     ┌──────────────────────────────┐  │
│  │ GUI (cambios)│────►│ DB interna (guardado ✓)       │  │
│  └──────────────┘     └──────────┬───────────────────┘  │
│                                  │                       │
│         ┌────────────────────────┼───────────────────┐   │
│         │                        │                   │   │
│    Precios,                   ATO, Retries,          │   │
│    descripciones              ZeroSale, etc.         │   │
│         │                        │                   │   │
│         ▼                        ▼                   │   │
│    ✅ EN CALIENTE            ❌ SOLO al              │   │
│    (inmediato)               INICIALIZAR             │   │
│                                  │                   │   │
│  ┌──────────────────────────────┐│                   │   │
│  │ Pump N Transaction Engine    │◄┘                   │   │
│  │ (usa valores viejos hasta    │                    │   │
│  │  que se reinicialice)        │                    │   │
│  └──────────────────────────────┘                    │   │
└──────────────────────────────────────────────────────────┘
```

**Regla general:** Si el cambio es de precios, se aplica solo. Si es de comportamiento del dispensador (timeouts, reintentos, modo), hay que reinicializar.

---

## Procedimiento paso a paso

### Paso 1 — Hacer el cambio en la GUI

Navegar a la sección correspondiente en la consola Wayne Fusion:

| Parámetro | Ruta en la GUI |
|-----------|---------------|
| Authorization Timeout (ATO) | `Forecourt Manager → General` |
| Retries por bomba | `Forecourt Manager → Pumps → Pump N → Transaction Engine` |
| Process zero sale | `Forecourt Manager → Pumps → Pump N → Transaction Engine` |
| Precio de combustible | `Forecourt Manager → Grades → Grade N → Price Level 1` |
| Modo de servicio (Self/Full) | `Forecourt Manager → Pumps → Pump N → Service Mode` |
| Límite máximo por monto | `Forecourt Manager → Pumps → Pump N → Max Amount` |
| Límite máximo por volumen | `Forecourt Manager → Pumps → Pump N → Max Volume` |

Guardar el cambio. La GUI confirma que se guardó, pero el cambio **todavía no está activo en las bombas**.

---

### Paso 2 — Forzar la reinicialización

Hay 3 métodos. Usar el que mejor se adapte a la situación operativa.

#### Método A — Por protocolo TCP (sin intervención física)

Ideal cuando la estación está operando y no se quiere intervenir físicamente.

```bash
# Para una bomba específica (ej: bomba 1)
python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --pump 1

# Para todas las bombas (1-6)
python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --all
```

El script ejecuta la secuencia:
```
1. REQ_PUMP_STOP_ID_00N|PA=1     → detener bomba
2. Esperar 5 segundos
3. REQ_PUMP_CLEAR_STOP_ID_00N    → liberar
4. REQ_PUMP_OPEN_ID_00N          → reabrir → Transaction Engine se reinicializa
5. Verificar que quede en ST=IDLE
```

**Nota:** Este método puede no funcionar en versiones antiguas del firmware (el STOP/OPEN por protocolo podría no gatillar la reinicialización completa del Transaction Engine). Validar con el script de diagnóstico.

#### Método B — Desconexión física del cable (100% efectivo)

El que usamos y validamos en campo.

```
Para cada dispensador a reinicializar:

1. Ubicar el cable de comunicación serial entre el dispensador y el Synergy
2. Desconectar el cable
3. Esperar 10 segundos (el Fusion marca "pump offline")
4. Reconectar el cable
5. El Fusion detecta la bomba → inicializa Transaction Engine desde la DB
6. Esperar a que el estado pase a IDLE
```

**Ventaja:** 100% garantizado.  
**Desventaja:** Requiere acceso físico a cada dispensador.

#### Método C — Desde la consola del dispensador (si aplica)

Solo para dispensadores con panel de control local.

```
1. En el teclado del dispensador, cambiar a modo MANUAL
2. Esperar 5 segundos
3. Volver a modo CONSOLA
4. El dispensador se re-registra con el Fusion → reinicializa Transaction Engine
```

---

### Paso 3 — Verificar con script de diagnóstico

```bash
python3.11 docs/scripts_fusion_bridge/diagnostico_preset.py
```

Verificar que:
- `ST=IDLE` en todas las bombas afectadas
- El PRESET de prueba es aceptado (`ST=AUTHORIZED`) en cada bomba
- Si alguna bomba sigue en ERROR o CLOSED → repetir Paso 2 para esa bomba

---

## Procedimiento para múltiples dispensadores (4, 6, 8...)

Con muchos dispensadores, la clave es ser **metódico y secuencial**, nunca en paralelo sin verificar.

```
1. Cambiar la configuración en la GUI del Fusion
                    │
                    ▼
2. Preguntarse: ¿el cambio aplica a TODAS las bombas o solo a algunas?
        ┌───────────┴───────────┐
        │                       │
     TODAS                    ALGUNAS
        │                       │
        ▼                       ▼
3. Elegir UNA bomba        3. Elegir UNA bomba
   de prueba (la más           de las afectadas
   accesible)
        │                       │
        ▼                       ▼
4. Aplicar Método A, B o C  → 4. Aplicar Método A, B o C
        │                       │
        ▼                       ▼
5. Ejecutar diagnostico_preset.py
        │
        ▼
6. ¿PRESET aceptado en bomba de prueba?
        ┌───────────┴───────────┐
        │                       │
       SÍ                       NO
        │                       │
        ▼                       ▼
7. Repetir Paso 4 en        7. Revisar qué pasó:
   cada bomba restante         - ¿Cable bien conectado?
   UNA POR UNA                 - ¿Bomba en CLOSED/ERROR?
                               - ¿Logs del Fusion?
                               - Repetir Paso 2 (método B)
```

### Reglas para múltiples dispensadores

1. **Nunca reinicializar todas a la vez** sin verificar la primera
2. **Probar una, verificar, luego la siguiente** — ritmo: 1 bomba cada ~30 segundos
3. **Si una bomba no responde** después de 2 intentos, pasar a la siguiente y volver después
4. **Documentar** qué bomba se reinicializó y a qué hora
5. **Tener a mano el script de diagnóstico** para verificar cada una

---

## Valores de referencia

| Parámetro | Valor correcto | Significado |
|-----------|---------------|-------------|
| Authorization Timeout (ATO) | `180` | Segundos que la autorización está vigente |
| Retries | `4` | Reintentos de autorización antes de abortar |
| Process zero sale | `0` / `NO` | No procesar ventas de $0.00 |
| Service Mode | `Self Service` | El POS controla la autorización |

---

## Diagnóstico rápido

### Script principal

```bash
# Verificar estado de todas las bombas + prueba de PRESET
python3.11 docs/scripts_fusion_bridge/diagnostico_preset.py
```

### Script de reinicialización individual

```bash
# Reinicializar una bomba específica
python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --pump 1
```

### Script de cambio de precios

```bash
# Solo mostrar precios actuales
python3.11 docs/scripts_fusion_bridge/actualizar_precio.py --show

# Cambiar precio DIESEL (requiere aprobación, ver sección abajo)
python3.11 docs/scripts_fusion_bridge/actualizar_precio.py 3.103
```

### Verificación manual rápida

```bash
# Solo estado de surtidores (sin prueba de PRESET)
echo -n "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^" | nc -v 192.168.1.20 3011
```

---

## Cambio de precios vía protocolo

El Wayne Fusion tiene un flujo de cambio de precios con aprobación:

```
Paso 1: REQ_PRICES_SET_NEW_PRICE_CHANGE → cambio pendiente
Paso 2: REQ_PRICES_APPROVE_PRICE_CHANGE  → aprobación (puede tardar ~2-3 min)
Paso 3: Precio aplicado → G001L01, P00xH1PRICE se actualizan en caliente
```

### Comando para crear cambio de precio

```
POST|REQ_PRICES_SET_NEW_PRICE_CHANGE|Price Change Add In||
  QTY=1|G01NR=3|G01LV=1|G01PR=3.103|^
```

| Campo | Descripción |
|-------|-------------|
| QTY | Cantidad de cambios en este mensaje |
| G01NR | Grade Number (3 = DIESEL) |
| G01LV | Price Level (1) |
| G01PR | Nuevo precio |

### Comando para aprobar cambio de precio

```
POST|REQ_PRICES_APPROVE_PRICE_CHANGE|Price Change Add In||
  PCHID=1|USER=POWERFIN|^
```

| Campo | Descripción |
|-------|-------------|
| PCHID | ID del cambio de precio a aprobar (generalmente "1") |
| USER | Usuario que aprueba |

### Notas importantes

- El módulo **"Price Change Add In"** debe estar habilitado en el Fusion
- La aprobación puede tardar **2-3 minutos** en aplicarse (no es instantánea)
- Una vez aplicado, el precio se propaga **en caliente** a las bombas (no requiere reinicialización)
- Si el módulo no está habilitado, el comando de aprobación será ignorado
- Alternativa: cambiar el precio directamente en `Forecourt Manager → Grades → DIESEL → Price Level 1`

---

---

## Checklist operativa

Antes de un cambio de configuración:

- [ ] ¿Hay ventas en curso? → Esperar a que terminen o avisar a isleros
- [ ] ¿Es horario pico? → Posponer si es posible
- [ ] ¿Tengo el script de diagnóstico listo? → `diagnostico_preset.py`
- [ ] ¿Sé exactamente qué bombas se verán afectadas?
- [ ] ¿Tengo acceso físico a los dispensadores? (por si falla el método A)

Después del cambio:

- [ ] Ejecutar `diagnostico_preset.py` en la bomba de prueba
- [ ] Verificar `ST=IDLE` y `PRESET ACEPTADO`
- [ ] Repetir en cada bomba afectada
- [ ] Confirmar que no hay bombas en ERROR o CLOSED
- [ ] Anotar hora y bombas reinicializadas (para correlacionar con logs si hay problemas después)

---

## Historial de validación

| Fecha | Cambio | Bombas afectadas | Método usado | Resultado |
|-------|--------|-----------------|-------------|-----------|
| 2026-05-28 | ATO: 0→180, Retries: 3→4, ZeroSale: YES→NO | 1, 2 | B (desconexión física) | ✅ PRESET funcionando |
| 2026-05-29 | Precio DIESEL: $9.999→$3.103 | 1, 2 | Protocolo (REQ_PRICES_SET + APPROVE) | ✅ Aplicado en caliente, sin reiniciar |
