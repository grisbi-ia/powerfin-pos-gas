import { writable, derived } from 'svelte/store';
import { api, setToken, clearToken } from '$lib/api/api';

export interface AdminUser {
  user_id: number;
  username: string;
  name: string;
  role: string;
  permissions: Record<string, string[]>;
}

export const currentUser = writable<AdminUser | null>(null);
export const isAuthenticated = derived(currentUser, ($u) => $u !== null);
export const isAdmin = derived(currentUser, ($u) => $u?.role === 'ADMIN');

// Restore from localStorage
if (typeof window !== 'undefined') {
  const stored = localStorage.getItem('admin_user');
  if (stored) {
    try { currentUser.set(JSON.parse(stored)); } catch { /* ignore */ }
  }
}

export async function login(username: string, password: string): Promise<AdminUser> {
  const data = await api.post<{
    access_token: string;
    user: AdminUser;
  }>('/auth/login', { username, password });

  setToken(data.access_token);
  currentUser.set(data.user);
  if (typeof window !== 'undefined') {
    localStorage.setItem('admin_user', JSON.stringify(data.user));
  }
  return data.user;
}

export function logout() {
  clearToken();
  currentUser.set(null);
}
