import { c as create_ssr_component, a as subscribe, v as validate_component, e as escape } from "../../../../chunks/ssr.js";
import { g as goto } from "../../../../chunks/client.js";
import { p as page } from "../../../../chunks/stores.js";
import { H as Header } from "../../../../chunks/Header.js";
function delay(ms = 200) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
async function printReceipt(_data) {
  await delay(300);
  return { status: "PRINTED" };
}
const PrintPrompt = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let { policy = "ASK" } = $$props;
  let { onPrint } = $$props;
  let { onSkip } = $$props;
  if ($$props.policy === void 0 && $$bindings.policy && policy !== void 0) $$bindings.policy(policy);
  if ($$props.onPrint === void 0 && $$bindings.onPrint && onPrint !== void 0) $$bindings.onPrint(onPrint);
  if ($$props.onSkip === void 0 && $$bindings.onSkip && onSkip !== void 0) $$bindings.onSkip(onSkip);
  return `${policy === "ALWAYS" ? `<div class="bg-blue-50 rounded-xl px-4 py-3 text-center" data-svelte-h="svelte-a6a84d"><div class="flex items-center justify-center gap-2 mb-2"><svg class="w-5 h-5 text-blue-500 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg> <span class="text-blue-700 text-sm font-medium">Imprimiendo ticket...</span></div></div>` : `${policy === "ASK" ? `<div class="flex gap-3"><button class="touch-btn flex-1 bg-white border-2 border-gray-200 rounded-xl py-3 text-sm font-medium text-gray-600" data-svelte-h="svelte-1hivp7p">No, gracias</button> <button class="touch-btn flex-1 bg-primary text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2" data-svelte-h="svelte-6zx32p"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
			Imprimir ticket</button></div>` : ``}`}`;
});
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let change;
  let $$unsubscribe_page;
  $$unsubscribe_page = subscribe(page, (value) => value);
  let orderId = "";
  let dispenserId = 0;
  let finalAmount = 0;
  let finalVolume = "";
  let presetAmount = 0;
  let paymentMethod = "";
  let unitPrice = 0;
  let printPolicy = "ASK";
  let printing = false;
  async function handlePrint() {
    printing = true;
    try {
      await printReceipt({
        type: "FUEL_RECEIPT",
        dispenserId,
        fuelData: {
          dispenserId,
          orderId,
          volume: finalVolume,
          amount: finalAmount.toFixed(2),
          unitPrice: unitPrice.toFixed(3),
          paymentMethod,
          grade: "SUPER"
        }
      });
    } finally {
      printing = false;
    }
  }
  function handleNewSale() {
    goto();
  }
  change = 0;
  $$unsubscribe_page();
  return `${validate_component(Header, "Header").$$render(
    $$result,
    {
      title: "Venta Completada",
      showBack: false
    },
    {},
    {}
  )} <main class="flex-1 px-4 py-6 overflow-y-auto"><div class="w-full max-w-sm mx-auto"> <div class="text-center mb-6"><div class="w-20 h-20 mx-auto mb-3 rounded-full bg-green-100 flex items-center justify-center" data-svelte-h="svelte-lqel03"><svg class="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></div> <h2 class="text-xl font-bold text-gray-800" data-svelte-h="svelte-14aiwcu">Venta Completada</h2> <p class="text-sm text-gray-500 mt-1">#${escape(orderId)}</p></div>  <div class="card p-4 mb-4"><h3 class="text-sm font-semibold text-gray-700 mb-3" data-svelte-h="svelte-lu5hlz">Resumen del despacho</h3> <div class="space-y-2"><div class="flex justify-between text-sm"><span class="text-gray-500" data-svelte-h="svelte-sumr7k">Surtidor</span> <span class="font-medium">${escape(dispenserId)}</span></div> <div class="flex justify-between text-sm"><span class="text-gray-500" data-svelte-h="svelte-1j51jn6">Volumen</span> <span class="font-medium">${escape(finalVolume)} L</span></div> <div class="flex justify-between text-sm"><span class="text-gray-500" data-svelte-h="svelte-ez7yqv">Precio unitario</span> <span class="font-medium">$${escape(unitPrice.toFixed(3))}</span></div> <div class="flex justify-between text-sm"><span class="text-gray-500" data-svelte-h="svelte-1l445sl">Forma de pago</span> <span class="font-medium">${escape(paymentMethod)}</span></div> <hr class="border-gray-100"> <div class="flex justify-between text-lg font-bold"><span class="text-gray-700" data-svelte-h="svelte-cpraay">Total</span> <span class="text-primary">$${escape(finalAmount.toFixed(2))}</span></div></div></div>  ${change > 0 ? `<div class="card p-4 mb-4 bg-green-50 border-green-200"><div class="flex justify-between items-center"><span class="text-sm font-medium text-green-700" data-svelte-h="svelte-uxvo88">Vuelto</span> <span class="text-xl font-bold text-green-700">$${escape(change.toFixed(2))}</span></div> <div class="text-xs text-green-600 mt-1">Preset: $${escape(presetAmount.toFixed(2))} — Despachado: $${escape(finalAmount.toFixed(2))}</div></div>` : ``}  ${!printing ? `<div class="mb-4">${validate_component(PrintPrompt, "PrintPrompt").$$render(
    $$result,
    {
      policy: printPolicy,
      onPrint: handlePrint,
      onSkip: handleNewSale
    },
    {},
    {}
  )}</div>` : `<div class="mb-4 text-center text-sm text-blue-600 animate-pulse" data-svelte-h="svelte-yohony">Imprimiendo ticket...</div>`}  <button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" data-svelte-h="svelte-1jdwhm">Nueva Venta</button></div></main>`;
});
export {
  Page as default
};
