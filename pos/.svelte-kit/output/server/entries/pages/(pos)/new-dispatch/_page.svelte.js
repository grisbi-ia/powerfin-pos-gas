import { c as create_ssr_component, b as add_attribute, d as each, e as escape, a as subscribe, v as validate_component } from "../../../../chunks/ssr.js";
import { g as goto } from "../../../../chunks/client.js";
import { p as page } from "../../../../chunks/stores.js";
import { H as Header } from "../../../../chunks/Header.js";
import { g as getCustomerPrice } from "../../../../chunks/powerfin.mock.js";
const CustomerSearch = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let { onSelect } = $$props;
  let { disabled = false } = $$props;
  let query = "";
  if ($$props.onSelect === void 0 && $$bindings.onSelect && onSelect !== void 0) $$bindings.onSelect(onSelect);
  if ($$props.disabled === void 0 && $$bindings.disabled && disabled !== void 0) $$bindings.disabled(disabled);
  return `<div class="relative"><label for="customer-search" class="block text-sm font-semibold text-gray-700 mb-1" data-svelte-h="svelte-u4qw25">Cliente</label> <div class="relative"><input id="customer-search" type="text" placeholder="Buscar placa, cédula o nombre..." class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:border-primary focus:outline-none pr-10" ${disabled ? "disabled" : ""}${add_attribute("value", query, 0)}> ${`${``}`}</div>  ${``} ${``}  ${``}</div>`;
});
const AmountInput = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let { onAmount } = $$props;
  let { disabled = false } = $$props;
  const quickAmounts = ["5", "10", "20", "50", "100"];
  let customAmount = "";
  let mode = "quick";
  if ($$props.onAmount === void 0 && $$bindings.onAmount && onAmount !== void 0) $$bindings.onAmount(onAmount);
  if ($$props.disabled === void 0 && $$bindings.disabled && disabled !== void 0) $$bindings.disabled(disabled);
  return `<div><label class="block text-sm font-semibold text-gray-700 mb-2" data-svelte-h="svelte-60cigt">Monto ($)</label>  <div class="grid grid-cols-5 gap-2 mb-3">${each(quickAmounts, (amount) => {
    return `<button class="${"touch-btn py-3 rounded-xl border-2 text-sm font-semibold transition-colors " + escape(
      customAmount === amount && mode === "quick" ? "border-primary bg-primary/5 text-primary" : "border-gray-200 text-gray-600 hover:border-gray-300",
      true
    )}" ${disabled ? "disabled" : ""}>$${escape(amount)} </button>`;
  })}</div>  <div class="relative"><span class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-lg" data-svelte-h="svelte-1gywh0x">$</span> <input type="number" step="0.01" min="0" placeholder="Otro monto" class="w-full rounded-xl border border-gray-200 pl-8 pr-4 py-3 text-lg focus:border-primary focus:outline-none" ${disabled ? "disabled" : ""}${add_attribute("value", customAmount, 0)}></div></div>`;
});
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $page, $$unsubscribe_page;
  $$unsubscribe_page = subscribe(page, (value) => $page = value);
  let dispenserId = 0;
  let selectedCustomer = null;
  let amount = "";
  let paymentMethod = "EFECTIVO";
  let loading = false;
  let unitPrice = 1.5;
  const paymentMethods = ["EFECTIVO", "TARJETA", "QR", "CREDITO"];
  async function handleCustomerSelect(customer) {
    selectedCustomer = customer;
    if (customer) {
      try {
        const price = await getCustomerPrice("mock-token", customer.customer_id, "SUPER");
        unitPrice = price.unit_price;
      } catch {
        unitPrice = 1.5;
      }
    } else {
      unitPrice = 1.5;
    }
  }
  dispenserId = Number($page.url.searchParams.get("dispenser") ?? "0");
  $$unsubscribe_page();
  return `${validate_component(Header, "Header").$$render(
    $$result,
    {
      title: "Nueva Venta",
      showBack: true,
      onBack: () => goto()
    },
    {},
    {}
  )} <main class="flex-1 px-4 py-4 overflow-y-auto"> <div class="card p-4 mb-4"><div class="flex items-center justify-between"><div><div class="text-xs text-gray-400" data-svelte-h="svelte-1pumv9q">Surtidor</div> <div class="text-lg font-bold text-gray-800">${escape(dispenserId)}</div></div> <div class="text-right"><div class="text-xs text-gray-400" data-svelte-h="svelte-1socfe2">Precio actual</div> <div class="text-lg font-bold text-primary">$${escape(unitPrice.toFixed(3))}/L</div></div></div></div>  <div class="card p-4 mb-4">${validate_component(CustomerSearch, "CustomerSearch").$$render(
    $$result,
    {
      onSelect: handleCustomerSelect,
      disabled: loading
    },
    {},
    {}
  )}</div>  <div class="card p-4 mb-4">${validate_component(AmountInput, "AmountInput").$$render(
    $$result,
    {
      onAmount: (a) => amount = a,
      disabled: loading
    },
    {},
    {}
  )}</div>  <div class="card p-4 mb-4"><label class="block text-sm font-semibold text-gray-700 mb-2" data-svelte-h="svelte-3ic2ic">Forma de pago</label> <div class="grid grid-cols-2 gap-2">${each(paymentMethods, (method) => {
    return `<button class="${"touch-btn py-3 rounded-xl border-2 text-sm font-medium transition-colors " + escape(
      paymentMethod === method ? "border-primary bg-primary/5 text-primary" : "border-gray-200 text-gray-600 hover:border-gray-300",
      true
    )}" ${""}>${escape(method)} </button>`;
  })}</div></div>  ${amount ? `<div class="card p-4 mb-4 bg-primary/5 border-primary/20"><div class="flex justify-between text-sm"><span class="text-gray-600" data-svelte-h="svelte-gpx74f">Litros estimados:</span> <span class="font-semibold">${escape((parseFloat(amount) / unitPrice).toFixed(2))} L</span></div> <div class="flex justify-between text-sm mt-1"><span class="text-gray-600" data-svelte-h="svelte-1kz55ok">Precio unitario:</span> <span class="font-semibold">$${escape(unitPrice.toFixed(3))}</span></div> ${selectedCustomer ? `<div class="flex justify-between text-sm mt-1"><span class="text-gray-600" data-svelte-h="svelte-1cco3hk">Lista:</span> <span class="font-semibold text-purple-600">${escape(selectedCustomer.price_list_name)}</span></div>` : ``}</div>` : ``} ${``}  <button class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4 text-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed" ${!amount ? "disabled" : ""}>${escape("Autorizar Despacho")}</button></main>`;
});
export {
  Page as default
};
