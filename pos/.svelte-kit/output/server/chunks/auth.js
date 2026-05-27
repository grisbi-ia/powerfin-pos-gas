import { d as derived, w as writable } from "./index.js";
function createAuthStore() {
  const stored = typeof localStorage !== "undefined" ? localStorage.getItem("auth") : null;
  const initialState = stored ? JSON.parse(stored) : { token: null, user: null };
  const { subscribe, set, update } = writable(initialState);
  return {
    subscribe,
    login(token, user) {
      const state = { token, user };
      localStorage.setItem("auth", JSON.stringify(state));
      set(state);
    },
    logout() {
      localStorage.removeItem("auth");
      set({ token: null, user: null });
    },
    getToken() {
      let current = { token: null };
      subscribe((s) => current = s)();
      return current.token;
    }
  };
}
const auth = createAuthStore();
derived(auth, ($auth) => $auth.token !== null);
const currentUser = derived(auth, ($auth) => $auth.user);
export {
  auth as a,
  currentUser as c
};
