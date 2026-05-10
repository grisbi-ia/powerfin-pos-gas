import { c as create_ssr_component, a as subscribe, e as escape, d as each, b as add_attribute } from "../../../../chunks/ssr.js";
import { a as auth } from "../../../../chunks/auth.js";
import "../../../../chunks/shift.js";
import { b as config } from "../../../../chunks/config.js";
import "@sveltejs/kit/internal";
import "../../../../chunks/exports.js";
import "../../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../../chunks/state.svelte.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $auth, $$unsubscribe_auth;
  let $config, $$unsubscribe_config;
  $$unsubscribe_auth = subscribe(auth, (value) => $auth = value);
  $$unsubscribe_config = subscribe(config, (value) => $config = value);
  let selectedDispensers = [];
  let openingCash = 0;
  const dispenserConfigs = $config?.dispensers ?? [];
  $$unsubscribe_auth();
  $$unsubscribe_config();
  return `<div class="min-h-screen flex flex-col items-center justify-center px-6 py-10"><div class="w-full max-w-md"><div class="text-center mb-8"><h2 class="text-2xl font-bold text-gray-800" data-svelte-h="svelte-1tamj4o">Abrir Turno</h2> <p class="text-gray-500 mt-1">${escape($auth.user?.name ?? "Usuario")} — ${escape((/* @__PURE__ */ new Date()).toLocaleDateString("es-EC", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric"
  }))}</p></div>  <div class="card p-6 mb-4"><h3 class="text-sm font-semibold text-gray-700 mb-3" data-svelte-h="svelte-tmxyoc">Selecciona tu isla:</h3> <div class="grid grid-cols-2 gap-3">${each(dispenserConfigs, (d) => {
    return `<button class="${"touch-btn p-4 rounded-xl border-2 text-left transition-colors " + escape(
      selectedDispensers.includes(d.dispenser_id) ? "border-primary bg-primary/5 text-primary" : "border-gray-200 text-gray-600 hover:border-gray-300",
      true
    )}"><div class="text-sm font-semibold">${escape(d.name)}</div> <div class="text-xs text-gray-400 mt-1">${escape(d.hoses.length)} pistolas — ${escape(d.hoses[0]?.grade_name)}</div> </button>`;
  })}</div></div>  <div class="card p-6 mb-4"><label for="cash" class="block text-sm font-semibold text-gray-700 mb-2" data-svelte-h="svelte-14phxt4">Efectivo inicial:</label> <input id="cash" type="number" step="0.01" min="0" class="w-full rounded-xl border border-gray-200 px-4 py-3 text-lg focus:border-primary focus:outline-none" placeholder="0.00"${add_attribute("value", openingCash, 0)}></div> ${``} <button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed" ${""}>${escape("Abrir Turno")}</button></div></div>`;
});
export {
  Page as default
};
