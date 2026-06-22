<script lang="ts">
  let { open = false, title = 'Confirmar acción', message = '¿Está seguro?',
        confirmLabel = 'Eliminar', variant = 'danger',
        onConfirm, onCancel } = $props<{
          open?: boolean; title?: string; message?: string; confirmLabel?: string;
          variant?: 'danger' | 'warning'; onConfirm?: () => void; onCancel?: () => void;
        }>();

  const variants = {
    danger: { iconBg: 'bg-red-100', iconColor: 'text-red-600', btnClass: 'bg-red-500 hover:bg-red-600 text-white' },
    warning: { iconBg: 'bg-yellow-100', iconColor: 'text-yellow-600', btnClass: 'bg-primary-500 hover:bg-primary-600 text-white' },
  } as const;
  let v = variants[variant as 'danger' | 'warning'] ?? variants.danger;
  let confirm = onConfirm ?? (() => {});
  let cancel = onCancel ?? (() => {});
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fixed inset-0 bg-black/50" onclick={cancel} role="presentation"></div>
    <div class="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
      <div class="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4 {v.iconBg}">
        <span class="text-2xl">⚠️</span>
      </div>
      <h3 class="text-lg font-semibold text-gray-900 text-center mb-2">{title}</h3>
      <p class="text-sm text-gray-500 text-center mb-6">{message}</p>
      <div class="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
        <button class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg
                       hover:bg-gray-50 transition-colors w-full sm:w-auto"
                onclick={cancel}>Cancelar</button>
        <button class="px-4 py-2 text-sm font-medium rounded-lg transition-colors w-full sm:w-auto {v.btnClass}"
                onclick={confirm}>{confirmLabel}</button>
      </div>
    </div>
  </div>
{/if}
