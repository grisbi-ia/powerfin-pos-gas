/**
 * Mock toggles for development without backends.
 *
 * VITE_USE_MOCKS_POWERFIN=true   → mock login, config, customers, shifts
 * VITE_USE_MOCKS_BRIDGE=true     → mock dispenser states (no FusionBridge)
 *
 * Legacy: VITE_USE_MOCKS=true forces both on.
 */
const forced = import.meta.env.VITE_USE_MOCKS === 'true';

export const USE_MOCKS_POWERFIN = forced || import.meta.env.VITE_USE_MOCKS_POWERFIN !== 'false';
export const USE_MOCKS_BRIDGE   = forced || import.meta.env.VITE_USE_MOCKS_BRIDGE === 'true';
