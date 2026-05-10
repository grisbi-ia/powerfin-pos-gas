import { c as create_ssr_component, a as subscribe, e as escape } from "./ssr.js";
import { c as currentUser } from "./auth.js";
import { s as shift } from "./shift.js";
import { d as derived, w as writable } from "./index.js";
import "@sveltejs/kit/internal";
import "./exports.js";
import "./utils.js";
import "@sveltejs/kit/internal/server";
import "./state.svelte.js";
function createDispensersStore() {
  const { subscribe: subscribe2, update, set } = writable({
    dispensers: /* @__PURE__ */ new Map(),
    fusionConnected: false
  });
  return {
    subscribe: subscribe2,
    updateDispenser(d) {
      update((state) => {
        const existing = state.dispensers.get(d.dispenserId) ?? {
          dispenserId: d.dispenserId,
          status: "UNKNOWN",
          subStatus: "",
          presetAmount: 0,
          hoseCount: 0,
          connected: false,
          online: false
        };
        state.dispensers.set(d.dispenserId, { ...existing, ...d });
        return { ...state, dispensers: new Map(state.dispensers) };
      });
    },
    setFusionConnected(connected) {
      update((state) => ({ ...state, fusionConnected: connected }));
    },
    reset() {
      set({ dispensers: /* @__PURE__ */ new Map(), fusionConnected: false });
    }
  };
}
const dispensers = createDispensersStore();
const dispenserList = derived(dispensers, ($d) => Array.from($d.dispensers.values()));
const fusionConnected = derived(dispensers, ($d) => $d.fusionConnected);
const Header = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $currentUser, $$unsubscribe_currentUser;
  let $shift, $$unsubscribe_shift;
  let $fusionConnected, $$unsubscribe_fusionConnected;
  $$unsubscribe_currentUser = subscribe(currentUser, (value) => $currentUser = value);
  $$unsubscribe_shift = subscribe(shift, (value) => $shift = value);
  $$unsubscribe_fusionConnected = subscribe(fusionConnected, (value) => $fusionConnected = value);
  let { title = "Powerfin POS" } = $$props;
  let { showBack = false } = $$props;
  let { onBack = null } = $$props;
  if ($$props.title === void 0 && $$bindings.title && title !== void 0) $$bindings.title(title);
  if ($$props.showBack === void 0 && $$bindings.showBack && showBack !== void 0) $$bindings.showBack(showBack);
  if ($$props.onBack === void 0 && $$bindings.onBack && onBack !== void 0) $$bindings.onBack(onBack);
  $$unsubscribe_currentUser();
  $$unsubscribe_shift();
  $$unsubscribe_fusionConnected();
  return `<header class="bg-primary text-white px-4 py-3"><div class="flex items-center justify-between"><div class="flex items-center gap-3">${showBack ? `<button class="touch-btn p-1 -ml-1" data-svelte-h="svelte-3pk3j7"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg></button>` : ``} <div><h1 class="text-lg font-bold">${escape(title)}</h1> <p class="text-xs text-blue-200">${escape($currentUser?.name ?? "")} ${$shift ? `— Turno #${escape($shift.shift_id)}` : ``}</p></div></div> <div class="flex items-center gap-2"> <div class="flex items-center gap-1"><div class="${"w-2 h-2 rounded-full " + escape($fusionConnected ? "bg-green-400" : "bg-red-400", true)}"></div> <span class="text-xs text-blue-200">${escape($fusionConnected ? "Online" : "Offline")}</span></div> <button class="touch-btn text-blue-200 hover:text-white text-xs underline" data-svelte-h="svelte-16dxvjl">Salir</button></div></div></header>`;
});
export {
  Header as H,
  dispenserList as d,
  fusionConnected as f
};
