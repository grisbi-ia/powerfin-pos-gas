<script lang="ts">
  import { login } from '$stores/auth';
  import { goto } from '$app/navigation';
  import { LogIn } from 'lucide-svelte';

  let username = $state('');
  let password = $state('');
  let error = $state('');
  let loading = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = '';
    loading = true;
    try {
      await login(username, password);
      goto('/dashboard');
    } catch (err: any) {
      error = err.message || 'Credenciales inválidas';
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-gray-100 p-4">
  <div class="w-full max-w-sm">
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
      <div class="text-center mb-6">
        <div class="w-12 h-12 bg-primary-500 rounded-xl flex items-center justify-center mx-auto mb-3">
          <span class="text-white font-bold text-xl">P</span>
        </div>
        <h1 class="text-xl font-semibold text-gray-900">Powerfin Admin</h1>
        <p class="text-sm text-gray-500 mt-1">Acceso administrativo</p>
      </div>

      <form onsubmit={handleSubmit} class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
          <input id="username" type="text" bind:value={username} required
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                 placeholder="admin" />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
          <input id="password" type="password" bind:value={password} required
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                 placeholder="••••••••" />
        </div>

        {#if error}
          <div class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
        {/if}

        <button type="submit" disabled={loading}
                class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5
                       bg-primary-500 text-white font-medium rounded-lg
                       hover:bg-primary-600 active:bg-primary-700
                       disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          <LogIn class="w-4 h-4" />
          {loading ? 'Ingresando...' : 'Ingresar'}
        </button>
      </form>
    </div>
  </div>
</div>
