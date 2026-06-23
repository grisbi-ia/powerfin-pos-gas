# Admin Roadmap — Powerfin Admin

> **Tracker independiente.** No mezclar con el roadmap del POS.
> Este documento se actualiza en cada commit de admin.
> Las fases 12-17 del ROADMAP.md principal son el resumen; aquí está el detalle.

```
Última actualización: 2026-06-23
Fase actual: 17 — Cloudflare + Deploy (completado)
Progreso:  ████████████████████  Fases 12-17 ✅
Tag: v0.32.0
```

---

## FASE 12 — Admin Backend CRUD + Auth `[v0.22.0]`

### 12.1 Auth

- [x] `POST /api/admin/auth/login` — login admin (username+password, JWT 4h)
- [x] `get_admin_user` — role check (ADMIN o SUPERVISOR)
- [x] `require_permission(resource, action)` — permisos granulares
- [x] 10 tests (login, reject dispatcher, backward compat POS)

### 12.2 Users CRUD

- [x] `GET /api/admin/users` — listar (search, pagination, sort, role filter)
- [x] `POST /api/admin/users` — crear (username unique, password bcrypt)
- [x] `GET /api/admin/users/{id}` — detalle
- [x] `PUT /api/admin/users/{id}` — actualizar (parcial)
- [x] `DELETE /api/admin/users/{id}` — soft-delete (is_active=false)
- [x] 26 tests (CRUD, pagination, search, role filter, permissions)

### 12.3 Roles CRUD

- [x] `GET /api/admin/roles` — listar (search, pagination, sort)
- [x] `POST /api/admin/roles` — crear (code unique, ^[A-Z_]+$)
- [x] `GET /api/admin/roles/{id}` — detalle con permissions_json
- [x] `PUT /api/admin/roles/{id}` — actualizar (code immutable)
- [x] 28 tests roles CRUD

### 12.4 Products CRUD

- [x] `GET /api/admin/products` — listar (search, pagination, category filter)
- [x] `POST /api/admin/products` — crear (code unique, FK validation)
- [x] `GET /api/admin/products/{id}` — detalle con category + tax info
- [x] `PUT /api/admin/products/{id}` — actualizar (model_dump exclude_unset)
- [x] `DELETE /api/admin/products/{id}` — soft-delete
- [x] 36 tests products CRUD

### 12.5 Grades CRUD

- [x] `GET /api/admin/grades` — listar con product info
- [x] `POST /api/admin/grades` — crear (code unique)
- [x] `GET /api/admin/grades/{id}` — detalle con product name/unit
- [x] `PUT /api/admin/grades/{id}` — actualizar
- [x] `DELETE /api/admin/grades/{id}` — soft-delete
- [x] 28 tests grades CRUD
- [x] Migración: add is_active to grades

### 12.6 Price Lists CRUD

- [x] `GET /api/admin/price-lists` — listar con item_count
- [x] `POST /api/admin/price-lists` — crear
- [x] `GET /api/admin/price-lists/{id}` — detalle con items[] anidados
- [x] `PUT /api/admin/price-lists/{id}` — actualizar
- [x] `DELETE /api/admin/price-lists/{id}` — soft-delete
- [x] `GET/POST/PUT/DELETE /api/admin/price-lists/{id}/items` — items CRUD
- [x] Reactivación de items inactivos al recrear mismo producto
- [x] 37 tests price lists CRUD
- [x] Migración: add is_active to price_lists + price_list_items

### 12.7 Dispensers + Hoses CRUD

- [x] `GET /api/admin/dispensers` — listar con hose_count + emission_label
- [x] `POST /api/admin/dispensers` — crear
- [x] `GET /api/admin/dispensers/{id}` — detalle con hoses[] y grade info
- [x] `PUT /api/admin/dispensers/{id}` — actualizar
- [x] `DELETE /api/admin/dispensers/{id}` — soft-delete
- [x] `GET/POST/PUT /api/admin/dispensers/{id}/hoses` — hoses CRUD
- [x] Validación: lado único por dispensador (side A/B no duplicado)
- [x] 32 tests dispensers + hoses
- [x] Migración: add is_active to hoses

### 12.8 Emission Points CRUD

- [x] `GET /api/admin/emission-points` — listar
- [x] `POST /api/admin/emission-points` — crear (unique pair)
- [x] `GET /api/admin/emission-points/{id}` — detalle
- [x] `PUT /api/admin/emission-points/{id}` — actualizar (deactivate via is_active)
- [x] 19 tests emission points

### 12.9 Company Info

- [x] `GET /api/admin/company-info` — leer
- [x] `PUT /api/admin/company-info` — actualizar
- [x] 6 tests company info

### 12.10 System Config

- [x] `GET /api/admin/system-config` — listar todas las keys
- [x] `PUT /api/admin/system-config/{key:path}` — upsert (crea si no existe)
- [x] 4 tests system config

### 12.11 Payment Methods CRUD

- [x] `GET /api/admin/payment-methods` — listar
- [x] `POST /api/admin/payment-methods` — crear
- [x] `GET /api/admin/payment-methods/{id}` — detalle
- [x] `PUT /api/admin/payment-methods/{id}` — actualizar
- [x] 12 tests payment methods

### 12.12 Credit Contracts

- [x] Ya existe CRUD completo en `/api/pos/credit-contracts` (Phase 8)
- [x] Protegido por admin auth via require_permission

### Criterio de salida Fase 12

```
✅ Todos los CRUD responden con paginación y búsqueda
✅ Auth admin rechaza DISPATCHER (403)
✅ Permission checker funcional (require_permission)
✅ Tests: 338 pasando (93 POS + 209 admin + 36 otros)
✅ git tag v0.25.0
```

---

## FASE 13 — Admin Backend Dashboard + Reportes `[v0.26.0]`

### 13.1 Dashboard ✅

- [x] `GET /api/admin/dashboard/summary?date_from=&date_to=`
- [x] `GET /api/admin/dashboard/sales-by-day?date_from=&date_to=`
- [x] `GET /api/admin/dashboard/sales-by-product?date_from=&date_to=`
- [x] `GET /api/admin/dashboard/sales-by-payment?date_from=&date_to=`
- [x] `GET /api/admin/dashboard/top-customers?date_from=&date_to=&limit=`
- [x] `GET /api/admin/dashboard/top-products?date_from=&date_to=&limit=`
- [x] 11 tests dashboard

### 13.2 Reportes ✅

- [x] `GET /api/admin/reports/sales` — paginado con filtros (date, status, payment, search)
- [x] `POST /api/admin/reports/sales/export` — PDF + Excel
- [x] `GET /api/admin/reports/dispatches` — detalle con filtros (date, status, search)
- [x] `POST /api/admin/reports/dispatches/export` — PDF + Excel
- [x] `GET /api/admin/reports/shifts` — histórico con collected/surplus/shortage
- [x] `POST /api/admin/reports/shifts/export` — PDF + Excel
- [x] `GET /api/admin/reports/cash-summary` — flujo consolidado (INCOME, EXPENSE, DEPOSIT, etc.)
- [x] `POST /api/admin/reports/cash-summary/export` — PDF + Excel
- [x] 22 tests reports

### 13.3 Export Engine ✅

- [x] PDF engine (reportlab) — landscape A4, header, tabla, filas alternadas
- [x] Excel engine (openpyxl) — frozen header, auto-fit, bordes, estilos
- [x] StreamingResponse con content-type correcto
- [x] Dependencias: reportlab 5.0.0, openpyxl 3.1.5, pillow 12.2.0

### Criterio de salida Fase 13

```
✅ Dashboard con 6 endpoints y filtros de fecha
✅ Reportes con 4 GET + 4 POST export (PDF + Excel)
✅ Export engine con reportlab + openpyxl
✅ Tests: 371 pasando (93 POS + 242 admin + 36 otros)
✅ git tag v0.26.0
```

---

## FASE 14 — Admin Frontend Layout + CRUD `[v0.27.0]` ✅ COMPLETADA

- [x] Proyecto SvelteKit `admin/` (Svelte 5 + Tailwind CSS 3)
- [x] AdminShell + Sidebar + Topbar responsive
- [x] Login page admin (username + password)
- [x] Auth store + JWT interceptor (localStorage, 401 redirect)
- [x] DataTable + Pagination + StatusBadge + ConfirmDialog + EmptyState + ErrorBanner + KpiCard
- [x] 14 pantallas CRUD: users, roles, products, grades, price-lists (con items), dispensers (con hoses), emission-points, company-info, system-config, payment-methods
- [x] Reports page con tabs (Ventas/Turnos/Caja) + date filter + PDF/Excel export
- [x] svelte-sonner eliminado (incompatible Svelte 5), reemplazado por toast nativo
- [x] SSR desactivado (ssr=false) para SPA estática

## FASE 15 — Admin Frontend Dashboard `[v0.28.0]` ✅ COMPLETADA

- [x] KPI cards (ventas totales, despachos, ticket promedio, turnos activos)
- [x] Sales by Day (Chart.js línea multi-producto)
- [x] Sales by Product (donut con % visibles)
- [x] Sales by Payment (pie con % visibles)
- [x] Dashboard "Hoy" con KPIs diarios, ventas por hora, turnos del día, últimos despachos
- [x] Toggle Mes | Hoy con comparación vs día anterior

## FASE 16 — Admin Frontend Reportes `[v0.29.0]` ✅ COMPLETADA

- [x] Sales report page (columnas: fecha, surtidor, lado, grado, cliente, placa, pago, monto, volumen, SRI, usuario)
- [x] Shifts report page (histórico con collected/surplus/shortage)
- [x] Cash summary page (flujo consolidado)
- [x] ExportButton → PDF / Excel (Response con content-type correcto)
- [x] Trend chart en reportes (bar chart de ventas diarias)
- [x] Summary KPIs por tab (total registros, monto, promedio, página)
- [x] Filtro closed_date para turnos cerrados hoy
- [x] 10 registros por página

### v0.31.0 — Deploy readiness + bugfixes (2026-06-23)

- [x] deploy-to-server.sh: admin target (rsync admin/src/ + config)
- [x] powerfin-gas: deploy-admin, start/stop/restart-admin, status + health :5174
- [x] INSTALL.md: admin-frontend.service, Nginx /admin location, firewall :5174
- [x] Alembic migrations tracked in git (4 archivos de schema admin)
- [x] requirements.txt: +reportlab, +openpyxl, +Pillow
- [x] package.json: @sveltejs/vite-plugin-svelte ^5.0.0 (vite 6 compat)
- [x] Dashboard: fixed UTC timezone bug — "Hoy" usaba toISOString()
- [x] Admin funcionando en producción (neoguayas2, :5174)

---

## FASE 17 — Cloudflare + Deploy `[v1.0.0]`

- [x] cloudflared instalado + configurado
- [x] Cloudflare Tunnel + DNS
- [x] Nginx config `/admin` (documentado en INSTALL.md)
- [ ] Rate limiting login
- [x] Deploy script (deploy-to-server.sh + powerfin-gas con admin)
- [x] Prueba E2E pública
- [x] Documentación final (docs/admin/CLOUDFLARE_TUNNEL.md)

---

## Convenciones de este documento

- **[x]** = completado y con tests pasando
- **[ ]** = pendiente
- Cada checkbox se actualiza en el commit donde se completa
- Este archivo es la fuente de verdad del progreso admin
- No duplicar tildes con ROADMAP.md — ROADMAP.md es el plan general, este es el tracker diario
