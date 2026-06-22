<script lang="ts">
  import '../app.css';
  import { Toaster } from 'svelte-sonner';
  import { browser } from '$app/environment';

  let { children } = $props();
</script>

{#if browser}
  <Toaster position="bottom-right" richColors closeButton visibleToasts={3} />
{/if}

{@render children?.()}
