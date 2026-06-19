# Admin Roadmap — Powerfin Admin

> **Tracker independiente.** No mezclar con el roadmap del POS.
> Este documento se actualiza en cada commit de admin.
> Las fases 12-17 del ROADMAP.md principal son el resumen; aquí está el detalle.

```
Última actualización: 2026-06-18
Fase actual: 12 — Admin Backend CRUD + Auth
Progreso:  ████░░░░░░░░░░░░░░  2/16 recursos CRUD (auth + users)
```

---

## FASE 12 — Admin Backend CRUD + Auth `[v0.20.0]`

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

- [ ] `GET /api/admin/roles` — listar
- [ ] `POST /api/admin/roles` — crear
- [ ] `PUT /api/admin/roles/{id}` — actualizar (incl. permissions_json)
- [ ] Tests roles CRUD

### 12.4 Products CRUD

- [ ] `GET /api/admin/products` — listar (search, pagination, category filter)
- [ ] `POST /api/admin/products` — crear (code unique)
- [ ] `GET /api/admin/products/{id}` — detalle con category + tax
- [ ] `PUT /api/admin/products/{id}` — actualizar
- [ ] `DELETE /api/admin/products/{id}` — soft-delete
- [ ] Tests products CRUD

### 12.5 Grades CRUD

- [ ] `GET /api/admin/grades` — listar
- [ ] `POST /api/admin/grades` — crear (code unique, product required)
- [ ] `GET /api/admin/grades/{id}` — detalle
- [ ] `PUT /api/admin/grades/{id}` — actualizar
- [ ] `DELETE /api/admin/grades/{id}` — soft-delete
- [ ] Tests grades CRUD

### 12.6 Price Lists CRUD

- [ ] `GET /api/admin/price-lists` — listar
- [ ] `POST /api/admin/price-lists` — crear
- [ ] `GET /api/admin/price-lists/{id}` — detalle con items
- [ ] `PUT /api/admin/price-lists/{id}` — actualizar
- [ ] `DELETE /api/admin/price-lists/{id}` — soft-delete
- [ ] `GET/POST/PUT/DELETE /api/admin/price-lists/{id}/items` — items CRUD
- [ ] Tests price lists CRUD

### 12.7 Dispensers + Hoses CRUD

- [ ] `GET /api/admin/dispensers` — listar
- [ ] `POST /api/admin/dispensers` — crear
- [ ] `GET /api/admin/dispensers/{id}` — detalle con hoses
- [ ] `PUT /api/admin/dispensers/{id}` — actualizar
- [ ] `DELETE /api/admin/dispensers/{id}` — soft-delete
- [ ] `GET/POST/PUT /api/admin/hoses` — hoses CRUD
- [ ] Tests dispensers + hoses CRUD

### 12.8 Emission Points CRUD

- [ ] `GET /api/admin/emission-points` — listar
- [ ] `POST /api/admin/emission-points` — crear
- [ ] `GET /api/admin/emission-points/{id}` — detalle
- [ ] `PUT /api/admin/emission-points/{id}` — actualizar
- [ ] Tests emission points CRUD

### 12.9 Company Info

- [ ] `GET /api/admin/company-info` — leer
- [ ] `PUT /api/admin/company-info` — actualizar
- [ ] Tests company info

### 12.10 System Config

- [ ] `GET /api/admin/system-config` — listar todas las keys
- [ ] `PUT /api/admin/system-config/{key}` — actualizar una key
- [ ] Tests system config

### 12.11 Payment Methods CRUD

- [ ] `GET /api/admin/payment-methods` — listar
- [ ] `POST /api/admin/payment-methods` — crear
- [ ] `PUT /api/admin/payment-methods/{id}` — actualizar
- [ ] Tests payment methods CRUD

### 12.12 Credit Contracts

- [x] Ya existe CRUD completo en `/api/pos/credit-contracts` (Phase 8)
- [ ] Revisar si necesita endpoint admin separado o basta con proteger el existente

### Criterio de salida Fase 12

```
✅ Todos los CRUD responden con paginación y búsqueda
✅ Auth admin rechaza DISPATCHER (403)
✅ Permission checker funcional
✅ Tests admin > 90% coverage
✅ git tag v0.20.0
```

---

## FASE 13 — Admin Backend Dashboard + Reportes `[v0.21.0]`

### 13.1 Dashboard

- [ ] `GET /api/admin/dashboard/summary?date_from=&date_to=`
- [ ] `GET /api/admin/dashboard/sales-by-day?date_from=&date_to=`
- [ ] `GET /api/admin/dashboard/sales-by-product?date_from=&date_to=`
- [ ] `GET /api/admin/dashboard/sales-by-payment?date_from=&date_to=`
- [ ] `GET /api/admin/dashboard/top-customers?date_from=&date_to=&limit=`
- [ ] `GET /api/admin/dashboard/top-products?date_from=&date_to=&limit=`

### 13.2 Reportes

- [ ] `GET /api/admin/reports/sales` — paginado con filtros
- [ ] `POST /api/admin/reports/sales/export` — PDF + Excel
- [ ] `GET /api/admin/reports/dispatches` — detalle con filtros
- [ ] `POST /api/admin/reports/dispatches/export` — PDF + Excel
- [ ] `GET /api/admin/reports/shifts` — histórico
- [ ] `POST /api/admin/reports/shifts/export` — PDF + Excel
- [ ] `GET /api/admin/reports/cash-summary` — flujo consolidado
- [ ] `POST /api/admin/reports/cash-summary/export` — PDF + Excel

### 13.3 Export Engine

- [ ] PDF engine (reportlab) — logo, header, tabla, footer
- [ ] Excel engine (openpyxl) — estilos, auto-filtro, congelar paneles
- [ ] Tests export

---

## FASE 14 — Admin Frontend Layout + CRUD `[v0.22.0]`

- [ ] Proyecto SvelteKit `admin/`
- [ ] AdminShell + Sidebar + Topbar responsive
- [ ] Login page admin
- [ ] Auth store + JWT interceptor
- [ ] DataTable + DataCard + FilterBar + Pagination
- [ ] Pantallas CRUD (users, products, grades, prices, dispensers, emission-points, company, config, payment-methods)

---

## FASE 15 — Admin Frontend Dashboard `[v0.23.0]`

- [ ] KPI cards
- [ ] Sales by Day (Chart.js línea)
- [ ] Sales by Product (donut)
- [ ] Sales by Payment (pie)
- [ ] Top Customers + Top Products (barras)
- [ ] Date range picker

---

## FASE 16 — Admin Frontend Reportes `[v0.24.0]`

- [ ] Sales report page
- [ ] Dispatches report page
- [ ] Shifts report page
- [ ] Cash summary page
- [ ] ExportButton → PDF / Excel

---

## FASE 17 — Cloudflare + Deploy `[v1.0.0]`

- [ ] cloudflared instalado + configurado
- [ ] Cloudflare Tunnel + DNS
- [ ] Nginx config `/admin`
- [ ] Rate limiting login
- [ ] Deploy script
- [ ] Prueba E2E pública
- [ ] Documentación final

---

## Convenciones de este documento

- **[x]** = completado y con tests pasando
- **[ ]** = pendiente
- Cada checkbox se actualiza en el commit donde se completa
- Este archivo es la fuente de verdad del progreso admin
- No duplicar tildes con ROADMAP.md — ROADMAP.md es el plan general, este es el tracker diario
