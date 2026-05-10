import { c as create_ssr_component, a as subscribe, v as validate_component, e as escape, b as add_attribute } from "../../../../chunks/ssr.js";
import "@sveltejs/kit/internal";
import "../../../../chunks/exports.js";
import "../../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../../chunks/state.svelte.js";
import { H as Header } from "../../../../chunks/Header.js";
import { a as auth } from "../../../../chunks/auth.js";
import { s as shift } from "../../../../chunks/shift.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $shift, $$unsubscribe_shift;
  let $$unsubscribe_auth;
  $$unsubscribe_shift = subscribe(shift, (value) => $shift = value);
  $$unsubscribe_auth = subscribe(auth, (value) => value);
  let closingCash = 0;
  $$unsubscribe_shift();
  $$unsubscribe_auth();
  return `${validate_component(Header, "Header").$$render($$result, { title: "Cerrar Turno", showBack: true }, {}, {})} <main class="flex-1 px-4 py-6">${$shift ? `<div class="card p-6 mb-4"><h2 class="text-lg font-semibold text-gray-800 mb-3">Cerrar Turno #${escape($shift.shift_id)}</h2> <div class="text-sm text-gray-500 space-y-1 mb-4"><p>Inicio: ${escape(new Date($shift.opened_at).toLocaleString("es-EC"))}</p> <p>Apertura: ${escape((/* @__PURE__ */ new Date()).toLocaleDateString("es-EC"))}</p></div> <label for="closing-cash" class="block text-sm font-semibold text-gray-700 mb-2" data-svelte-h="svelte-idn0td">Efectivo final:</label> <input id="closing-cash" type="number" step="0.01" min="0" class="w-full rounded-xl border border-gray-200 px-4 py-3 text-lg focus:border-primary focus:outline-none mb-4" placeholder="0.00"${add_attribute("value", closingCash, 0)}> ${``} <button class="touch-btn w-full bg-danger text-white rounded-xl py-4 text-lg font-semibold disabled:opacity-50" ${""}>${escape("Cerrar Turno")}</button></div>` : ``}</main>`;
});
export {
  Page as default
};
