import { c as create_ssr_component, a as subscribe, o as onDestroy, v as validate_component } from "../../../chunks/ssr.js";
import { a as auth } from "../../../chunks/auth.js";
import { s as shift } from "../../../chunks/shift.js";
import { a as configLoaded } from "../../../chunks/config.js";
import { f as fusionConnected, d as dispenserList, H as Header } from "../../../chunks/Header.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
const OfflineBanner = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $fusionConnected, $$unsubscribe_fusionConnected;
  $$unsubscribe_fusionConnected = subscribe(fusionConnected, (value) => $fusionConnected = value);
  $$unsubscribe_fusionConnected();
  return `${!$fusionConnected ? `<div class="bg-warning/10 border-b border-warning/30 px-4 py-2 text-center" data-svelte-h="svelte-11uokhr"><div class="flex items-center justify-center gap-2"><svg class="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"></path></svg> <span class="text-warning text-xs font-medium">Sin conexión con FusionBridge — reconectando...</span></div></div>` : ``}`;
});
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $$unsubscribe_shift;
  let $$unsubscribe_auth;
  let $$unsubscribe_configLoaded;
  let $$unsubscribe_dispenserList;
  $$unsubscribe_shift = subscribe(shift, (value) => value);
  $$unsubscribe_auth = subscribe(auth, (value) => value);
  $$unsubscribe_configLoaded = subscribe(configLoaded, (value) => value);
  $$unsubscribe_dispenserList = subscribe(dispenserList, (value) => value);
  onDestroy(() => {
  });
  $$unsubscribe_shift();
  $$unsubscribe_auth();
  $$unsubscribe_configLoaded();
  $$unsubscribe_dispenserList();
  return `${validate_component(Header, "Header").$$render($$result, { title: "Powerfin POS" }, {}, {})} ${validate_component(OfflineBanner, "OfflineBanner").$$render($$result, {}, {}, {})} <main class="flex-1 px-4 py-4 pb-24">${`<div class="flex items-center justify-center py-20" data-svelte-h="svelte-1ak6qz2"><div class="text-center"><div class="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div> <p class="text-gray-400 mt-4 text-sm">Conectando...</p></div></div>`}</main>  <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3"><div class="flex justify-around"><button class="touch-btn flex flex-col items-center gap-1 text-primary" data-svelte-h="svelte-169kcd"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg> <span class="text-xs">Inicio</span></button> <button class="touch-btn flex flex-col items-center gap-1 text-gray-400" data-svelte-h="svelte-9ktqll"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> <span class="text-xs">Historial</span></button> <button class="touch-btn flex flex-col items-center gap-1 text-gray-400" data-svelte-h="svelte-qceoh"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg> <span class="text-xs">Cerrar turno</span></button></div></nav>`;
});
export {
  Page as default
};
