# Dashboard Diario — Plan de implementación

> Powerfin Admin · v0.33.0 plan
> Fecha: 2026-06-26

## Objetivo

Unificar los dashboards actuales (HOY + MES) en una sola página con 3 modos
de visualización: **DIARIO**, **MENSUAL**, **ANUAL**. Cada modo comparte un
patrón de chips horizontales con scroll para seleccionar el período concreto
(día del mes, mes del año, año desde fundación).

---

## 1. Arquitectura general

```
/admin/dashboard  (página única, 3 tabs)

┌────────────────────────────────────────────────────┐
│  [ 📅 DIARIO ]    [ 📆 MENSUAL ]    [ 📈 ANUAL ]   │
├────────────────────────────────────────────────────┤
│  ← Chips horizontales con scroll →                 │
│  (días 1-31 / meses Ene-Dic / años 2024-2026)      │
├────────────────────────────────────────────────────┤
│  📅 Fecha seleccionada                             │
│  ┌────────┬────────┬────────┬────────┐             │
│  │ KPI 1  │ KPI 2  │ KPI 3  │ KPI 4  │             │
│  └────────┴────────┴────────┴────────┘             │
│  📊 Gráficas específicas del modo                  │
│  📋 Tablas top                                     │
└────────────────────────────────────────────────────┘
```

### Principios

- **1 página, 3 modos** — cero duplicación de componentes estructurales.
- **Chips = patrón único** — días (28-31), meses (12), años (N).
- **Comparativo siempre presente** — vs período anterior (ayer, mes pasado, año pasado).
- **Galones al lado de dólares** — en cada modo, en cada gráfica.
- **HOY especial** — solo cuando modo=DIARIO y fecha=HOY: secciones extra de turnos y caja.

---

## 2. Lo que YA existe (HOY + MES actual)

| Componente | Archivo | Estado |
|------------|---------|--------|
| Dashboard HOY (KPI cards + shifts + cash) | `admin/src/routes/(admin)/dashboard/+page.svelte` | Existe |
| Dashboard HOY (server load) | `admin/src/routes/(admin)/dashboard/+page.ts` | Existe |
| Dashboard MES (charts) | Misma página, modo "historical" | Existe |
| `/api/admin/dashboard/summary` | `app/api/admin/dashboard.py` | Existe |
| `/api/admin/dashboard/sales-by-day` | `app/api/admin/dashboard.py` | Existe |
| `/api/admin/dashboard/sales-by-product` | `app/api/admin/dashboard.py` | Existe |
| `/api/admin/dashboard/sales-by-payment` | `app/api/admin/dashboard.py` | Existe |
| `/api/admin/dashboard/top-customers` | `app/api/admin/dashboard.py` | Existe |
| `/api/admin/dashboard/top-products` | `app/api/admin/dashboard.py` | Existe |

---

## 3. Nuevos endpoints necesarios

### Parámetro universal: `period=daily|monthly|annual`

Todos los endpoints existentes y nuevos aceptan `period` + `date`.
El backend resuelve el GROUP BY según el período:

| Period | GROUP BY | Range |
|--------|----------|-------|
| `daily` | hour | 00:00–23:59 del día |
| `monthly` | day | 1–31 del mes |
| `annual` | month | 1–12 del año |

### 3.1 Endpoints a modificar

```
GET /api/admin/dashboard/summary
  + param: period=daily|monthly|annual
  + param: date (YYYY-MM-DD | YYYY-MM | YYYY)
  → Retorna: total_sales, dispatch_count, total_gallons, avg_ticket

GET /api/admin/dashboard/sales-by-product
  + param: period=daily|monthly|annual
  + param: date
  → Igual que ahora pero filtrado por período

GET /api/admin/dashboard/sales-by-payment
  + param: period=daily|monthly|annual
  + param: date
  → Igual que ahora pero filtrado por período

GET /api/admin/dashboard/top-customers
  + param: period=daily|monthly|annual
  + param: date
  + param: limit (5/10/20 según modo)
  → Igual que ahora pero filtrado por período
```

### 3.2 Endpoints nuevos

```
GET /api/admin/dashboard/evolution
  + param: period=daily|monthly|annual
  + param: date
  → Retorna serie temporal según período:
    · daily:   [{hour: 0, sales: X, gallons: Y}, ...] (24 puntos)
    · monthly: [{day: 1, sales: X, gallons: Y}, ...] (28-31 puntos)
    · annual:  [{month: 1, sales: X, gallons: Y}, ...] (12 puntos)

GET /api/admin/dashboard/compare
  + param: period=daily|monthly|annual
  + param: date
  → Retorna comparación vs período anterior:
    · daily:   actual (today) + previous (yesterday) — mismos KPI
    · monthly: actual (this month) + previous (last month) — mismos KPI
    · annual:  actual (this year) + previous (last year) — mismos KPI
    → Período anterior = misma granularidad, mismo rango, desplazado -1

GET /api/admin/dashboard/galones-by-product
  + param: period=daily|monthly|annual
  + param: date
  → Donut: galones por producto (en vez de dólares)

GET /api/admin/dashboard/top-periods
  + param: period (solo monthly|annual)
  + param: date
  → Retorna mejores/peores sub-períodos:
    · monthly → top 5 días del mes por ventas $
    · annual  → top 3 meses del año por ventas $

GET /api/admin/dashboard/top-customers
  (modificado: limit dinámico según modo)
  → daily: 5, monthly: 10, annual: 20
```

---

## 4. Componentes visuales por modo

### 4.1 📅 DIARIO

| # | Componente | Gráfica | Endpoint |
|---|-----------|---------|----------|
| 1 | KPI Cards (Ventas $, Despachos, Galones, Ticket Prom.) | Tarjetas | `summary` |
| 2 | Ventas por Hora | 📊 Barras | `evolution` |
| 3 | Galones por Hora | 📊 Barras | `evolution` |
| 4 | Ventas por Producto | 🍩 Donut | `sales-by-product` |
| 5 | Galones por Producto | 🍩 Donut | `galones-by-product` |
| 6 | Métodos de Pago | 🥧 Pie | `sales-by-payment` |
| 7 | Comparativo vs AYER | 📊 Barras lado a lado | `compare` |
| 8 | Top 5 Clientes | 📋 Tabla | `top-customers` |

**Especial (solo si fecha = HOY):**
- Turnos abiertos/cerrados (ya existe)
- Cuadre de caja (ya existe)

### 4.2 📆 MENSUAL

| # | Componente | Gráfica | Endpoint |
|---|-----------|---------|----------|
| 1 | KPI Cards (Total $, Despachos, Galones, Ticket Prom.) | Tarjetas | `summary` |
| 2 | Evolución Ventas por Día | 📈 Línea | `evolution` |
| 3 | Evolución Galones por Día | 📈 Línea | `evolution` |
| 4 | Ventas por Producto | 🍩 Donut | `sales-by-product` |
| 5 | Galones por Producto | 🍩 Donut | `galones-by-product` |
| 6 | Métodos de Pago | 🥧 Pie | `sales-by-payment` |
| 7 | Comparativo vs MES ANTERIOR | 📊 Barras agrupadas | `compare` |
| 8 | Top 5 Días del Mes | 📊 Barras horizontales | `top-periods` |
| 9 | Top 10 Clientes | 📋 Tabla | `top-customers` |

### 4.3 📈 ANUAL

| # | Componente | Gráfica | Endpoint |
|---|-----------|---------|----------|
| 1 | KPI Cards (Total $, Despachos, Galones, Ticket Prom.) | Tarjetas | `summary` |
| 2 | Evolución Ventas por Mes | 📈 Línea/Área | `evolution` |
| 3 | Evolución Galones por Mes | 📈 Línea/Área | `evolution` |
| 4 | Ventas por Producto | 🍩 Donut | `sales-by-product` |
| 5 | Galones por Producto | 🍩 Donut | `galones-by-product` |
| 6 | Métodos de Pago | 🥧 Pie | `sales-by-payment` |
| 7 | Comparativo vs AÑO ANTERIOR | 📊 Barras agrupadas (12 pares) | `compare` |
| 8 | Top 3 Meses del Año | 📊 Barras horizontales | `top-periods` |
| 9 | Top 20 Clientes | 📋 Tabla | `top-customers` |

---

## 5. Plan de implementación (5 pasos)

### Paso 1 — Backend: refactor endpoints existentes

**Archivos:**
- `pos_backend/app/api/admin/dashboard.py`
- `app/schemas/__init__.py`

**Tareas:**
1. Agregar `period` y `date` como query params a `summary`, `sales-by-product`, `sales-by-payment`, `top-customers`
2. Implementar GROUP BY dinámico según `period` (hour/day/month)
3. Agregar `total_gallons` a `DashboardSummaryResponse`
4. Tests existentes deben seguir pasando (regresión)
5. Nuevos tests para parámetros `period` y `date`

### Paso 2 — Backend: endpoints nuevos

**Archivos:**
- `pos_backend/app/api/admin/dashboard.py`
- `app/services/dashboard_service.py` (nuevo o extender)
- `tests/test_api_admin_dashboard.py`

**Tareas:**
1. `GET /api/admin/dashboard/evolution` — serie temporal con sales + gallons
2. `GET /api/admin/dashboard/compare` — actual vs anterior
3. `GET /api/admin/dashboard/galones-by-product` — donut galones
4. `GET /api/admin/dashboard/top-periods` — top días/meses
5. Todos con tests unitarios

### Paso 3 — Frontend: refactor página dashboard

**Archivos:**
- `admin/src/routes/(admin)/dashboard/+page.svelte`
- `admin/src/routes/(admin)/dashboard/+page.ts`

**Tareas:**
1. Sustituir los 2 botones HOY/MES por 3 tabs: DIARIO / MENSUAL / ANUAL
2. Estado reactivo: `mode` (`'daily'|'monthly'|'annual'`) + `selectedDate`
3. Componente `ModeSelector.svelte` (3 botones tipo tab)
4. Componente `ChipScroller.svelte` (chips horizontales con scroll, parametrizado)
5. Auto-scroll al día actual / mes actual / año actual al cargar
6. Refactorizar `load()` para aceptar `period` y `date`

### Paso 4 — Frontend: componentes por modo

**Archivos nuevos:**
- `admin/src/lib/components/dashboard/DailyDashboard.svelte`
- `admin/src/lib/components/dashboard/MonthlyDashboard.svelte`
- `admin/src/lib/components/dashboard/AnnualDashboard.svelte`
- `admin/src/lib/components/dashboard/EvolutionChart.svelte`
- `admin/src/lib/components/dashboard/CompareChart.svelte`
- `admin/src/lib/components/dashboard/GallonsDonut.svelte`
- `admin/src/lib/components/dashboard/TopPeriodsChart.svelte`

**Tareas:**
1. Extraer componentes reutilizables de la página actual (KPI cards, donut, pie)
2. Implementar las 3 variantes de dashboard
3. Componente `EvolutionChart`: barras (daily) / línea (monthly) / área (annual)
4. Componente `CompareChart`: barras lado a lado (actual vs previous)
5. Conectar a los endpoints nuevos

### Paso 5 — UX + pulido

**Archivos:**
- `admin/src/lib/components/dashboard/ChipScroller.svelte`
- `admin/src/lib/components/dashboard/ModeSelector.svelte`

**Tareas:**
1. Chips: badge "Hoy"/"Ayer" en el número, destacado en color primario
2. Chips: días sin ventas en gris claro
3. Flechas ← → en chip scroller para meses/años con pocos elementos
4. Responsive: chips de 36-40px, scroll táctil suave (`overflow-x: auto` + `scroll-behavior: smooth`)
5. Animación de transición entre modos (fade o slide sutil)
6. Configurar `first_year` en `system_config` para el carrusel ANUAL

---

## 6. Estructura de archivos (resumen)

```
pos_backend/
├── app/api/admin/dashboard.py          ← MODIFICADO (+ evolution, compare, galones, top-periods)
├── app/schemas/__init__.py            ← MODIFICADO (+ nuevos schemas)
└── tests/test_api_admin_dashboard.py  ← MODIFICADO (+ tests nuevos)

admin/
├── src/routes/(admin)/dashboard/
│   ├── +page.svelte                   ← REFACTOR (3 tabs + chip scroller)
│   └── +page.ts                       ← REFACTOR (period + date params)
└── src/lib/components/dashboard/
    ├── ModeSelector.svelte            ← NUEVO (DIARIO/MENSUAL/ANUAL tabs)
    ├── ChipScroller.svelte            ← NUEVO (chips horizontales)
    ├── KpiCards.svelte                ← EXTRAÍDO de +page.svelte
    ├── DailyDashboard.svelte          ← NUEVO
    ├── MonthlyDashboard.svelte        ← NUEVO
    ├── AnnualDashboard.svelte         ← NUEVO
    ├── EvolutionChart.svelte          ← NUEVO (barras/línea/área según modo)
    ├── CompareChart.svelte            ← NUEVO (actual vs previous)
    ├── GallonsDonut.svelte            ← NUEVO (donut galones)
    └── TopPeriodsChart.svelte         ← NUEVO (top días/meses)
```

---

## 7. Orden de implementación recomendado

```
Paso 1 (backend refactor) → 1-2 horas
Paso 2 (backend nuevo)    → 2-3 horas
Paso 3 (frontend refactor) → 2-3 horas
Paso 4 (componentes modo)  → 3-4 horas
Paso 5 (UX pulido)         → 1-2 horas
                           ─────────
Total estimado:            9-14 horas
```

---

## 8. Configuración nueva en system_config

```sql
INSERT INTO system_config (key, value, description)
VALUES ('dashboard.first_year', '2024',
        'Primer año de operación para el carrusel ANUAL del dashboard');
```

El frontend consulta `GET /api/admin/system-config` al cargar el dashboard.
Si la key no existe, usa **2024** como fallback.

---

## 9. Estado de implementación

| Paso | Estado |
|------|--------|
| 1 — Backend refactor endpoints | ✅ v0.33.0 |
| 2 — Backend endpoints nuevos | ✅ v0.33.0 |
| 3 — Frontend refactor (tabs + chips) | ✅ v0.33.0 |
| 4 — Frontend componentes por modo | ✅ v0.33.0 |
| 5 — UX pulido (arrows, fade, first_year) | ✅ v0.33.0 |
