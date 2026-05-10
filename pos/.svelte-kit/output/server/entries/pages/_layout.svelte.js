import { c as create_ssr_component, a as subscribe } from "../../chunks/ssr.js";
import { a as auth } from "../../chunks/auth.js";
import "../../chunks/shift.js";
import { c as configStore } from "../../chunks/config.js";
import { p as page } from "../../chunks/stores.js";
import "@sveltejs/kit/internal";
import "../../chunks/exports.js";
import "../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/state.svelte.js";
const Layout = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $$unsubscribe_auth;
  let $$unsubscribe_configStore;
  let $$unsubscribe_page;
  $$unsubscribe_auth = subscribe(auth, (value) => value);
  $$unsubscribe_configStore = subscribe(configStore, (value) => value);
  $$unsubscribe_page = subscribe(page, (value) => value);
  $$unsubscribe_auth();
  $$unsubscribe_configStore();
  $$unsubscribe_page();
  return `${slots.default ? slots.default({}) : ``}`;
});
export {
  Layout as default
};
