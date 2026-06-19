# Powerfin Admin — Interfaz de Administración

## Propósito

Interfaz de administración para la gasolinera, completamente independiente del
Powerfin POS (despacho). Mientras el POS es táctil y orientado a ventas rápidas,
Admin es una aplicación web completa para gestión de catálogos, usuarios, reportes,
gráficas y configuración del sistema.

```
┌─────────────────────┐     ┌─────────────────────┐
│   Powerfin POS      │     │   Powerfin Admin     │
│  (SvelteKit PWA)    │     │  (SvelteKit SPA)     │
│  táctil / despacho  │     │  datos / gestión     │
│  Dispatcher role    │     │  Admin/Supervisor    │
└─────────┬───────────┘     └──────────┬───────────┘
          │                            │
          │ /api/pos/*                 │ /api/admin/*
          ▼                            ▼
┌───────────────────────────────────────────────────┐
│                POS Backend (FastAPI :8080)          │
│  ┌──────────────────┐  ┌────────────────────────┐  │
│  │ /api/pos/*       │  │ /api/admin/*            │  │
│  │ 38 endpoints     │  │ CRUD + reports +        │  │
│  │ operativos       │  │ dashboard + exports     │  │
│  └──────────────────┘  └────────────────────────┘  │
│                                                     │
│              PostgreSQL (powerfin_gas)               │
└─────────────────────────────────────────────────────┘
```

---

## Principios de diseño

### 1. Separación total del POS

| Principio | Detalle |
|---|---|
| **Proyecto independiente** | `admin/` — package.json, build, y deploy propios |
| **Sin dependencia del POS** | Ningún `import` desde `pos/`. Si necesita algo compartido, va en el backend |
| **Deploy separado** | `npm run build` de admin NO toca el POS, y viceversa |
| **Cero riesgo de romper ventas** | Un bug en admin jamás afecta al despachador |

### 2. Responsive-first (obligatorio)

```
La interfaz DEBE funcionar perfectamente en:

┌──────────┐   ┌──────────────┐   ┌────────────────────┐
│  Mobile  │   │   Tablet     │   │     Desktop        │
│  < 768px │   │  768-1024px  │   │    > 1024px        │
│          │   │              │   │                    │
│ Sidebar  │   │ Sidebar      │   │ Sidebar siempre    │
│ → hambur-│   │ → colapsable │   │ visible + multi-   │
│   guesa  │   │              │   │ columna layouts    │
│ Single   │   │ 2-columnas   │   │ Data tables        │
│ column   │   │ adaptativas  │   │ completas          │
│ Charts   │   │ Charts       │   │ Charts + filtros   │
│ apilados │   │ side-by-side │   │ avanzados          │
└──────────┘   └──────────────┘   └────────────────────┘
```

**Estrategia responsive con Tailwind CSS:**

```css
/* Mobile-first breakpoints de Tailwind */
sm: 640px   → móvil landscape
md: 768px   → tablet portrait
lg: 1024px  → tablet landscape / desktop pequeño
xl: 1280px  → desktop
2xl: 1536px → desktop grande
```

**Reglas de diseño responsive:**

| Elemento | Mobile (<768px) | Tablet (768-1024px) | Desktop (>1024px) |
|---|---|---|---|
| Sidebar | Oculto, toggle hamburguesa | Colapsado a iconos | Siempre visible |
| Tablas | Cards apiladas (list view) | Tabla compacta | Tabla completa |
| Gráficas | 1 columna, altura reducida | 2 columnas | 2-3 columnas con filtros |
| Formularios | Single column, full width | 2 columnas | 2-3 columnas + panel lateral |
| KPIs dashboard | 2×2 grid | 4×1 grid | Fila horizontal |

### 3. Roles reforzados

El sistema de roles actual (DISPATCHER, SUPERVISOR, ADMIN) se refuerza con
permisos granulares para el módulo admin:

```json
// Ejemplo: permissions_json en tabla roles
{
  "ADMIN": {
    "users":        ["read", "write", "delete"],
    "roles":        ["read", "write"],
    "products":     ["read", "write", "delete"],
    "prices":       ["read", "write"],
    "grades":       ["read", "write"],
    "dispensers":   ["read", "write"],
    "emission_points": ["read", "write"],
    "company_info": ["read", "write"],
    "system_config":["read", "write"],
    "payment_methods": ["read", "write"],
    "credit_contracts": ["read", "write", "delete"],
    "dashboard":    ["read"],
    "reports":      ["read", "export"],
    "shifts":       ["read"]
  },
  "SUPERVISOR": {
    "users":        ["read"],
    "products":     ["read"],
    "prices":       ["read"],
    "grades":       ["read"],
    "dispensers":   ["read"],
    "emission_points": ["read"],
    "company_info": ["read"],
    "payment_methods": ["read"],
    "credit_contracts": ["read"],
    "dashboard":    ["read"],
    "reports":      ["read", "export"],
    "shifts":       ["read"]
  },
  "DISPATCHER": {
    // Sin acceso a /api/admin/* — solo /api/pos/*
  }
}
```

**Enforcement en backend:**

```python
# app/api/admin/deps.py
async def get_admin_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    role = await db.get(Role, current_user.role_id)
    if role.code not in ("ADMIN", "SUPERVISOR"):
        raise HTTPException(403, "Acceso restringido")
    return current_user

def require_permission(resource: str, action: str):
    """Factory para proteger endpoints individuales."""
    async def checker(
        current_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db),
    ):
        role = await db.get(Role, current_user.role_id)
        perms = role.permissions_json or {}
        allowed = perms.get(role.code, {}).get(resource, [])
        if action not in allowed:
            raise HTTPException(403, f"Permiso denegado: {action} {resource}")
        return current_user
    return checker

# Uso en endpoints:
@router.post("/users", dependencies=[Depends(require_permission("users", "write"))])
```

### 4. Autenticación admin

A diferencia del POS (que usa PIN numérico), el admin usará:

```
POS:      username + PIN (6 dígitos) → JWT 8h
Admin:    username + password        → JWT 4h (más corto por seguridad)
```

Misma tabla `users`, mismo campo `pin_hash` para compatibilidad, pero el endpoint
de login admin (`POST /api/admin/auth/login`) acepta contraseña alfanumérica.

**Alternativa:** Si no queremos tocar la tabla users, podemos agregar una columna
`password_hash` específica para admin, manteniendo `pin_hash` para el POS.
El endpoint decide cuál validar según el contexto.

---

## Arquitectura del proyecto `admin/`

```
admin/
├── package.json
├── svelte.config.js          # adapter-static (SPA)
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
├── .env.example
├── src/
│   ├── app.html
│   ├── app.css               # Tailwind directives + custom admin theme
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts              # fetch wrapper: JWT, base URL, error handling
│   │   │   ├── admin.ts               # CRUD: users, roles, products, prices, grades, etc.
│   │   │   ├── dashboard.ts           # /api/admin/dashboard/* endpoints
│   │   │   ├── reports.ts             # /api/admin/reports/* endpoints
│   │   │   ├── exports.ts             # PDF / Excel download handlers
│   │   │   └── types.ts               # TypeScript interfaces (shared via copy)
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AdminShell.svelte       # sidebar + topbar + content slot
│   │   │   │   ├── Sidebar.svelte          # navegación colapsable
│   │   │   │   ├── Topbar.svelte           # user info, logout, responsive toggle
│   │   │   │   └── Breadcrumb.svelte       # navegación jerárquica
│   │   │   ├── data/
│   │   │   │   ├── DataTable.svelte        # sort, paginate, search, responsive
│   │   │   │   ├── DataCard.svelte         # card view para mobile (fallback de tabla)
│   │   │   │   ├── FilterBar.svelte        # filtros de fecha, búsqueda, selects
│   │   │   │   └── Pagination.svelte       # controles de paginación
│   │   │   ├── charts/
│   │   │   │   ├── SalesChart.svelte       # línea/barras: ventas por día
│   │   │   │   ├── ProductChart.svelte     # donut: ventas por producto
│   │   │   │   ├── PaymentChart.svelte     # pie: ventas por método de pago
│   │   │   │   └── KpiCard.svelte          # tarjeta de métrica individual
│   │   │   ├── forms/
│   │   │   │   ├── FormField.svelte        # wrapper: label + input + error
│   │   │   │   ├── UserForm.svelte         # create/edit user
│   │   │   │   ├── ProductForm.svelte      # create/edit product
│   │   │   │   ├── PriceListForm.svelte    # create/edit price list + items
│   │   │   │   └── ConfirmDialog.svelte    # modal de confirmación (delete, etc.)
│   │   │   └── shared/
│   │   │       ├── EmptyState.svelte       # "No hay datos" con icono
│   │   │       ├── LoadingSpinner.svelte
│   │   │       ├── ErrorBanner.svelte
│   │   │       ├── ExportButton.svelte     # dropdown: PDF / Excel
│   │   │       └── StatusBadge.svelte      # active/inactive/pending
│   │   ├── stores/
│   │   │   ├── auth.ts              # JWT, user, role, permissions
│   │   │   ├── dashboard.ts         # datos de dashboard cacheados
│   │   │   └── ui.ts                # sidebar open, theme, loading states
│   │   └── utils/
│   │       ├── format.ts            # currency, date, number formatters
│   │       ├── validators.ts        # form validation (RUC, CED, etc.)
│   │       └── permissions.ts       # can(role, resource, action) helper
│   └── routes/
│       ├── +layout.svelte           # auth guard + AdminShell
│       ├── +layout.ts               # load: verifica JWT, carga user + permissions
│       ├── login/
│       │   └── +page.svelte         # login admin (username + password)
│       ├── dashboard/
│       │   └── +page.svelte         # KPIs + gráficas principales
│       ├── users/
│       │   ├── +page.svelte         # tabla de usuarios
│       │   └── [id]/
│       │       └── +page.svelte     # crear/editar usuario
│       ├── products/
│       │   ├── +page.svelte         # tabla de productos
│       │   └── [id]/
│       │       └── +page.svelte     # crear/editar producto
│       ├── grades/
│       │   ├── +page.svelte
│       │   └── [id]/
│       │       └── +page.svelte
│       ├── prices/
│       │   ├── +page.svelte         # listas de precios
│       │   └── [id]/
│       │       └── +page.svelte     # editar lista + items inline
│       ├── dispensers/
│       │   └── +page.svelte         # dispensadores + mangueras
│       ├── emission-points/
│       │   └── +page.svelte         # puntos de emisión SRI
│       ├── credit/
│       │   ├── +page.svelte         # contratos de crédito
│       │   └── [id]/
│       │       └── +page.svelte
│       ├── reports/
│       │   ├── sales/
│       │   │   └── +page.svelte     # reporte de ventas con filtros + export
│       │   ├── shifts/
│       │   │   └── +page.svelte     # histórico de turnos + detalle
│       │   └── cash/
│       │       └── +page.svelte     # flujo de caja consolidado
│       └── settings/
│           ├── company/
│           │   └── +page.svelte     # company_info
│           ├── system/
│           │   └── +page.svelte     # system_config
│           └── payment-methods/
│               └── +page.svelte
├── tests/
│   ├── api/                         # tests de API client
│   ├── components/                  # tests de componentes
│   └── routes/                      # tests de páginas
└── static/
    └── favicon.png
```

---

## Estrategia responsive — detalles de implementación

### Sidebar adaptativo

```svelte
<!-- AdminShell.svelte — pseudocódigo -->
<script>
  let sidebarOpen = false;
  $: isDesktop = typeof window !== 'undefined' && window.innerWidth >= 1024;
</script>

<div class="flex h-screen">
  <!-- Overlay mobile -->
  {#if sidebarOpen && !isDesktop}
    <div class="fixed inset-0 bg-black/50 z-40 lg:hidden"
         on:click={() => sidebarOpen = false} />
  {/if}

  <!-- Sidebar -->
  <aside class="fixed lg:static z-50 transition-transform
                {sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
                lg:translate-x-0 lg:w-64">
    <Sidebar />
  </aside>

  <!-- Main content -->
  <main class="flex-1 overflow-auto">
    <Topbar on:toggle={() => sidebarOpen = !sidebarOpen} />
    <div class="p-4 md:p-6 lg:p-8">
      <slot />
    </div>
  </main>
</div>
```

### DataTable → DataCard en mobile

```svelte
<!-- Uso responsive -->
<div class="hidden md:block">
  <DataTable {columns} {rows} />   <!-- Tabla tradicional -->
</div>
<div class="block md:hidden">
  <DataCard {rows} />              <!-- Cards apiladas -->
</div>
```

**DataCard** renderiza cada fila como una tarjeta con pares clave-valor, igual
que las tarjetas de turnos en el POS actual, pero con acciones (editar, eliminar).

### Charts responsivos

Usando Chart.js con la opción `responsive: true` y contenedores con clases Tailwind:

```svelte
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
  <div class="bg-white rounded-lg p-4">
    <SalesChart />        <!-- se redimensiona automágicamente -->
  </div>
  <div class="bg-white rounded-lg p-4">
    <ProductChart />
  </div>
  <div class="bg-white rounded-lg p-4">
    <PaymentChart />
  </div>
</div>
```

---

## Exposición a Internet con Cloudflare Tunnels

### Por qué Cloudflare Tunnels

```
Situación: La gasolinera NO tiene IP pública fija.
Solución:  cloudflared crea un túnel saliente desde el servidor Debian
           hacia Cloudflare. El tráfico entra por el tunnel sin exponer
           puertos ni requerir IP pública.

Beneficios:
  - No abre puertos en el firewall
  - SSL automático (Cloudflare edge)
  - DDoS protection incluida
  - Zero Trust: podemos agregar autenticación adicional (Cloudflare Access)
  - Sin costo (plan gratuito de Cloudflare)
```

### Topología con Cloudflare Tunnel

```
                            Internet
                               │
                    ┌──────────▼──────────┐
                    │  Cloudflare Edge     │
                    │  admin.gasolinera.com │
                    │  SSL + DDoS + WAF    │
                    └──────────┬──────────┘
                               │ tunnel saliente (HTTPS/QUIC)
                               │ iniciado por cloudflared
                               ▼
┌──────────────────────────────────────────────────┐
│  Servidor Debian (LAN 192.168.1.10)              │
│                                                   │
│  cloudflared ←──→ Nginx :443 (:80 redir)         │
│                      │                            │
│                      ├── /admin → SPA estáticos   │
│                      ├── /pos   → SPA estáticos   │
│                      └── /api   → backend :8080   │
└──────────────────────────────────────────────────┘
```

### Instalación de cloudflared en Debian 12

```bash
# Descargar e instalar
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Autenticar (esto abre un browser o da URL)
cloudflared tunnel login

# Crear el túnel
cloudflared tunnel create powerfin-admin

# Configurar — /etc/cloudflared/config.yml
```

```yaml
# /etc/cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: /home/pvalarezo/.cloudflared/<TUNNEL_ID>.json

ingress:
  # Admin — acceso público con auth fuerte
  - hostname: admin.gasolinera.com
    service: https://localhost:443
    originRequest:
      originServerName: admin.gasolinera.com

  # POS — despachadores
  - hostname: pos.gasolinera.com
    service: https://localhost:443
    originRequest:
      originServerName: pos.gasolinera.com

  # Fallback
  - service: http_status:404
```

```bash
# Instalar como servicio systemd
sudo cloudflared service install

# Verificar
sudo systemctl status cloudflared
cloudflared tunnel list
```

### Configuración DNS en Cloudflare

```
Registros DNS (gestionados automáticamente por cloudflared):
  admin.gasolinera.com  → CNAME  <TUNNEL_ID>.cfargotunnel.com
  pos.gasolinera.com    → CNAME  <TUNNEL_ID>.cfargotunnel.com
```

### Seguridad adicional con Cloudflare Access (Zero Trust)

Para el admin, podemos agregar una capa extra de autenticación antes de que el
tráfico llegue al servidor:

```
Usuario → Cloudflare Access (login email OTP) → Cloudflare Tunnel → Nginx → Admin
```

Esto protege el admin incluso si el JWT interno tiene vulnerabilidades.

**Alternativa más simple:** Cloudflare WAF rules para:
- Rate limiting en `/api/admin/auth/login` (5 intentos/min)
- Bloquear IPs sospechosas
- Country blocking (solo Ecuador)

### Nginx adaptado para Cloudflare

Con Cloudflare Tunnel, Nginx solo escucha en localhost. Cloudflare maneja SSL.

```nginx
# /etc/nginx/sites-available/powerfin-all

server {
    listen 443 ssl http2;
    server_name admin.gasolinera.com pos.gasolinera.com;

    # SSL — sigue siendo necesario para la conexión cloudflared→nginx
    ssl_certificate     /etc/letsencrypt/live/admin.gasolinera.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/admin.gasolinera.com/privkey.pem;

    # Restaurar IP real del cliente (Cloudflare envía headers)
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;
    real_ip_header CF-Connecting-IP;

    # Admin SPA
    location /admin {
        alias /var/www/admin;
        try_files $uri $uri/ /admin/index.html;
        add_header Cache-Control "no-cache";
    }

    # POS SPA
    location /pos {
        alias /var/www/pos;
        try_files $uri $uri/ /pos/index.html;
        add_header Cache-Control "public, max-age=3600";
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Rate limiting para auth
        location /api/admin/auth/login {
            limit_req zone=admin_login burst=5 nodelay;
            proxy_pass http://127.0.0.1:8080;
        }
        location /api/pos/auth/login {
            limit_req zone=pos_login burst=10 nodelay;
            proxy_pass http://127.0.0.1:8080;
        }
    }
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=admin_login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=pos_login:10m rate=10r/m;
```

---

## Exportación de reportes (PDF y Excel)

### Arquitectura de exportación

```
Frontend (admin/)                    Backend (pos_backend/)
───────────────                      ──────────────────────
1. Usuario configura filtros
2. Click "Exportar" →
   └─ dropdown: PDF | Excel
                             ───→   3. POST /api/admin/reports/sales/export
                                      body: { format, filters }
                                   4. Genera archivo en backend
                                   5. Retorna URL temporal o stream
                             ←───   6. Content-Disposition: attachment
7. Browser descarga archivo
```

### Decisiones de generación

| Formato | Biblioteca | Razón |
|---|---|---|
| **PDF** | `reportlab` | PDF nativos, sin dependencia de headless browser. Ligero (~3MB). Alternativa: `weasyprint` (HTML→PDF) para templates más bonitos pero más pesado |
| **Excel** | `openpyxl` | Archivos .xlsx nativos, estilos, fórmulas. Sin dependencia de MS Office |

### Endpoints de exportación

| Endpoint | Formato | Descripción |
|---|---|---|
| `POST /api/admin/reports/sales/export` | pdf, xlsx | Reporte de ventas con filtros |
| `POST /api/admin/reports/dispatches/export` | pdf, xlsx | Detalle de despachos |
| `POST /api/admin/reports/shifts/export` | pdf, xlsx | Histórico de turnos |
| `POST /api/admin/reports/cash/export` | pdf, xlsx | Flujo de caja |
| `POST /api/admin/reports/products/export` | xlsx | Catálogo de productos (solo Excel) |

### Ejemplo: endpoint de exportación

```python
# app/api/admin/reports.py
from io import BytesIO
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

@router.post("/reports/sales/export")
async def export_sales_report(
    body: SalesExportRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("reports", "export")),
):
    """Export sales report in PDF or Excel format."""
    # Query data with filters
    rows = await fetch_sales_data(db, body.filters)

    if body.format == "xlsx":
        buffer = build_excel(rows, body.filters)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"reporte_ventas_{body.filters.date_from}_{body.filters.date_to}.xlsx"
    else:
        buffer = build_pdf(rows, body.filters)
        media_type = "application/pdf"
        filename = f"reporte_ventas_{body.filters.date_from}_{body.filters.date_to}.pdf"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
```

### Diseño del PDF de reporte

```
┌─────────────────────────────────────────────┐
│  [LOGO]  ESTACIÓN DE SERVICIO               │
│          "POWERFIN GAS"                     │
│          RUC: 1790012345001                  │
│          Dir: Av. Principal Km 5            │
├─────────────────────────────────────────────┤
│  REPORTE DE VENTAS                          │
│  Período: 01/06/2026 — 18/06/2026          │
│  Generado: 18/06/2026 16:30 por Admin      │
├─────────────────────────────────────────────┤
│  RESUMEN                                     │
│  Total ventas:    $45,230.50                │
│  Total despachos:     1,234                 │
│  Galones vendidos:   12,450.3               │
│  Ticket promedio:      $36.67               │
├─────────────────────────────────────────────┤
│  VENTAS POR PRODUCTO                         │
│  ┌──────────┬────────┬──────────┬────────┐  │
│  │ Producto │ Galones│  Ventas  │   %    │  │
│  ├──────────┼────────┼──────────┼────────┤  │
│  │ SUPER    │ 5,200  │$18,200.00│ 40.2%  │  │
│  │ DIESEL   │ 4,800  │$14,400.00│ 31.8%  │  │
│  │ ECO PAÍS │ 2,450  │$12,650.50│ 27.9%  │  │
│  └──────────┴────────┴──────────┴────────┘  │
├─────────────────────────────────────────────┤
│  VENTAS POR DÍA                              │
│  ┌────────────┬────────┬──────────┐         │
│  │ Fecha      │ Ventas │Despachos │         │
│  ├────────────┼────────┼──────────┤         │
│  │ 01/06/2026 │$2,500  │    68    │         │
│  │ 02/06/2026 │$3,100  │    82    │         │
│  │ ...        │ ...    │   ...    │         │
│  └────────────┴────────┴──────────┘         │
├─────────────────────────────────────────────┤
│  Página 1 de 3                              │
└─────────────────────────────────────────────┘
```

---

## Endpoints del backend (`/api/admin/*`)

### Auth

| Método | Endpoint | Rol | Descripción |
|---|---|---|---|
| POST | `/api/admin/auth/login` | Cualquiera con rol admin/supervisor | Login con username + password → JWT |
| POST | `/api/admin/auth/refresh` | Admin/Supervisor | Refrescar JWT |

**Nota:** Comparte la tabla `users`. Si el usuario tiene role DISPATCHER, este
endpoint rechaza el login con 403. No se crea tabla nueva.

### CRUD — Catálogos

| Método | Endpoint | Permiso |
|---|---|---|
| GET | `/api/admin/users` | users.read |
| POST | `/api/admin/users` | users.write |
| GET | `/api/admin/users/{id}` | users.read |
| PUT | `/api/admin/users/{id}` | users.write |
| DELETE | `/api/admin/users/{id}` | users.delete |
| GET | `/api/admin/roles` | roles.read |
| POST | `/api/admin/roles` | roles.write |
| PUT | `/api/admin/roles/{id}` | roles.write |
| GET | `/api/admin/products` | products.read |
| POST | `/api/admin/products` | products.write |
| PUT | `/api/admin/products/{id}` | products.write |
| GET | `/api/admin/grades` | grades.read |
| POST | `/api/admin/grades` | grades.write |
| PUT | `/api/admin/grades/{id}` | grades.write |
| GET | `/api/admin/price-lists` | prices.read |
| POST | `/api/admin/price-lists` | prices.write |
| PUT | `/api/admin/price-lists/{id}` | prices.write |
| GET | `/api/admin/price-lists/{id}/items` | prices.read |
| POST | `/api/admin/price-lists/{id}/items` | prices.write |
| PUT | `/api/admin/price-lists/{id}/items/{itemId}` | prices.write |
| DELETE | `/api/admin/price-lists/{id}/items/{itemId}` | prices.write |
| GET | `/api/admin/dispensers` | dispensers.read |
| POST | `/api/admin/dispensers` | dispensers.write |
| PUT | `/api/admin/dispensers/{id}` | dispensers.write |
| GET | `/api/admin/hoses` | dispensers.read |
| POST | `/api/admin/hoses` | dispensers.write |
| PUT | `/api/admin/hoses/{id}` | dispensers.write |
| GET | `/api/admin/emission-points` | emission_points.read |
| POST | `/api/admin/emission-points` | emission_points.write |
| PUT | `/api/admin/emission-points/{id}` | emission_points.write |
| GET | `/api/admin/company-info` | company_info.read |
| PUT | `/api/admin/company-info` | company_info.write |
| GET | `/api/admin/system-config` | system_config.read |
| PUT | `/api/admin/system-config/{key}` | system_config.write |
| GET | `/api/admin/payment-methods` | payment_methods.read |
| POST | `/api/admin/payment-methods` | payment_methods.write |
| PUT | `/api/admin/payment-methods/{id}` | payment_methods.write |

### Dashboard

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/admin/dashboard/summary?date_from=&date_to=` | KPIs: total ventas, despachos, galones, clientes, ticket promedio |
| GET | `/api/admin/dashboard/sales-by-day?date_from=&date_to=` | Ventas diarias para gráfica de línea |
| GET | `/api/admin/dashboard/sales-by-product?date_from=&date_to=` | Ventas agrupadas por producto (donut) |
| GET | `/api/admin/dashboard/sales-by-payment?date_from=&date_to=` | Ventas por método de pago (pie) |
| GET | `/api/admin/dashboard/top-customers?date_from=&date_to=&limit=10` | Clientes top por monto |
| GET | `/api/admin/dashboard/top-products?date_from=&date_to=&limit=10` | Productos top por cantidad |

### Reports (con export)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/admin/reports/sales?date_from=&date_to=&...` | Reporte de ventas paginado |
| POST | `/api/admin/reports/sales/export` | Export PDF/Excel |
| GET | `/api/admin/reports/dispatches?date_from=&date_to=&...` | Detalle de despachos |
| POST | `/api/admin/reports/dispatches/export` | Export PDF/Excel |
| GET | `/api/admin/reports/shifts?date_from=&date_to=&user_id=` | Histórico de turnos |
| POST | `/api/admin/reports/shifts/export` | Export PDF/Excel |
| GET | `/api/admin/reports/cash-summary?date_from=&date_to=` | Flujo de caja consolidado |
| POST | `/api/admin/reports/cash-summary/export` | Export PDF/Excel |

---

## Gráficas del dashboard

### Layout del dashboard principal

```
Desktop (>1024px)
┌──────────────────────────────────────────────────────────────┐
│  Dashboard                                    18/06/2026     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Ventas   │ │ Despachos│ │ Clientes │ │ Ticket Prom. │   │
│  │$45,230.50│ │   1,234  │ │    892   │ │   $36.67     │   │
│  │ ↑12%     │ │ ↑8%     │  │ ↑15%    │ │   ↑3%        │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                               │
│  ┌─────────────────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ Ventas por Día (línea) │ │Por Producto  │ │Por Pago  │  │
│  │ ▂▃▅▇▆█▃▅▃▇█▆▅▃        │ │  (donut)    │ │  (pie)   │  │
│  │                        │ │ SUPER  40%  │ │ Efect 55%│  │
│  │                        │ │ DIESEL 32%  │ │ Tjt  30% │  │
│  │                        │ │ ECO   28%   │ │ QR   15% │  │
│  └─────────────────────────┘ └──────────────┘ └──────────┘  │
│                                                               │
│  ┌──────────────────────────────┐ ┌───────────────────────┐   │
│  │ Top Clientes (bar horiz)     │ │ Top Productos (bar)   │   │
│  │ Juan Pérez    ████████ $5,200│ │ SUPER     ██████ 5200│   │
│  │ Trans Andes   ██████   $4,800│ │ DIESEL    █████  4800│   │
│  │ María Gómez   ████     $3,100│ │ ECO PAÍS  ████   2450│   │
│  └──────────────────────────────┘ └───────────────────────┘   │
└──────────────────────────────────────────────────────────────┘

Mobile (<768px)
┌─────────────────────┐
│  Dashboard          │
│  ┌───────────────┐  │
│  │ Ventas        │  │
│  │ $45,230.50    │  │
│  │ ↑12%          │  │
│  ├───────────────┤  │
│  │ Despachos     │  │
│  │ 1,234  ↑8%   │  │
│  ├───────────────┤  │
│  │ Clientes      │  │
│  │ 892    ↑15%   │  │
│  ├───────────────┤  │
│  │ Ticket Prom.  │  │
│  │ $36.67 ↑3%    │  │
│  └───────────────┘  │
│                     │
│  Ventas por Día     │
│  ┌─────────────────┐│
│  │  📈 chart       ││
│  │  (full width)   ││
│  └─────────────────┘│
│                     │
│  Por Producto       │
│  ┌─────────────────┐│
│  │  🍩 donut      ││
│  └─────────────────┘│
│                     │
│  Por Método Pago    │
│  ┌─────────────────┐│
│  │  🥧 pie        ││
│  └─────────────────┘│
└─────────────────────┘
```

---

## Fases de desarrollo (Admin)

### Fase Admin 1 — Backend CRUD + Auth (1.5 semanas)

```
☐ POST /api/admin/auth/login       — login admin (username+password, JWT 4h)
☐ Admin auth guard                 — role.code in (ADMIN, SUPERVISOR)
☐ Permission checker               — require_permission(resource, action)
☐ CRUD /api/admin/users            — GET/POST/PUT/DELETE + search + pagination
☐ CRUD /api/admin/roles            — GET/POST/PUT
☐ CRUD /api/admin/products         — GET/POST/PUT/DELETE + search + pagination
☐ CRUD /api/admin/grades           — GET/POST/PUT/DELETE
☐ CRUD /api/admin/price-lists      — GET/POST/PUT/DELETE + items CRUD
☐ CRUD /api/admin/dispensers       — GET/POST/PUT + hoses CRUD
☐ CRUD /api/admin/emission-points  — GET/POST/PUT
☐ CRUD /api/admin/company-info     — GET/PUT
☐ CRUD /api/admin/system-config    — GET/PUT (by key)
☐ CRUD /api/admin/payment-methods  — GET/POST/PUT
☐ Tests completos (pytest) para admin endpoints
```

### Fase Admin 2 — Dashboard + Reportes API (1 semana)

```
☐ GET /api/admin/dashboard/summary              — KPIs con rango de fechas
☐ GET /api/admin/dashboard/sales-by-day         — serie temporal
☐ GET /api/admin/dashboard/sales-by-product     — agrupación por producto
☐ GET /api/admin/dashboard/sales-by-payment     — agrupación por método de pago
☐ GET /api/admin/dashboard/top-customers        — ranking clientes
☐ GET /api/admin/dashboard/top-products         — ranking productos
☐ GET /api/admin/reports/sales                  — reporte paginado con filtros
☐ POST /api/admin/reports/sales/export          — PDF + Excel
☐ GET /api/admin/reports/dispatches             — detalle con filtros
☐ POST /api/admin/reports/dispatches/export     — PDF + Excel
☐ GET /api/admin/reports/shifts                 — histórico turnos
☐ POST /api/admin/reports/shifts/export         — PDF + Excel
☐ GET /api/admin/reports/cash-summary           — flujo consolidado
☐ POST /api/admin/reports/cash-summary/export   — PDF + Excel
☐ Biblioteca PDF (reportlab) + Excel (openpyxl) integradas
☐ Tests completos para dashboard y reportes
```

### Fase Admin 3 — Frontend base + Layout responsive (1 semana)

```
☐ SvelteKit project setup (admin/)
☐ Tailwind CSS + tema personalizado
☐ Layout: AdminShell + Sidebar + Topbar
☐ Sidebar responsive (hamburguesa mobile, colapsable tablet, fijo desktop)
☐ Auth store + login page (username/password)
☐ JWT interceptor en api/client.ts (auto-refresh, redirect on 401)
☐ Permission-based route guarding (+layout.ts)
☐ Breadcrumb dinámico
☐ Componentes base: LoadingSpinner, ErrorBanner, EmptyState, StatusBadge
☐ Componentes de datos: DataTable, DataCard, Pagination, FilterBar
☐ Componentes de formulario: FormField, ConfirmDialog
```

### Fase Admin 4 — Pantallas CRUD (2 semanas)

```
☐ Users CRUD screen               — tabla + formulario create/edit
☐ Products CRUD screen            — tabla + formulario con categorías
☐ Grades CRUD screen              — tabla + formulario con productos
☐ Price Lists CRUD screen         — tabla + edición inline de items
☐ Dispensers + Hoses screen       — tabla + formulario
☐ Emission Points screen          — tabla + formulario
☐ Company Info screen             — formulario de campos
☐ System Config screen            — key-value editor
☐ Payment Methods screen          — tabla + formulario
☐ Credit Contracts screen         — tabla + formulario (aprovecha API existente)
☐ ExportButton en todas las tablas (CSV descarga simple)
```

### Fase Admin 5 — Dashboard + Gráficas (1 semana)

```
☐ Dashboard page con KPIs cards
☐ Sales by Day chart (línea/barras con Chart.js)
☐ Sales by Product chart (donut)
☐ Sales by Payment Method chart (pie)
☐ Top Customers (barra horizontal)
☐ Top Products (barra vertical)
☐ Date range picker con presets (hoy, ayer, 7d, 30d, este mes)
☐ Responsive: charts se reorganizan en mobile
```

### Fase Admin 6 — Reportes + Exportación (1 semana)

```
☐ Sales report page con filtros avanzados + tabla paginada
☐ Dispatches report page
☐ Shifts report page
☐ Cash summary report page
☐ Botón Export en cada reporte → dropdown PDF / Excel
☐ Descarga con feedback visual (spinner durante generación)
☐ PDF diseñado con logo, header, resumen, tabla, footer
☐ Excel con estilos, congelar paneles, auto-filtro
```

### Fase Admin 7 — Cloudflare + Deploy + Hardening (1 semana)

```
☐ Instalar y configurar cloudflared en servidor Debian
☐ Configurar Cloudflare Tunnel + DNS
☐ Configurar Nginx para admin con rate limiting
☐ Cloudflare WAF rules (rate limit login, country block)
☐ Certbot SSL para dominio interno (cloudflared→nginx)
☐ Script deploy.sh actualizado para admin/
☐ systemd service para cloudflared
☐ Prueba de acceso público: https://admin.gasolinera.com
☐ Tests end-to-end: login admin → CRUD producto → ver en POS
☐ Documentación final actualizada
```

---

## Temas adicionales a definir

### 1. ¿Qué pasa con los endpoints `/api/pos/` existentes?

Los endpoints actuales de lectura (`/api/pos/products`, `/api/pos/price-lists`,
`/api/pos/dispatch-types`) **se mantienen sin cambios** para el POS. El admin usa
sus propios endpoints `/api/admin/*`.

**No se duplica lógica de negocio.** Los servicios del backend (sequential_service,
credit_service, etc.) son compartidos. Solo se agregan routers nuevos.

### 2. Paginación y búsqueda

Todos los endpoints CRUD del admin deben soportar:

```
GET /api/admin/users?search=juan&page=1&page_size=20&sort=name&order=asc
```

El POS actual no pagina (los catálogos son pequeños), pero admin sí debe paginar
porque maneja tablas completas con potencial de crecer.

### 3. Soft delete vs hard delete

| Tabla | Estrategia | Razón |
|---|---|---|
| users | Soft delete (is_active=false) | Integridad referencial con shifts, dispatches |
| products | Soft delete | Referenciados por dispatch_details |
| grades | Soft delete | Referenciados por hoses, price_list_items |
| price_lists | Soft delete | Referenciados por persons, vehicles |
| dispensers | Soft delete | Referenciados por dispatches |
| emission_points | Soft delete | Referenciados por dispatches |
| price_list_items | Hard delete | Sin dependencias fuertes |
| hoses | Hard delete (si dispenser activo) | Sin dependencias históricas |

### 4. Auditoría

Para cumplimiento y trazabilidad:

```sql
-- Tabla de auditoría para cambios desde admin
CREATE TABLE audit_log (
    audit_id      SERIAL PRIMARY KEY,
    table_name    VARCHAR(50) NOT NULL,
    record_id     INTEGER NOT NULL,
    action        VARCHAR(10) NOT NULL,  -- CREATE, UPDATE, DELETE
    changed_by    INTEGER NOT NULL REFERENCES users(user_id),
    old_values    JSONB,
    new_values    JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Esto es **opcional fase 1**, pero recomendado para producción. Permite saber
quién cambió qué y cuándo.

### 5. Dark mode

Tailwind CSS facilita dark mode con la clase `dark:`. El admin puede incluir
un toggle en el Topbar que persista en localStorage. Bajo esfuerzo, alto valor
para el admin que trabaja de noche.

### 6. Notificaciones in-app

Para acciones críticas (cambio de precio, desactivación de usuario, etc.),
mostrar toast notifications con feedback claro:

```svelte
<!-- +layout.svelte -->
<Toaster />  <!-- posición fija, stack de notificaciones -->
```

Librería sugerida: `svelte-french-toast` o `svelte-sonner` — ligeras, accesibles.

### 7. Actualización en tiempo real

Si dos admins están trabajando simultáneamente (raro pero posible), considerar:

- **Pesimista:** No implementar. La probabilidad de colisión es baja.
- **Optimista:** Al guardar, verificar `updated_at`. Si cambió desde que se cargó → warning.
- **SSE:** Mismo mecanismo que el POS para notificar cambios de catálogo.

Recomendación: empezar sin real-time. Agregar si se vuelve necesario.

---

## Stack técnico — Admin

```yaml
framework: SvelteKit 2.x + TypeScript
styling: Tailwind CSS 3.x
charts: Chart.js 4.x + svelte-chartjs (wrapper ligero)
icons: Lucide Icons (tree-shakeable, SVG)
http: fetch nativo (sin axios — menos dependencias)
adapter: '@sveltejs/adapter-static' (SPA)
testing: Vitest + @testing-library/svelte
package_manager: npm
```

---

## Convenciones de código — Admin

| Regla | Detalle |
|---|---|
| **Idioma** | Código y comentarios: inglés. UI visible: español |
| **Componentes** | PascalCase: `DataTable.svelte`, `KpiCard.svelte` |
| **Rutas** | kebab-case: `/emission-points`, `/price-lists` |
| **Stores** | camelCase: `authStore`, `dashboardStore` |
| **API client** | Funciones nombradas por recurso: `adminApi.users.list()`, `adminApi.products.create()` |
| **Manejo de errores** | Nunca silent. Mostrar ErrorBanner o toast. Sin try/catch vacíos |
| **Carga de datos** | SvelteKit load functions en +layout.ts/+page.ts para SSR/CSR |

---

## Fecha: 2026-06-18 | Versión: 1.0-draft | Documento: ADMIN_UI.md
