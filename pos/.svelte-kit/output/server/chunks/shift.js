import { d as derived, w as writable } from "./index.js";
function createShiftStore() {
  const stored = typeof localStorage !== "undefined" ? localStorage.getItem("shift") : null;
  const initial = stored ? JSON.parse(stored) : null;
  const { subscribe, set, update } = writable(initial);
  return {
    subscribe,
    set(shift2) {
      localStorage.setItem("shift", JSON.stringify(shift2));
      set(shift2);
    },
    clear() {
      localStorage.removeItem("shift");
      set(null);
    }
  };
}
const shift = createShiftStore();
derived(shift, ($s) => $s?.status === "OPEN");
export {
  shift as s
};
