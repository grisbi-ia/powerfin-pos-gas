# PROMPT_NEXT_SESSION — Powerfin POS

## Dónde nos quedamos

**Branch:** `develop`

**Último avance:** Escenario 1 funcional end-to-end con simulador Fusion + FusionBridge real + POS.

## Cómo retomar mañana

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
git checkout develop
git status
```

### 4 terminales (en orden):

```bash
# Terminal 1 — Simulador Fusion
python3 tools/fusion_simulator.py --port 3012 --pumps 2

# Terminal 2 — PowerFin Server (backend REST simulado)
python3 tools/powerfin_server.py --port 8080

# Terminal 3 — FusionBridge
cd fusion-bridge
FUSION_IP=127.0.0.1 FUSION_PORT=3012 ./mvnw quarkus:dev

# Terminal 4 — Powerfin POS
cd posexport PATH=$HOME/.n/bin:$PATH
npm run dev -- --host
```

### Navegador: http://localhost:5173
Login: `carlos` / PIN `1234`

## Lo logrado hoy

### Persistencia y reconciliación de pendingOrders
- **localStorage:** pendingOrders persiste en `localStorage` (clave `"pendingOrders"`)
- **Escritura instantánea:** cada add/update/remove guarda a localStorage
- **Reconciliación cada 30s:** compara local vs PowerFin vía `GET /api/pos/shifts/{id}/dispatches`
- **Reglas de reconciliación:**
  - Orden local que no está en servidor → se elimina (cobrada/cancelada en otro dispositivo)
  - Orden del servidor que no está local → se agrega (otro despachador autorizó)
  - Ambas → actualiza local con datos autoritativos del servidor
- **Mock persistente:** `powerfin.mock.ts` ahora guarda `mockOrders` en `localStorage` (`mockServerOrders`)
- **DispatchOrder** extendido con `side`, `final_amount`, `final_volume`, `invoice_number`, `shift_id`, `authorized_by`
- **CustomerName:** "Consumidor Final" cuando no hay cliente identificado

### PowerFin Server Simulator (`tools/powerfin_server.py`)
- Servidor HTTP REST completo emulando PowerFin ERP
- **Persistencia en archivo JSON** — estado compartido entre todos los dispositivos
- 14 endpoints (`login`, `config`, `customers`, `vehicles/lookup`, `prices`, `shifts/*`, `dispatches/*`)
- 3 usuarios: carlos, maria, pedro (todos PIN 1234)
- CORS habilitado para acceso desde tablets
- Arquitectura multi-dispositivo real:
  ```
  Tablet 1 ─┐
  Tablet 2 ─┤── powerfin_server.py :8080 ── JSON file
  Tablet 3 ─┘
  ```

### Documentación
- `tools/README.md` actualizado con PowerFin Server Simulator
- `PROMPT_NEXT_SESSION.md` actualizado a 4 terminales

## Pendientes para la siguiente sesión

1. **Escenarios restantes** (2 al 23 de FLUJOS_VENTA_ESCENARIOS.md)
2. **Conectar POS al `powerfin_server.py`** (ahora usa `powerfin.mock.ts`)
3. **FusionBridge per-hose tracking** (ahora es pump-level, convertimos en POS)
4. **Cierre de turno** con cuadre de caja
5. **Depósitos a caja fuerte**
6. **Impresión de tickets** (Fase 5)

## Lecciones aprendidas (Svelte)

- `$store` solo funciona en top-level de `<script>` o `$:`, NO dentro de funciones regulares
- Map como prop no es reactivo. Leer el store directo con `$store` en el componente
- `{@const}` debe ser hijo directo de `{#if}`/`{#each}`, no dentro de `<div>`
- `as` type assertion no funciona en templates de Svelte

## Tests

```bash
# FusionBridge: 35 tests
cd fusion-bridge && ./mvnw test

# Powerfin POS: 41 tests
cd pos && npm run test

# Typecheck
cd pos && npm run check
```
