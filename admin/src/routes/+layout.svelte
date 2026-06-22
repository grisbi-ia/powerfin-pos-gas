<script lang="ts">
  import '../app.css';
  import { Toaster } from 'svelte-sonner';
  let { children } = $props();
</script>

<Toaster position="bottom-right" richColors closeButton visibleToasts={3} />
{@render children?.()}
