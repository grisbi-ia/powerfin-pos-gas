# PowerFin POS — Documentación Técnica

## ¿Qué es el Powerfin POS?

Aplicación web progresiva (PWA) optimizada para celulares y tablets
que usan los despachadores en la estación de servicio.

```
NO tiene base de datos propia.
NO tiene lógica de negocio propia.
NO calcula precios ni genera facturas.
ES la interfaz táctil del sistema — rápida, simple, eficiente.
```

Habla con **dos backends**:

- **PowerFin ERP** → negocio (login, clientes, precios, ventas, turnos)
- **FusionBridge** → hardware (estado surtidores, autorizar, imprimir)

---

## Stack tecnológico

```
Framework:   SvelteKit 2.x
Lenguaje:    TypeScript
Estilos:     Tailwind CSS 3.x
Iconos:      Lucide Svelte
HTTP:        Fetch API nativa
SSE:         EventSource API nativa del browser
PWA:         @vite-pwa/sveltekit
Estado:      Svelte stores (sin librerías extra)
Build:       Vite
Deploy:      Archivos estáticos servidos por Nginx
```

---

## Estructura del proyecto

```
pos/
├── src/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── powerfin.ts        ← cliente REST hacia PowerFin
│   │   │   ├── bridge.ts          ← cliente REST/SSE hacia FusionBridge
│   │   │   └── types.ts           ← tipos TypeScript compartidos
│   │   ├── stores/
│   │   │   ├── auth.ts            ← sesión del usuario
│   │   │   ├── dispensers.ts      ← estado surtidores (via SSE)
│   │   │   └── shift.ts           ← turno activo
│   │   ├── components/
│   │   │   ├── DispenserCard.svelte
│   │   │   ├── CustomerSearch.svelte
│   │   │   ├── PinKeyboard.svelte
│   │   │   ├── AmountInput.svelte
│   │   │   ├── OfflineBanner.svelte
│   │   │   └── PrintPrompt.svelte  ← pregunta si desea ticket
│   │   └── utils/
│   │       ├── currency.ts
│   │       └── plate.ts
│   │
│   └── routes/
│       ├── +layout.svelte          ← auth guard
│       ├── login/
│       │   └── +page.svelte
│       ├── shift/
│       │   ├── open/+page.svelte
│       │   └── close/+page.svelte
│       └── (pos)/                  ← grupo protegido
│           ├── +layout.svelte
│           ├── +page.svelte        ← pantalla principal (surtidores)
│           ├── new-dispatch/
│           │   └── +page.svelte
│           ├── fueling/
│           │   └── +page.svelte    ← progreso en tiempo real
│           ├── confirmation/
│           │   └── +page.svelte    ← resumen + manejo de impresión
│           └── history/
│               └── +page.svelte
│
├── static/
│   ├── manifest.json
│   └── icons/
├── tests/
├── svelte.config.js
├── vite.config.ts
└── package.json
```

---

## Variables de entorno (.env.local para desarrollo)

```bash
PUBLIC_POWERFIN_URL=http://localhost:8080
PUBLIC_BRIDGE_URL=http://localhost:8090
```

En producción estas URLs apuntan al mismo servidor vía Nginx:

```bash
PUBLIC_POWERFIN_URL=https://pos.gasolinera.com
PUBLIC_BRIDGE_URL=https://pos.gasolinera.com/bridge
```

---

## Cliente hacia FusionBridge (bridge.ts)

```typescript
// src/lib/api/bridge.ts

const BRIDGE_URL = import.meta.env.PUBLIC_BRIDGE_URL;

// ── REST ──────────────────────────────────────────────────

export async function authorizeDispatch(data: AuthorizeData) {
  const res = await fetch(`${BRIDGE_URL}/api/dispatch/authorize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Authorization failed: ${res.status}`);
  return res.json();
}

export async function cancelDispatch(dispenserId: number, orderId: string) {
  const res = await fetch(`${BRIDGE_URL}/api/dispatch/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dispenser_id: dispenserId, order_id: orderId }),
  });
  return res.ok;
}

// Consultar política de impresión al arrancar la app
export async function getPrintPolicy(): Promise<"ALWAYS" | "ASK" | "NEVER"> {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/print/policy`);
    const data = await res.json();
    return data.policy;
  } catch {
    return "ASK"; // valor por defecto si no se puede consultar
  }
}

// Solicitar impresión de ticket
export async function printReceipt(data: PrintReceiptData): Promise<boolean> {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/print`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── SSE — eventos en tiempo real ──────────────────────────

export function connectToEvents(handlers: EventHandlers): EventSource {
  const es = new EventSource(`${BRIDGE_URL}/api/events`);

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);
    switch (data.type) {
      case "DISPENSER_STATUS":
        handlers.onDispenserStatus?.(data);
        break;
      case "FUELING_PROGRESS":
        handlers.onFuelingProgress?.(data);
        break;
      case "SALE_COMPLETED":
        handlers.onSaleCompleted?.(data);
        break;
      case "FUSION_DISCONNECTED":
        handlers.onDisconnected?.();
        break;
      case "FUSION_CONNECTED":
        handlers.onConnected?.();
        break;
    }
  };

  es.onerror = () => console.warn("SSE reconnecting...");
  return es;
}

export interface EventHandlers {
  onDispenserStatus?: (e: DispenserStatusEvent) => void;
  onFuelingProgress?: (e: FuelingProgressEvent) => void;
  onSaleCompleted?: (e: SaleCompletedEvent) => void;
  onDisconnected?: () => void;
  onConnected?: () => void;
}
```

---

## Store de configuración (config.ts)

```typescript
// src/lib/stores/config.ts
import { writable } from "svelte/store";
import { getPrintPolicy } from "$lib/api/bridge";

export type PrintPolicy = "ALWAYS" | "ASK" | "NEVER";

export const printPolicy = writable<PrintPolicy>("ASK");

// Cargar al arrancar la app
export async function loadConfig() {
  const policy = await getPrintPolicy();
  printPolicy.set(policy);
}
```

---

## Pantalla de confirmación con manejo de impresión

```svelte
<!-- src/routes/(pos)/confirmation/+page.svelte -->
<script lang="ts">
    import { onMount }       from 'svelte';
    import { goto }          from '$app/navigation';
    import { page }          from '$app/stores';
    import { printPolicy }   from '$lib/stores/config';
    import { printReceipt }  from '$lib/api/bridge';
    import type { DispatchOrder, LocationInfo } from '$lib/api/types';

    // Los datos llegan via state de navegación desde FuelingPage
    let order:    DispatchOrder   = $page.state.order;
    let location: LocationInfo    = $page.state.location;

    let printStatus: 'idle' | 'printing' | 'done' | 'error' | 'skipped' = 'idle';

    onMount(async () => {
        // Si la política es ALWAYS, imprimir automáticamente sin preguntar
        if ($printPolicy === 'ALWAYS') {
            await handlePrint();
        }
        // Si es ASK → mostrar botones (flujo normal)
        // Si es NEVER → no mostrar nada de impresión
    });

    async function handlePrint() {
        printStatus = 'printing';
        const success = await printReceipt({
            type:        'FUEL_RECEIPT',
            dispenser_id: order.dispenser_id,
            fuel_data: {
                location_name:    location.name,
                location_address: location.address,
                location_ruc:     location.ruc,
                date:             formatDate(order.completed_at),
                time:             formatTime(order.completed_at),
                dispenser_id:     order.dispenser_id,
                hose_id:          order.hose_id,
                grade:            order.grade,
                volume:           order.actual_volume.toFixed(3),
                unit_price:       order.unit_price.toFixed(3),
                amount:           order.actual_amount.toFixed(2),
                payment_method:   order.payment_method,
                customer_name:    order.customer_name ?? '',
                plate:            order.plate ?? '',
                invoice_id:       order.invoice_id ?? '',
                invoice_auth:     order.invoice_auth ?? ''
            }
        });
        printStatus = success ? 'done' : 'error';
    }

    function handleSkip() {
        printStatus = 'skipped';
    }

    function formatDate(iso: string) {
        return new Date(iso).toLocaleDateString('es-EC');
    }
    function formatTime(iso: string) {
        return new Date(iso).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
    }
</script>

<div class="min-h-screen bg-gray-900 p-4 flex flex-col">

    <!-- Resumen del despacho -->
    <div class="bg-green-900 rounded-2xl p-5 mb-4">
        <div class="text-center mb-3">
            <span class="text-4xl">✅</span>
            <h2 class="text-white text-xl font-bold mt-2">Despacho completado</h2>
        </div>
        <div class="text-white space-y-2">
            <div class="flex justify-between">
                <span class="text-gray-300">Producto</span>
                <span class="font-bold">{order.grade}</span>
            </div>
            <div class="flex justify-between">
                <span class="text-gray-300">Volumen</span>
                <span class="font-bold">{order.actual_volume.toFixed(3)} litros</span>
            </div>
            <div class="flex justify-between">
                <span class="text-gray-300">Precio</span>
                <span>${order.unit_price.toFixed(3)}/litro</span>
            </div>
            <div class="border-t border-green-700 pt-2 flex justify-between">
                <span class="text-gray-300">Total</span>
                <span class="text-2xl font-bold">${order.actual_amount.toFixed(2)}</span>
            </div>
            {#if order.change_amount > 0}
                <div class="flex justify-between text-yellow-300">
                    <span>Vuelto</span>
                    <span class="font-bold">${order.change_amount.toFixed(2)}</span>
                </div>
            {/if}
        </div>
        {#if order.invoice_id}
            <div class="mt-3 bg-green-800 rounded-lg p-2 text-center">
                <p class="text-gray-300 text-xs">Factura SRI</p>
                <p class="text-white font-mono text-sm">{order.invoice_id}</p>
            </div>
        {/if}
    </div>

    <!-- Sección de impresión según política -->
    {#if $printPolicy !== 'NEVER'}
        <div class="bg-gray-800 rounded-2xl p-4 mb-4">

            {#if printStatus === 'idle' && $printPolicy === 'ASK'}
                <!-- Preguntar al despachador -->
                <p class="text-white text-center mb-4 text-lg">
                    ¿El cliente desea ticket?
                </p>
                <div class="grid grid-cols-2 gap-3">
                    <button
                        on:click={handlePrint}
                        class="bg-blue-600 text-white rounded-xl p-4 text-lg
                               font-bold active:scale-95 transition-transform"
                    >
                        🖨 SÍ, IMPRIMIR
                    </button>
                    <button
                        on:click={handleSkip}
                        class="bg-gray-600 text-white rounded-xl p-4 text-lg
                               font-bold active:scale-95 transition-transform"
                    >
                        ✗ NO, GRACIAS
                    </button>
                </div>

            {:else if printStatus === 'printing'}
                <p class="text-yellow-400 text-center">🖨 Imprimiendo ticket...</p>

            {:else if printStatus === 'done'}
                <p class="text-green-400 text-center">✅ Ticket impreso</p>

            {:else if printStatus === 'error'}
                <div class="text-center">
                    <p class="text-red-400">⚠️ Error al imprimir</p>
                    <button
                        on:click={handlePrint}
                        class="mt-2 text-blue-400 underline text-sm"
                    >
                        Reintentar
                    </button>
                </div>

            {:else if printStatus === 'skipped'}
                <p class="text-gray-400 text-center text-sm">Sin ticket físico</p>
            {/if}

        </div>
    {/if}

    <!-- Botón nueva venta -->
    {#if printStatus !== 'idle' || $printPolicy === 'NEVER'}
        <button
            on:click={() => goto('/')}
            class="bg-blue-600 text-white rounded-2xl p-5 text-xl
                   font-bold text-center active:scale-95 transition-transform mt-auto"
        >
            Nueva venta
        </button>
    {/if}

</div>
```

---

## DispenserCard.svelte

```svelte
<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { Dispenser }        from '$lib/api/types';

    export let dispenser: Dispenser;
    const dispatch = createEventDispatcher();

    const STATUS_CONFIG: Record<string, { color: string; label: string; canSell: boolean }> = {
        IDLE:       { color: 'bg-green-600',  label: 'Disponible',       canSell: true  },
        CALLING:    { color: 'bg-blue-600',   label: 'Cliente esperando',canSell: true  },
        AUTHORIZED: { color: 'bg-yellow-600', label: 'Autorizado',       canSell: false },
        FUELLING:   { color: 'bg-orange-600', label: 'Despachando',      canSell: false },
        PAUSED:     { color: 'bg-purple-600', label: 'Pausado',          canSell: false },
        STOPPED:    { color: 'bg-red-600',    label: 'Detenido',         canSell: false },
        ERROR:      { color: 'bg-red-800',    label: 'Error',            canSell: false },
        CLOSED:     { color: 'bg-gray-600',   label: 'Cerrado',          canSell: false },
    };

    $: config = STATUS_CONFIG[dispenser.status] ?? STATUS_CONFIG['CLOSED'];
</script>

<button
    on:click={() => config.canSell && dispatch('select')}
    class="rounded-2xl p-5 text-white text-left w-full transition-transform
           active:scale-95 {config.color}
           {config.canSell ? 'cursor-pointer' : 'cursor-not-allowed opacity-70'}"
>
    <p class="text-sm opacity-75">Surtidor {dispenser.fusion_pump_id}</p>
    <p class="text-2xl font-bold mt-1">{config.label}</p>
    {#if dispenser.status === 'FUELLING'}
        <div class="mt-3 bg-white/20 rounded-full h-2">
            <div class="bg-white rounded-full h-2 w-1/2 transition-all"></div>
        </div>
    {/if}
</button>
```

---

## PinKeyboard.svelte

```svelte
<script lang="ts">
    export let value:     string = '';
    export let maxLength: number = 6;

    const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫'];

    function press(key: string) {
        if (key === '⌫') {
            value = value.slice(0, -1);
        } else if (key && value.length < maxLength) {
            value += key;
        }
    }
</script>

<!-- Indicadores de dígitos -->
<div class="flex justify-center gap-3 mb-4">
    {#each Array(maxLength) as _, i}
        <div class="w-4 h-4 rounded-full border-2 border-gray-500
                    {i < value.length ? 'bg-blue-500 border-blue-500' : ''}">
        </div>
    {/each}
</div>

<!-- Teclado numérico -->
<div class="grid grid-cols-3 gap-3">
    {#each keys as key}
        {#if key === ''}
            <div></div>
        {:else}
            <button
                type="button"
                on:click={() => press(key)}
                class="bg-gray-700 text-white rounded-xl text-2xl font-bold py-4
                       active:scale-90 active:bg-gray-600 transition-transform"
            >
                {key}
            </button>
        {/if}
    {/each}
</div>
```

---

## PWA Manifest

```json
{
  "name": "Powerfin POS",
  "short_name": "POS",
  "description": "Sistema de despacho de combustible NEOPAUTE",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#111827",
  "theme_color": "#111827",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

---

## Tipos TypeScript (types.ts)

```typescript
export interface User {
  user_id: number;
  name: string;
  username: string;
  role: "ADMIN" | "SUPERVISOR" | "DISPATCHER";
  location_id: number;
  location_name: string;
}

export interface Dispenser {
  dispenser_id: number;
  fusion_pump_id: number;
  name: string;
  status: string;
  sub_status: string;
  hose?: string;
  last_updated?: Date;
}

export interface Customer {
  customer_id: string;
  id_type: string;
  id_number: string;
  name: string;
  email?: string;
  phone?: string;
  price_list: string;
  price_list_name: string;
  plates: string[];
}

export interface Shift {
  shift_id: number;
  user_id: number;
  user_name: string;
  opened_at: string;
  accounting_date: string;
  status: "OPEN" | "CLOSED";
  opening_cash: number;
  dispenser_ids: number[];
}

export interface DispatchOrder {
  dispatch_order_id: string;
  shift_id: number;
  customer_id?: string;
  customer_name?: string;
  plate?: string;
  dispenser_id: number;
  hose_id: number;
  grade: string;
  preset_type: "MONEY" | "VOLUME";
  preset_value: string;
  unit_price: number;
  payment_method: string;
  actual_volume: number;
  actual_amount: number;
  change_amount: number;
  status: string;
  invoice_id?: string;
  invoice_auth?: string;
  completed_at: string;
}

export interface LocationInfo {
  location_id: number;
  name: string;
  address: string;
  ruc: string;
}

export interface PrintReceiptData {
  type: "FUEL_RECEIPT";
  dispenser_id: number;
  fuel_data: {
    location_name: string;
    location_address: string;
    location_ruc: string;
    date: string;
    time: string;
    dispenser_id: number;
    hose_id: number;
    grade: string;
    volume: string;
    unit_price: string;
    amount: string;
    payment_method: string;
    customer_name: string;
    plate: string;
    invoice_id: string;
    invoice_auth: string;
  };
}

// Eventos SSE desde FusionBridge
export interface DispenserStatusEvent {
  type: "DISPENSER_STATUS";
  dispenserId: number;
  status: string;
  subStatus: string;
}

export interface FuelingProgressEvent {
  type: "FUELING_PROGRESS";
  dispenserId: number;
  volume: string;
  amount: string;
}

export interface SaleCompletedEvent {
  type: "SALE_COMPLETED";
  dispenserId: number;
  orderId: string;
  volume: string;
  amount: string;
}
```
