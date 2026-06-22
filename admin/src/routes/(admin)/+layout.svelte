<script lang="ts">
  import AdminShell from '$components/AdminShell.svelte';
  import { isAuthenticated } from '$stores/auth';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let { children } = $props();

  $effect(() => { (async () => {
    if (!$isAuthenticated && $page.url.pathname !== '/') {
      goto('/');
    }
  })();
});
</script>

{#if $isAuthenticated}
  <AdminShell>
    {@render children?.()}
  </AdminShell>
{:else}
  {@render children?.()}
{/if}
