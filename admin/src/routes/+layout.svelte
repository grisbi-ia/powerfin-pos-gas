<script>
  import '../app.css';
  import { Toaster } from 'svelte-sonner';
</script>

<Toaster position="bottom-right" richColors closeButton visibleToasts={3} />
<slot />
