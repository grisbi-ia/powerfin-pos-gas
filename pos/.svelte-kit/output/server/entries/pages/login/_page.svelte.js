import { c as create_ssr_component, d as each, e as escape, b as add_attribute, v as validate_component } from "../../../chunks/ssr.js";
import { a as auth } from "../../../chunks/auth.js";
import { g as goto } from "../../../chunks/client.js";
import { l as login } from "../../../chunks/powerfin.mock.js";
const PinKeyboard = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let { onDigit } = $$props;
  let { onDelete } = $$props;
  let { onEnter } = $$props;
  let { loading = false } = $$props;
  const digits = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["", "0", "⌫"]];
  if ($$props.onDigit === void 0 && $$bindings.onDigit && onDigit !== void 0) $$bindings.onDigit(onDigit);
  if ($$props.onDelete === void 0 && $$bindings.onDelete && onDelete !== void 0) $$bindings.onDelete(onDelete);
  if ($$props.onEnter === void 0 && $$bindings.onEnter && onEnter !== void 0) $$bindings.onEnter(onEnter);
  if ($$props.loading === void 0 && $$bindings.loading && loading !== void 0) $$bindings.loading(loading);
  return `<div class="grid grid-cols-3 gap-3">${each(digits, (row) => {
    return `${each(row, (digit) => {
      return `${digit === "" ? `<div></div>` : `<button class="${"touch-btn bg-white/10 hover:bg-white/20 text-white rounded-2xl py-4 text-2xl font-semibold border border-white/15 " + escape(loading ? "opacity-50" : "", true)}" ${loading ? "disabled" : ""}>${escape(digit)} </button>`}`;
    })}`;
  })}</div> <div class="mt-4"><button class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-2xl py-4 text-lg font-bold disabled:opacity-50" ${loading ? "disabled" : ""}>${escape(loading ? "Ingresando..." : "Ingresar")}</button></div>`;
});
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let username = "carlos";
  let pin = "";
  let error = "";
  let loading = false;
  async function handleLogin() {
    if (pin.length < 3) {
      error = "Ingrese un PIN válido";
      return;
    }
    loading = true;
    error = "";
    try {
      const response = await login({ username, pin });
      auth.login(response.access_token, response.user);
      goto("/");
    } catch {
      error = "Credenciales inválidas";
      pin = "";
    } finally {
      loading = false;
    }
  }
  function handlePinDigit(digit) {
    if (pin.length < 4) pin += digit;
  }
  function handlePinDelete() {
    pin = pin.slice(0, -1);
  }
  return `<div class="min-h-screen flex flex-col items-center justify-center bg-primary px-6"><div class="w-full max-w-sm"> <div class="text-center mb-10" data-svelte-h="svelte-usljks"><h1 class="text-3xl font-bold text-white">Powerfin POS</h1> <p class="text-blue-200 mt-1 text-sm">Gasolinera NEOPAUTE</p></div>  <div class="mb-6"><label for="username" class="block text-blue-200 text-xs font-medium mb-1" data-svelte-h="svelte-dcohby">Usuario</label> <input id="username" type="text" class="w-full bg-white/10 text-white placeholder-blue-300 rounded-xl px-4 py-3 border border-white/20 focus:border-white/40 focus:outline-none text-lg" placeholder="Nombre de usuario"${add_attribute("value", username, 0)}></div>  <div class="mb-6 text-center"><span class="block text-blue-200 text-xs font-medium mb-2" data-svelte-h="svelte-1nliqne">PIN</span> <div class="flex justify-center gap-3">${each([0, 1, 2, 3], (i) => {
    return `<div class="${"w-5 h-5 rounded-full border-2 transition-colors " + escape(
      i < pin.length ? "bg-white border-white" : "border-white/30",
      true
    )}"></div>`;
  })}</div></div>  ${error ? `<div class="bg-red-500/20 text-red-200 text-sm text-center rounded-lg py-2 mb-4">${escape(error)}</div>` : ``}  ${validate_component(PinKeyboard, "PinKeyboard").$$render(
    $$result,
    {
      onDigit: handlePinDigit,
      onDelete: handlePinDelete,
      onEnter: handleLogin,
      loading
    },
    {},
    {}
  )} <div class="text-center mt-6" data-svelte-h="svelte-1jrnvgc"><p class="text-blue-300 text-xs">PIN demo: <span class="font-mono text-white">1234</span></p></div></div></div>`;
});
export {
  Page as default
};
