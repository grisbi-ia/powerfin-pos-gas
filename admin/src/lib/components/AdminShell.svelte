<script lang="ts">
  import { Menu, LayoutDashboard, Users, Shield, Package, Ruler, DollarSign, Truck, FileCode, Building2, Settings, CreditCard, BarChart3, LogOut, Activity, FileText } from 'lucide-svelte';
  import { currentUser, logout } from '$stores/auth';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { api } from '$lib/api/api';

  let { children } = $props();
  let mobileOpen = $state(false);
  let companyName = $state('NEOGAS');

  $effect(() => { (async () => {
    try { const c = await api.get<any>('/company-info'); companyName = c.commercial_name || c.name || 'NEOGAS'; } catch {}
  })();
  });

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/users', label: 'Usuarios', icon: Users },
    { href: '/roles', label: 'Roles', icon: Shield },
    { href: '/products', label: 'Productos', icon: Package },
    { href: '/grades', label: 'Grados', icon: Ruler },
    { href: '/price-lists', label: 'Listas de Precios', icon: DollarSign },
    { href: '/dispensers/status', label: 'Surtidores (vivo)', icon: Activity },
    { href: '/dispensers', label: 'Surtidores', icon: Truck },
    { href: '/emission-points', label: 'Puntos Emisión', icon: FileCode },
    { href: '/company-info', label: 'Empresa', icon: Building2 },
    { href: '/system-config', label: 'Configuración', icon: Settings },
    { href: '/payment-methods', label: 'Pagos', icon: CreditCard },
    { href: '/contracts', label: 'Contratos', icon: FileText },
    { href: '/reports', label: 'Reportes', icon: BarChart3 },
  ];

  function handleLogout() {
    logout();
    window.location.href = '/login';
  }
</script>

<div class="flex h-screen bg-gray-50">
  {#if mobileOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fixed inset-0 z-40 bg-black/50 lg:hidden" onclick={() => mobileOpen = false} role="presentation"></div>
  {/if}

  <aside class="fixed inset-y-0 left-0 z-50 w-64 bg-primary-900 text-white transform transition-transform duration-200
                 {mobileOpen ? 'translate-x-0' : '-translate-x-full'}
                 lg:translate-x-0 lg:static lg:z-auto flex flex-col">
    <div class="flex items-center gap-3 px-6 py-5 border-b border-primary-700">
      <div class="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center font-bold text-sm">P</div>
      <div>
        <div class="font-semibold text-sm">Powerfin GAS</div>
        <div class="text-xs text-primary-200">{companyName}</div>
      </div>
    </div>

    <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-1">
      {#each navItems as item}
        <a href={item.href}
           class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  {$page.url.pathname.startsWith(item.href)
                    ? 'bg-primary-700 text-white'
                    : 'text-primary-100 hover:bg-primary-800 hover:text-white'}"
           onclick={() => mobileOpen = false}>
          <item.icon class="w-5 h-5 flex-shrink-0" />
          {item.label}
        </a>
      {/each}
    </nav>

    <div class="border-t border-primary-700 p-4">
      <button onclick={handleLogout}
              class="flex items-center gap-2 w-full px-3 py-2 text-sm text-primary-200
                     hover:bg-primary-800 hover:text-white rounded-lg transition-colors">
        <LogOut class="w-4 h-4" /> Cerrar sesión
      </button>
    </div>
  </aside>

  <div class="flex-1 flex flex-col min-w-0">
    <header class="bg-white border-b border-gray-200 px-4 lg:px-6 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="lg:hidden p-2 -ml-2 text-gray-500 hover:text-gray-700 rounded-lg"
                onclick={() => mobileOpen = !mobileOpen}>
          <Menu class="w-5 h-5" />
        </button>
        <span class="text-sm font-semibold text-gray-700 block lg:hidden">{companyName}</span>
      </div>
      <div class="flex-1"></div>
      <div class="flex items-center gap-3">
        {#if $currentUser}
          <div class="text-right">
            <div class="text-sm font-medium text-gray-700">{$currentUser.name}</div>
            <div class="text-xs text-gray-500">{$currentUser.role}</div>
          </div>
          <div class="w-8 h-8 bg-primary-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
            {$currentUser.name.charAt(0)}
          </div>
        {/if}
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
      {@render children?.()}
    </main>
  </div>
</div>
