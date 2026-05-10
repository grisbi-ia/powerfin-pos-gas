import { d as derived, w as writable } from "./index.js";
function createConfigStore() {
  const { subscribe, set } = writable({
    config: null,
    loaded: false
  });
  return {
    subscribe,
    setConfig(config2) {
      set({ config: config2, loaded: true });
    }
  };
}
const configStore = createConfigStore();
const config = derived(configStore, ($c) => $c.config);
const configLoaded = derived(configStore, ($c) => $c.loaded);
export {
  configLoaded as a,
  config as b,
  configStore as c
};
