# UX Standards — Powerfin POS & Admin

## Propósito

Documento canónico de estándares de UI/UX para todos los proyectos frontend
del ecosistema Powerfin POS. Cualquier agente (LLM, coding agent, desarrollador)
debe consultar este documento antes de crear o modificar componentes visuales.

## ⚠️ PROTECCIÓN DEL CÓDIGO EXISTENTE (LEER PRIMERO)

```
┌─────────────────────────────────────────────────────────────────┐
│  REGLA #1: NO REFACTORIZAR POS POR ESTÉTICA                     │
│                                                                 │
│  El proyecto pos/ está en producción y es funcionalmente        │
│  correcto. Este documento es:                                   │
│                                                                 │
│  • PRESCRIPTIVO para admin/  → todo código NUEVO debe          │
│    seguir estos estándares al pie de la letra                   │
│                                                                 │
│  • DESCRIPTIVO para pos/     → documenta lo que YA existe       │
│    como referencia. NO modificar pos/ solo para "alinear"      │
│    con este documento.                                          │
│                                                                 │
│  • POS solo se modifica por:                                    │
│    - Nuevos features funcionales                                 │
│    - Bug fixes                                                   │
│    - Cambios de requisitos del negocio                           │
│    NUNCA por "estandarización visual" o "consistencia"          │
│    con admin/.                                                   │
│                                                                 │
│  • Si un nuevo feature en pos/ toca UI existente, se aplican    │
│    los estándares SOLO al código NUEVO, no al circundante.      │
│                                                                 │
│  • Si hay conflicto entre este doc y el código POS existente:   │
│    GANA EL CÓDIGO POS. Este documento se actualiza para         │
│    reflejar la realidad, no al revés.                            │
└─────────────────────────────────────────────────────────────────┘
```

```
Aplica a:
  pos/      → Powerfin POS (despachadores, táctil, PWA)
               ⚠️ SOLO LECTURA — no modificar por estándares
  admin/    → Powerfin Admin (administradores, responsive, SPA)
               ✅ APLICAR obligatoriamente

Regla de oro:
  Consistencia DENTRO de cada proyecto.
  No forzar consistencia ENTRE proyectos si rompe producción.
  Si no está en este documento, preguntar antes de inventar.
```

---

## 1. Design Tokens — Paleta de colores

### Colores de marca

```css
:root {
  /* ── Primary (acciones principales, marca) ── */
  --color-primary-50:  #eff6ff;   /* fondo suave */
  --color-primary-100: #dbeafe;
  --color-primary-200: #bfdbfe;
  --color-primary-500: #3b82f6;   /* principal */
  --color-primary-600: #2563eb;   /* hover */
  --color-primary-700: #1d4ed8;   /* active/pressed */
  --color-primary-900: #1e3a5f;   /* sidebar, headers oscuros */

  /* ── Secondary (acciones secundarias) ── */
  --color-secondary-500: #6b7280;
  --color-secondary-600: #4b5563;

  /* ── Semantic — Éxito ── */
  --color-success-50:  #f0fdf4;
  --color-success-500: #22c55e;
  --color-success-600: #16a34a;
  --color-success-700: #15803d;

  /* ── Semantic — Advertencia ── */
  --color-warning-50:  #fffbeb;
  --color-warning-500: #f59e0b;
  --color-warning-600: #d97706;

  /* ── Semantic — Error / Peligro ── */
  --color-danger-50:  #fef2f2;
  --color-danger-500: #ef4444;
  --color-danger-600: #dc2626;
  --color-danger-700: #b91c1c;

  /* ── Semantic — Info ── */
  --color-info-50:  #f0f9ff;
  --color-info-500: #0ea5e9;
  --color-info-600: #0284c7;

  /* ── Neutrals (fondos, bordes, texto) ── */
  --color-gray-50:  #f9fafb;
  --color-gray-100: #f3f4f6;
  --color-gray-200: #e5e7eb;
  --color-gray-300: #d1d5db;
  --color-gray-400: #9ca3af;
  --color-gray-500: #6b7280;
  --color-gray-600: #4b5563;
  --color-gray-700: #374151;
  --color-gray-800: #1f2937;
  --color-gray-900: #111827;
}
```

### Uso por contexto

| Contexto | Color | Ejemplo |
|---|---|---|
| Botón principal | `primary-500` bg, white text | "Guardar", "Autorizar" |
| Botón secundario | white bg, `gray-300` border | "Cancelar", "Volver" |
| Botón peligroso | `danger-500` bg, white text | "Eliminar", "Anular" |
| Link / acción texto | `primary-600` text, underline on hover | "Editar", "Ver detalle" |
| Badge éxito | `success-50` bg, `success-700` text | "COMPLETED", "Activo" |
| Badge error | `danger-50` bg, `danger-700` text | "CANCELLED", "Error" |
| Badge warning | `warning-50` bg, `warning-600` text | "PENDING", "Pendiente" |
| Badge neutral | `gray-100` bg, `gray-600` text | "INACTIVE" |
| Sidebar | `primary-900` o `gray-900` | Navegación lateral |
| Fondo página | `gray-50` | POS y Admin |
| Card / panel | white bg, `gray-200` border, rounded-lg shadow-sm | Contenedores |

### Colores por estado de dispensador (POS)

| Estado | Color bg | Color texto | Icono |
|---|---|---|---|
| IDLE | `gray-100` | `gray-600` | Circle (gris) |
| CALLING | `warning-50` | `warning-600` | Phone (amarillo) |
| AUTHORIZED | `primary-50` | `primary-600` | CheckCircle (azul) |
| FUELLING | `success-50` | `success-600` | Fuel (verde, animado) |
| STOPPED | `danger-50` | `danger-600` | AlertTriangle (rojo) |

---

## 2. Tipografía

```css
:root {
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}
```

### Escala tipográfica (Tailwind)

| Clase | Tamaño | Uso |
|---|---|---|
| `text-xs` | 12px | Badges, labels pequeños, metadata |
| `text-sm` | 14px | Texto de tabla, campos de formulario, breadcrumb |
| `text-base` | 16px | Texto de cuerpo, párrafos, inputs |
| `text-lg` | 18px | Subtítulos de card, títulos de sección |
| `text-xl` | 20px | Títulos de página (mobile) |
| `text-2xl` | 24px | Títulos de página (desktop) |
| `text-3xl` | 30px | KPIs, números grandes en dashboard |
| `text-4xl` | 36px | KPI principal en hero |

**Pesos:**
- `font-normal` — texto cuerpo
- `font-medium` — labels, botones, navegación
- `font-semibold` — títulos de card, encabezados de tabla
- `font-bold` — títulos de página, KPIs

**Monospace:** Solo para códigos (order_id, sequential_number, RUC, placa).

---

## 3. Espaciado

Usar el sistema de Tailwind. **Nunca hardcodear px en CSS inline.**

### Espaciado entre elementos

| Contexto | Clase | Valor |
|---|---|---|
| Padding de página | `p-4 md:p-6 lg:p-8` | 16px → 24px → 32px |
| Gap entre cards en grid | `gap-4` | 16px |
| Gap entre items en lista | `gap-2` o `gap-3` | 8-12px |
| Separación entre secciones | `mb-6` o `mb-8` | 24-32px |
| Padding interno de card | `p-4` o `p-6` | 16-24px |
| Padding de botón | `px-4 py-2` | 16px horizontal, 8px vertical |
| Padding de input | `px-3 py-2` | 12px horizontal, 8px vertical |

### Bordes redondeados

| Elemento | Clase |
|---|---|
| Botones | `rounded-lg` (8px) |
| Cards / paneles | `rounded-lg` (8px) |
| Inputs / selects | `rounded-md` (6px) |
| Modales | `rounded-xl` (12px) |
| Badges / chips | `rounded-full` (pill) |
| Tablas | `rounded-lg` con `overflow-hidden` |

---

## 4. Componentes UI — Catálogo

### 4.1 Botones

**Regla: un solo estilo por contexto. No improvisar variantes.**

```svelte
<!-- Botón primario — acción principal -->
<button class="inline-flex items-center gap-2 px-4 py-2
               bg-blue-500 text-white font-medium rounded-lg
               hover:bg-blue-600 active:bg-blue-700
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors">
  <Icon name="save" class="w-4 h-4" />
  Guardar
</button>

<!-- Botón secundario — acción alternativa -->
<button class="inline-flex items-center gap-2 px-4 py-2
               bg-white text-gray-700 font-medium rounded-lg
               border border-gray-300
               hover:bg-gray-50 active:bg-gray-100
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors">
  Cancelar
</button>

<!-- Botón peligroso — acción destructiva -->
<button class="inline-flex items-center gap-2 px-4 py-2
               bg-red-500 text-white font-medium rounded-lg
               hover:bg-red-600 active:bg-red-700
               focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors">
  <Icon name="trash" class="w-4 h-4" />
  Eliminar
</button>

<!-- Botón ghost — acción discreta en tabla/fila -->
<button class="inline-flex items-center gap-1 px-2 py-1
               text-gray-500 hover:text-blue-600 hover:bg-blue-50
               rounded-md transition-colors"
        title="Editar">
  <Icon name="edit" class="w-4 h-4" />
</button>

<!-- Botón icono — solo icono, sin texto -->
<button class="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50
               rounded-lg transition-colors"
        title="Exportar">
  <Icon name="download" class="w-5 h-5" />
</button>
```

**Tamaños de botón:**

| Size | Clases | Uso |
|---|---|---|
| `sm` | `px-3 py-1.5 text-sm` | Tablas, toolbars |
| `md` (default) | `px-4 py-2 text-sm` | Formularios, cards |
| `lg` | `px-6 py-3 text-base` | CTAs principales, login |

**Jerarquía visual por pantalla:**
- Máximo **un** botón primario por formulario/sección
- Botón primario siempre a la **derecha** (o abajo en mobile)
- Acciones destructivas separadas visualmente de las constructivas

### 4.2 Inputs y formularios

```svelte
<!-- Campo de texto estándar -->
<div class="space-y-1">
  <label for="name" class="block text-sm font-medium text-gray-700">
    Nombre <span class="text-red-500">*</span>
  </label>
  <input
    id="name"
    type="text"
    bind:value={form.name}
    placeholder="Ej: Juan Pérez"
    class="block w-full px-3 py-2 text-sm
           border border-gray-300 rounded-md
           placeholder-gray-400
           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
           disabled:bg-gray-100 disabled:text-gray-500
           aria-invalid={errors.name ? 'true' : undefined}"
  />
  {#if errors.name}
    <p class="text-sm text-red-600 flex items-center gap-1">
      <Icon name="alertCircle" class="w-3.5 h-3.5" />
      {errors.name}
    </p>
  {/if}
</div>

<!-- Select / Dropdown -->
<select class="block w-full px-3 py-2 text-sm
               border border-gray-300 rounded-md
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
               disabled:bg-gray-100">
  <option value="">Seleccionar...</option>
  {#each options as opt}
    <option value={opt.value}>{opt.label}</option>
  {/each}
</select>

<!-- Checkbox / Toggle -->
<label class="inline-flex items-center gap-2 cursor-pointer">
  <input type="checkbox" bind:checked={value}
         class="w-4 h-4 text-blue-500 border-gray-300 rounded
                focus:ring-blue-500" />
  <span class="text-sm text-gray-700">Activo</span>
</label>
```

**Layout de formulario:**

```
Desktop (2-3 columnas):       Mobile (1 columna):
┌──────────────────────┐      ┌──────────────┐
│ Nombre    │ RUC      │      │ Nombre       │
│           │          │      │              │
│ Email     │ Teléfono │      │ RUC          │
│           │          │      │              │
│ Dirección (full)     │      │ Email        │
│                      │      │              │
│ [Cancelar] [Guardar] │      │ Teléfono     │
└──────────────────────┘      │              │
                              │ Dirección    │
                              │              │
                              │ [Guardar]    │
                              │ [Cancelar]   │
                              └──────────────┘
```

Tailwind grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4`

### 4.3 Tablas de datos (DataTable)

```svelte
<!-- Contenedor con borde redondeado y shadow -->
<div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
  <!-- Toolbar: búsqueda + filtros + acciones -->
  <div class="px-4 py-3 border-b border-gray-200 flex flex-col sm:flex-row gap-3">
    <!-- Search input -->
    <div class="relative flex-1">
      <Icon name="search" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input placeholder="Buscar..."
             class="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-md
                    focus:outline-none focus:ring-2 focus:ring-blue-500" />
    </div>
    <!-- Acciones -->
    <button class="...primary...">
      <Icon name="plus" class="w-4 h-4" /> Nuevo
    </button>
    <ExportButton />  <!-- solo en admin -->
  </div>

  <!-- Tabla (desktop) -->
  <div class="hidden md:block overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Columna
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100 bg-white">
        <tr class="hover:bg-gray-50 transition-colors">
          <td class="px-4 py-3 text-sm text-gray-700">Dato</td>
        </tr>
      </tbody>
      <!-- Empty state (ver sección 5.3) -->
      <tbody>
        <tr>
          <td colspan="99" class="px-4 py-12">
            <EmptyState message="No se encontraron resultados" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Cards (mobile fallback) — ver sección 4.4 -->
  <div class="md:hidden divide-y divide-gray-100">
    <DataCard {row} />
  </div>

  <!-- Paginación -->
  <Pagination />
</div>
```

**Columnas de tabla — reglas:**
- Encabezados: `text-xs font-semibold text-gray-500 uppercase tracking-wider`
- Celdas: `text-sm text-gray-700` (dato normal), `text-gray-900 font-medium` (dato principal como nombre)
- Montos: alineados a la derecha, `font-mono` para cifras
- Estados: usar `StatusBadge` (nunca texto plano de color)
- Acciones: máximo 3 iconos ghost por fila (editar, eliminar, ver). Si hay más → menú dropdown "..."

**Columnas sortables:**
```svelte
<th class="px-4 py-3 text-left cursor-pointer select-none
           hover:bg-gray-100 transition-colors"
    on:click={() => sort('name')}>
  <span class="inline-flex items-center gap-1">
    Nombre
    <Icon name="chevronUpDown" class="w-3.5 h-3.5 text-gray-400" />
  </span>
</th>
```

### 4.4 DataCard (mobile fallback de tabla)

```svelte
<!-- DataCard.svelte — reemplaza filas de tabla en mobile -->
<div class="px-4 py-3 hover:bg-gray-50 transition-colors">
  <div class="flex items-start justify-between">
    <div class="space-y-1.5">
      <!-- Campo principal (nombre/título) -->
      <p class="text-sm font-medium text-gray-900">{row.name}</p>
      <!-- Campos secundarios como key-value -->
      <div class="flex items-center gap-1.5 text-xs text-gray-500">
        <span class="font-medium">Código:</span>
        <span class="font-mono">{row.code}</span>
      </div>
      <div class="flex items-center gap-1.5 text-xs text-gray-500">
        <span class="font-medium">Categoría:</span>
        <span>{row.category}</span>
      </div>
    </div>
    <!-- Badge de estado + acciones -->
    <div class="flex flex-col items-end gap-2">
      <StatusBadge status={row.status} />
      <div class="flex gap-1">
        <button class="ghost-icon" title="Editar"><Icon name="edit" class="w-4 h-4"/></button>
        <button class="ghost-icon" title="Eliminar"><Icon name="trash" class="w-4 h-4"/></button>
      </div>
    </div>
  </div>
</div>
```

### 4.5 StatusBadge

```svelte
<!-- StatusBadge.svelte — NUNCA usar texto coloreado sin badge -->
<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
             {badgeClass}">
  <span class="w-1.5 h-1.5 rounded-full {dotClass}"></span>
  {label}
</span>
```

| Estado | bg | text | dot |
|---|---|---|---|
| Activo / COMPLETED / COLLECTED | `bg-green-50` | `text-green-700` | `bg-green-500` |
| Inactivo / CANCELLED | `bg-red-50` | `text-red-700` | `bg-red-500` |
| Pendiente / AUTHORIZED / OPEN | `bg-yellow-50` | `text-yellow-700` | `bg-yellow-500` |
| Procesando / FUELLING | `bg-blue-50` | `text-blue-700` | `bg-blue-500` (animado) |

### 4.6 Modales (ConfirmDialog)

**Usar modal para:**
- Confirmación de eliminación
- Confirmación de acción destructiva
- Formularios cortos que no justifican página nueva (máx 4 campos)

**NO usar modal para:**
- Formularios largos de creación/edición (→ página dedicada)
- Información no crítica (→ toast)
- Wizard flows (→ página step-by-step)

```svelte
<!-- ConfirmDialog.svelte -->
{#if open}
  <!-- Overlay -->
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4"
       role="dialog" aria-modal="true">
    <!-- Backdrop -->
    <div class="fixed inset-0 bg-black/50 transition-opacity"
         on:click={onCancel}></div>

    <!-- Panel (centrado, responsive) -->
    <div class="relative bg-white rounded-xl shadow-xl
                w-full max-w-md p-6
                transform transition-all">

      <!-- Icono (opcional, contextual) -->
      <div class="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4
                  {iconBgClass}">
        <Icon name={iconName} class="w-6 h-6 {iconColorClass}" />
      </div>

      <!-- Título -->
      <h3 class="text-lg font-semibold text-gray-900 text-center mb-2">
        {title}
      </h3>

      <!-- Mensaje -->
      <p class="text-sm text-gray-500 text-center mb-6">
        {message}
      </p>

      <!-- Acciones -->
      <div class="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
        <button class="secondary w-full sm:w-auto" on:click={onCancel}>
          Cancelar
        </button>
        <button class="{dangerClass} w-full sm:w-auto" on:click={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
```

**Variantes de modal por tipo:**

| Tipo | Icono | Icono bg | Botón confirmación |
|---|---|---|---|
| `danger` | `alertTriangle` | `bg-red-100 text-red-600` | Botón peligroso rojo |
| `warning` | `alertCircle` | `bg-yellow-100 text-yellow-600` | Botón primario |
| `info` | `info` | `bg-blue-100 text-blue-600` | Botón primario |

### 4.7 Notificaciones Toast

```svelte
<!-- Usar svelte-sonner o svelte-french-toast -->
<!-- Configuración global en +layout.svelte -->
<Toaster
  position="bottom-right"
  richColors
  closeButton
  visibleToasts={3}
/>

<!-- Uso en cualquier componente -->
<script>
  import { toast } from 'svelte-sonner';
</script>

<!-- Éxito -->
toast.success('Producto guardado correctamente');

<!-- Error -->
toast.error('No se pudo guardar: cupo insuficiente');

<!-- Info -->
toast.info('Cargando datos...');

<!-- Promesa (loading → success/error) -->
toast.promise(saveProduct(data), {
  loading: 'Guardando producto...',
  success: 'Producto guardado',
  error: 'Error al guardar',
});
```

**Reglas de toast:**
- Éxito: verde, auto-dismiss 3s
- Error: rojo, auto-dismiss 6s (más tiempo para leer)
- Info: azul, auto-dismiss 3s
- Promesa: loading persiste hasta resolver
- **Máximo 3 toasts visibles** simultáneos
- **Nunca** usar `alert()` nativo del browser

---

## 5. Patrones de estado

### 5.1 Loading (carga de datos)

**Spinner global (carga inicial de página):**

```svelte
<div class="flex items-center justify-center min-h-[400px]">
  <div class="flex flex-col items-center gap-3">
    <div class="w-8 h-8 border-2 border-blue-500 border-t-transparent
                rounded-full animate-spin"></div>
    <p class="text-sm text-gray-500">Cargando...</p>
  </div>
</div>
```

**Skeleton (carga de contenido con estructura conocida):**

```svelte
<!-- Skeleton para tabla -->
<div class="animate-pulse space-y-3 p-4">
  <div class="h-4 bg-gray-200 rounded w-1/4"></div>  <!-- header -->
  {#each Array(5) as _}
    <div class="h-12 bg-gray-100 rounded"></div>      <!-- filas -->
  {/each}
</div>
```

Usar skeleton para tablas, cards de dashboard, y listas. Usar spinner para páginas completas y exports.

### 5.2 Error

```svelte
<!-- ErrorBanner — error recuperable (p.ej. API caída) -->
<div class="bg-red-50 border border-red-200 rounded-lg p-4
            flex items-start gap-3">
  <Icon name="alertCircle" class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
  <div class="flex-1">
    <h4 class="text-sm font-medium text-red-800">
      {title || 'Error al cargar datos'}
    </h4>
    <p class="text-sm text-red-600 mt-1">{message}</p>
    {#if retryAction}
      <button class="mt-2 text-sm font-medium text-red-700 hover:text-red-800 underline"
              on:click={retryAction}>
        Reintentar
      </button>
    {/if}
  </div>
  <button class="text-red-400 hover:text-red-600" on:click={dismiss}>
    <Icon name="x" class="w-4 h-4" />
  </button>
</div>
```

**Error inline (campo de formulario):**
- Texto rojo debajo del input, icono `alertCircle` 14px
- `aria-invalid="true"` en el input
- Ver sección 4.2

### 5.3 Empty State

```svelte
<!-- EmptyState — "no hay datos" -->
<div class="flex flex-col items-center justify-center py-12 text-center px-4">
  <Icon name="{icon}" class="w-12 h-12 text-gray-300 mb-4" />
  <h3 class="text-sm font-medium text-gray-900 mb-1">
    {title || 'No hay datos'}
  </h3>
  <p class="text-sm text-gray-500 max-w-sm">
    {message || 'No se encontraron resultados con los filtros actuales.'}
  </p>
  {#if actionLabel}
    <button class="primary mt-4" on:click={action}>
      <Icon name="plus" class="w-4 h-4" /> {actionLabel}
    </button>
  {/if}
</div>
```

**Iconos por contexto:**

| Contexto | Icono |
|---|---|
| Búsqueda sin resultados | `search` |
| Lista vacía (CRUD) | `inbox` o `packageOpen` |
| Sin ventas en rango | `barChart3` |
| Sin notificaciones | `bellOff` |

---

## 6. Flujos de interacción

### 6.1 CRUD estándar

```
LIST PAGE                           FORM PAGE (o modal si ≤4 campos)
┌──────────────────────┐            ┌──────────────────────┐
│ [Buscar...] [Nuevo] │            │ ← Volver  [Guardar]  │
│                      │  click    │                      │
│ Tabla paginada       │ ────────→ │ Formulario           │
│  ┌──────────────┐    │  "Nuevo"  │  Nombre: [...]       │
│  │ Fila 1 [✏️🗑️] │   │  o ✏️    │  Email:  [...]       │
│  │ Fila 2 [✏️🗑️] │   │           │  Activo: [✓]         │
│  │ Fila 3 [✏️🗑️] │   │           │                      │
│  └──────────────┘    │           │ [Cancelar] [Guardar] │
│  ← 1 2 3 ... 10 →   │           └──────────────────────┘
└──────────────────────┘
        │
        │ click 🗑️
        ▼
┌──────────────────┐
│  Modal confirm   │
│  ¿Eliminar X?    │
│  [Cancelar][Sí]  │
└──────────────────┘
```

**Reglas de flujo CRUD:**
1. **Crear/Editar**: Navegar a página dedicada `/[resource]/[id]` (id = 'new' para crear)
2. **Eliminar**: Modal de confirmación. Nunca eliminar sin confirmar.
3. **Guardar**: Toast success → redirect a lista. Si error → toast error, mantener en formulario.
4. **Cancelar**: Volver a lista sin confirmación (a menos que el formulario esté dirty → modal "¿Descartar cambios?").
5. **Dirty detection**: Track si el form cambió. Si navega sin guardar → confirmar.

### 6.2 Wizard / Multi-step (solo POS — SaleWizard)

```
Step 1: Customer → Step 2: Fuel → Step 3: Payment → Step 4: Confirm

Barra de progreso siempre visible en el top:
[●──────────]  [●──────────]  [●──────────]  [●──────────]
 Cliente       Combustible    Pago           Confirmación
```

**Reglas de wizard:**
- Navegación lineal: solo avanzar, no saltar pasos
- Botón "Atrás" para volver al paso anterior (sin perder datos)
- Cada paso se valida antes de avanzar
- Resumen antes de confirmar (step final)
- No puede salir del wizard sin completar o cancelar explícitamente

### 6.3 Export (solo Admin)

```
1. Usuario configura filtros en pantalla de reporte
2. Click botón "Exportar" → dropdown: [PDF] [Excel]
3. Se muestra toast.loading: "Generando reporte..."
4. Al completar:
   - Éxito: toast.success + descarga automática del archivo
   - Error: toast.error con mensaje
5. El archivo se descarga vía Content-Disposition: attachment
```

**ExportButton:**

```svelte
<div class="relative">
  <button class="secondary" on:click={toggle}>
    <Icon name="download" class="w-4 h-4" /> Exportar
    <Icon name="chevronDown" class="w-3 h-3" />
  </button>
  {#if open}
    <div class="absolute right-0 mt-1 bg-white rounded-lg shadow-lg
                border border-gray-200 py-1 w-36 z-50">
      <button class="w-full px-3 py-2 text-sm text-gray-700
                     hover:bg-gray-50 flex items-center gap-2"
              on:click={() => export_('pdf')}>
        <Icon name="fileText" class="w-4 h-4 text-red-500" /> PDF
      </button>
      <button class="w-full px-3 py-2 text-sm text-gray-700
                     hover:bg-gray-50 flex items-center gap-2"
              on:click={() => export_('xlsx')}>
        <Icon name="fileSpreadsheet" class="w-4 h-4 text-green-600" /> Excel
      </button>
    </div>
  {/if}
</div>
```

---

## 7. Iconografía

### Librería: Lucide Icons

```bash
npm install lucide-svelte
```

```svelte
<script>
  import { Save, Trash2, Edit, Search, Plus, Download, ChevronDown } from 'lucide-svelte';
</script>

<Save class="w-4 h-4" />
```

**Tamaños estándar:**
- Botones y acciones: `w-4 h-4` (16px)
- Iconos standalone (empty state): `w-12 h-12` (48px)
- KPIs dashboard: `w-8 h-8` (32px)
- Nav sidebar: `w-5 h-5` (20px)

**Mapping de acciones → iconos (obligatorio):**

| Acción | Icono | Color (opcional) |
|---|---|---|
| Guardar / Crear | `save` | — |
| Editar | `edit` (o `pencil`) | — |
| Eliminar | `trash2` | `text-red-500` en hover |
| Cancelar / Cerrar | `x` | — |
| Volver / Atrás | `arrowLeft` | — |
| Buscar | `search` | — |
| Filtrar | `filter` | — |
| Exportar | `download` | — |
| PDF | `fileText` | `text-red-500` |
| Excel | `fileSpreadsheet` | `text-green-600` |
| Agregar / Nuevo | `plus` | — |
| Refrescar | `refreshCw` | — |
| Configuración | `settings` | — |
| Usuario | `user` | — |
| Dashboard | `layoutDashboard` | — |
| Reportes | `barChart3` | — |
| Productos | `package` | — |
| Precios | `dollarSign` | — |
| Despachos | `truck` | — |
| Caja | `wallet` | — |
| Ver / Detalle | `eye` | — |
| Imprimir | `printer` | — |
| Copiar | `copy` | — |
| Notificaciones | `bell` | — |
| Menú (hamburguesa) | `menu` | — |
| Cerrar sesión | `logOut` | — |
| Check / Sí | `check` | — |

**NO usar:** emojis como iconos. Siempre Lucide SVG.

---

## 8. Layout responsive

### 8.1 AdminShell (admin)

```
Desktop (>1024px):              Mobile (<768px):
┌───┬──────────────────┐        ┌─────────────────┐
│ S │ Topbar            │        │ ☰ Topbar        │
│ i │                   │        ├─────────────────┤
│ d │                   │        │                 │
│ e │   Content         │        │   Content       │
│ b │                   │        │   (scroll)      │
│ a │                   │        │                 │
│ r │                   │        │                 │
└───┴──────────────────┘        └─────────────────┘
                                 Sidebar = overlay
                                 al hacer tap en ☰
```

**Sidebar items:** Icono + texto en desktop, solo icono en tablet (768-1024px), overlay en mobile.

### 8.2 POS Shell

```
Mobile siempre (PWA):
┌─────────────────┐
│ Header (user,   │
│  turno, hora)   │
├─────────────────┤
│                 │
│   Content       │
│   (scroll)      │
│                 │
├─────────────────┤
│ Bottom Nav      │
│ [🏠] [💰] [📋] │
└─────────────────┘
```

POS no tiene sidebar. Navegación inferior con tabs (máx 4).

---

## 9. Gráficas (admin dashboard)

### Librería: Chart.js + svelte-chartjs

```bash
npm install chart.js svelte-chartjs
```

### Tipos de gráfica y cuándo usarlos

| Tipo | Cuándo | Ejemplo |
|---|---|---|
| **Línea** (`line`) | Series temporales (ventas por día/semana/mes) | Ventas diarias |
| **Barra** (`bar`) | Comparar categorías, rankings | Top productos, top clientes |
| **Barra horizontal** (`bar`, indexAxis: 'y') | Rankings con etiquetas largas | Top clientes |
| **Donut** (`doughnut`) | Proporciones (3-6 categorías) | Ventas por producto |
| **Pie** (`pie`) | Proporciones (≤5 categorías) | Ventas por método de pago |

### Configuración base obligatoria

```typescript
// lib/charts/config.ts — importar en cada gráfica
export const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        usePointStyle: true,  // círculos en vez de rectángulos
        padding: 20,
        font: { size: 12, family: 'Inter, system-ui, sans-serif' },
      },
    },
    tooltip: {
      backgroundColor: '#1f2937',  // gray-800
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 12,
      cornerRadius: 8,
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 } },
    },
    y: {
      grid: { color: '#f3f4f6' },  // gray-100
      ticks: { font: { size: 11 } },
    },
  },
};

// Colores consistentes para datasets
export const chartColors = {
  blue:   '#3b82f6',
  green:  '#22c55e',
  yellow: '#f59e0b',
  red:    '#ef4444',
  purple: '#8b5cf6',
  teal:   '#14b8a6',
  orange: '#f97316',
  pink:   '#ec4899',
};
```

### Contenedor de gráfica

```svelte
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
  <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Día</h3>
  <div class="relative h-64 md:h-80">
    <Bar {data} {options} />
  </div>
</div>
```

**Altura fija** en el contenedor (`h-64` o `h-80`) para que todas las gráficas del dashboard tengan la misma altura. Chart.js se adapta vía `maintainAspectRatio: false` + `responsive: true`.

---

## 10. Formateo de datos

### Moneda (USD)

```typescript
// lib/utils/format.ts
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-EC', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}
// $1,234.56
```

### Fechas

```typescript
export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('es-EC', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(date));
}
// 18/06/2026

export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat('es-EC', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
}
// 18/06/2026 16:30
```

### Números

```typescript
export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('es-EC', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}
// 1.234 → "1.234" (miles con punto, español Ecuador)
```

### Galones / Cantidades

```typescript
export function formatGallons(value: number): string {
  return new Intl.NumberFormat('es-EC', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 3,
  }).format(value);
}
// 12.450 → "12,450"
```

**Regla:** Siempre usar `Intl` nativo del browser. Formato `es-EC` para compatibilidad con Ecuador.

---

## 11. Accesibilidad (mínimo obligatorio)

| Requisito | Implementación |
|---|---|
| **Labels en inputs** | Todo `<input>` tiene `<label>` asociado vía `for`/`id` |
| **Textos alternativos** | Iconos decorativos: `aria-hidden="true"`. Iconos accionables: `aria-label` |
| **Contraste** | Texto ≥ 4.5:1 ratio sobre fondo. Verificar con Tailwind defaults |
| **Focus visibile** | `focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` en interactivos |
| **Keyboard nav** | Modales: <kbd>Esc</kbd> cierra, <kbd>Tab</kbd> dentro del modal, focus trap |
| **aria en modales** | `role="dialog" aria-modal="true"` |
| **aria en errores** | `aria-invalid="true"` + `aria-describedby` apuntando al mensaje de error |
| **Loading states** | `aria-busy="true"` en contenedores durante carga |

---

## 12. Convenciones de código UI

### Nombrado de componentes

```
Componentes reutilizables → PascalCase:  DataTable.svelte, KpiCard.svelte
Páginas (rutas)          → kebab-case:  +page.svelte (ruta /emission-points)
Stores                   → camelCase:   authStore, dashboardStore
Utilidades               → camelCase:   formatCurrency, canEdit
```

### Props de componente

```svelte
<script lang="ts">
  // Props obligatorias primero
  export let items: Item[];

  // Props opcionales con default
  export let loading = false;
  export let error = '';

  // Callbacks: on:event (Svelte 4) o callback prop (Svelte 5)
  export let onEdit: (id: number) => void = () => {};
  export let onDelete: (id: number) => void = () => {};
</script>
```

### Estructura de archivo Svelte

```svelte
<script lang="ts">
  // 1. Imports
  // 2. Props
  // 3. Estado local
  // 4. Derivados ($:)
  // 5. Funciones
</script>

<!-- HTML / Svelte template -->

<style>
  /* Solo si es necesario — preferir Tailwind */
</style>
```

### CSS: Tailwind > style scoped > CSS global

1. **Tailwind classes** en el markup — primera opción siempre
2. **`<style>` scoped** solo para cosas que Tailwind no puede (animaciones complejas, print styles)
3. **CSS global** solo en `app.css` para design tokens, fuentes, reset

**Nunca:**
- CSS inline (`style="..."`)
- Mezclar `class={variable}` de Tailwind con clases condicionales manuales — usar `clsx` o template literals
- Hardcodear colores en hex fuera de los design tokens

---

## 13. Performance

| Regla | Implementación |
|---|---|
| **Lazy loading** | Rutas de admin: `import()` dinámico (SvelteKit lo hace automático) |
| **Imágenes** | Optimizar con `imagetools` de Vite si hay logos/imágenes |
| **Tablas grandes** | Paginación en backend (nunca cargar 1000+ filas al frontend) |
| **Charts** | Import dinámico de `chart.js` si no está en la ruta inicial |
| **Bundle size** | Chart.js es ~60KB gzipped. No agregar más librerías de charts |

---

## 14. Errores comunes a evitar

| ❌ Mal | ✅ Bien |
|---|---|
| `alert('Error')` | `toast.error('Mensaje descriptivo')` |
| `style="color: red"` | `class="text-red-600"` (Tailwind) |
| Botón sin padding | `px-4 py-2` mínimo |
| Texto plano para estados | `<StatusBadge status={...} />` |
| Spinner custom inventado | Clases `animate-spin` de Tailwind |
| Modal sin overlay oscuro | `bg-black/50` backdrop |
| Tabla sin hover | `hover:bg-gray-50` en filas |
| Input sin placeholder | Siempre incluir `placeholder` descriptivo |
| Mensaje de error genérico | Mostrar error del backend, no "Algo salió mal" |
| Botón sin estado disabled | `disabled={loading}` durante submits |
| Doble submit | `disabled={loading}` + prevenir con flag |
| Skip empty/loading/error state | Siempre manejar los 4 estados: loading, empty, error, data |
| Emojis como iconos | Usar Lucide SVG |

---

## 15. Referencia rápida para agentes

Al recibir un requerimiento de UI, el agente debe:

1. **Consultar este documento** para colores, componentes, patrones
2. **Identificar el proyecto**: ¿es `pos/` (táctil, mobile-first, PWA) o `admin/` (responsive, desktop-first pero adaptativo)?
3. **Revisar los 4 estados**: loading, empty, error, data
4. **Usar componentes existentes**: `DataTable`, `StatusBadge`, `ConfirmDialog`, `ErrorBanner`, `EmptyState`, `KpiCard` — no reinventar
5. **Si necesita un componente nuevo**: ¿realmente es nuevo o se puede componer con los existentes?
6. **Tailwind primero**: no `<style>` a menos que sea estrictamente necesario
7. **Toast para feedback**: nunca `alert()`
8. **Probar los 3 breakpoints**: mobile (<768), tablet (768-1024), desktop (>1024)
9. **Testear accesibilidad mínima**: labels, aria, focus, keyboard

---

## Fecha: 2026-06-18 | Versión: 1.0 | Documento: UX_STANDARDS.md
