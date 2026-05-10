import { c as create_ssr_component, a as subscribe, v as validate_component, e as escape } from "../../../../chunks/ssr.js";
import "@sveltejs/kit/internal";
import "../../../../chunks/exports.js";
import "../../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../../chunks/state.svelte.js";
import { H as Header } from "../../../../chunks/Header.js";
import { s as shift } from "../../../../chunks/shift.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $shift, $$unsubscribe_shift;
  $$unsubscribe_shift = subscribe(shift, (value) => $shift = value);
  $$unsubscribe_shift();
  return `${validate_component(Header, "Header").$$render($$result, { title: "Historial", showBack: true }, {}, {})} <main class="flex-1 px-4 py-6"><div class="card p-6 text-center"><h2 class="text-lg font-semibold text-gray-800 mb-2" data-svelte-h="svelte-opcb8a">Historial del Turno</h2> ${$shift ? `<p class="text-sm text-gray-500 mb-4">Turno #${escape($shift.shift_id)} — ${escape($shift.status === "OPEN" ? "Abierto" : "Cerrado")}</p>` : ``} <div class="bg-gray-50 rounded-xl p-4 mb-4" data-svelte-h="svelte-hj9dye"><p class="text-xs text-gray-400">Historial de despachos disponible en Fase 6</p></div> <button class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm" data-svelte-h="svelte-wc3lhe">Volver al inicio</button></div></main>`;
});
export {
  Page as default
};
