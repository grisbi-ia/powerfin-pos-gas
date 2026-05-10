import { c as create_ssr_component, a as subscribe, o as onDestroy, v as validate_component, e as escape } from "../../../../chunks/ssr.js";
import "@sveltejs/kit/internal";
import "../../../../chunks/exports.js";
import "../../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../../chunks/state.svelte.js";
import { p as page } from "../../../../chunks/stores.js";
import { H as Header } from "../../../../chunks/Header.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let progressPct;
  let remaining;
  let estimatedVolume;
  let $$unsubscribe_page;
  $$unsubscribe_page = subscribe(page, (value) => value);
  let dispenserId = 0;
  let presetAmount = 0;
  let paymentMethod = "";
  let currentAmount = 0;
  onDestroy(() => {
  });
  progressPct = 0;
  remaining = 0;
  estimatedVolume = "0.00";
  $$unsubscribe_page();
  return `${validate_component(Header, "Header").$$render($$result, { title: "Despachando", showBack: false }, {}, {})} <main class="flex-1 flex flex-col items-center justify-center px-6 py-8"><div class="w-full max-w-sm"> <div class="text-center mb-8"><div class="${"w-24 h-24 mx-auto mb-4 rounded-full border-4 " + escape(
    "border-purple-500",
    true
  ) + " flex items-center justify-center"}">${`<svg class="w-12 h-12 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>`}</div> <h2 class="text-lg font-semibold text-gray-700">${escape(
    "Surtidor autorizado"
  )}</h2> <p class="text-sm text-gray-500 mt-1">Surtidor ${escape(dispenserId)}</p></div>  <div class="mb-6"><div class="flex justify-between text-sm text-gray-500 mb-1"><span>$${escape(currentAmount.toFixed(2))}</span> <span>$${escape(presetAmount.toFixed(2))}</span></div> <div class="w-full h-4 bg-gray-200 rounded-full overflow-hidden"><div class="${"h-full rounded-full transition-all duration-500 " + escape(
    "bg-purple-500",
    true
  )}" style="${"width: " + escape(progressPct, true) + "%"}"></div></div></div>  <div class="card p-4 space-y-3"><div class="flex justify-between"><span class="text-sm text-gray-500" data-svelte-h="svelte-g8j3jo">Volumen</span> <span class="text-sm font-semibold">${escape(estimatedVolume)} L</span></div> <div class="flex justify-between"><span class="text-sm text-gray-500" data-svelte-h="svelte-1msyvrl">Monto</span> <span class="text-sm font-semibold">$${escape(currentAmount.toFixed(2))}</span></div> <div class="flex justify-between"><span class="text-sm text-gray-500" data-svelte-h="svelte-147i0mu">Restante</span> <span class="text-sm font-semibold">$${escape(remaining.toFixed(2))}</span></div> <div class="flex justify-between"><span class="text-sm text-gray-500" data-svelte-h="svelte-vccd2l">Pago</span> <span class="text-sm font-semibold">${escape(paymentMethod)}</span></div></div>  <div class="text-center mt-6"><p class="text-xs text-gray-400">${escape(
    "Levante la pistola para iniciar el despacho"
  )}</p></div></div></main>`;
});
export {
  Page as default
};
