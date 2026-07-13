import * as mock from './powerfin.mock';
import { USE_MOCKS_POWERFIN } from './env';
import type {
	User, LoginRequest, LoginResponse, AppConfig, Customer,
	PriceInfo, Shift, OpenShiftRequest, CloseShiftResponse,
	CreateDispatchRequest, CreateDispatchResponse, SaleCompletedData
} from './types';

// Dev: Vite proxies /api/pos/* → localhost:8080
// Prod: Nginx routes to PowerFin ERP at root (same domain, no CORS)
function powerfinUrl(path: string): string {
	return path;
}

// ── Auth ─────────────────────────────────────────────────────

export async function login(data: LoginRequest): Promise<LoginResponse> {
	if (USE_MOCKS_POWERFIN) return mock.login(data);
	const res = await fetch(powerfinUrl('/api/pos/auth/login'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Credenciales inválidas');
	return res.json();
}

// ── Config ───────────────────────────────────────────────────

export async function fetchConfig(token: string): Promise<AppConfig> {
	if (USE_MOCKS_POWERFIN) return mock.fetchConfig(token);
	const res = await fetch(powerfinUrl('/api/pos/config'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error al cargar configuración');
	return res.json();
}

// ── Customers ────────────────────────────────────────────────

export async function searchCustomers(token: string, query: string): Promise<Customer[]> {
	if (USE_MOCKS_POWERFIN) return mock.searchCustomers(token, query);
	const res = await fetch(powerfinUrl(`/api/pos/customers?q=${encodeURIComponent(query)}`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (res.status === 404) return [];
	if (!res.ok) throw new Error('Error buscando clientes');
	return res.json();
}

export async function getCustomerPrice(
	token: string, customerId: string, gradeId: string,
	vehicleId?: string
): Promise<PriceInfo> {
	if (USE_MOCKS_POWERFIN) return mock.getCustomerPrice(token, customerId, gradeId);
	let url = powerfinUrl(`/api/pos/prices?customerId=${customerId}&gradeId=${gradeId}`);
	if (vehicleId) url += `&vehicleId=${encodeURIComponent(vehicleId)}`;
	const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
	if (!res.ok) throw new Error('Error obteniendo precio');
	return res.json();
}

// ── Shifts ───────────────────────────────────────────────────

export async function openShift(token: string, data: OpenShiftRequest): Promise<Shift> {
	if (USE_MOCKS_POWERFIN) return mock.openShift(token, data);
	const res = await fetch(powerfinUrl('/api/pos/shifts/open'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error abriendo turno');
	return res.json();
}

export async function getCurrentShift(token: string): Promise<Shift | null> {
	if (USE_MOCKS_POWERFIN) return mock.getCurrentShift(token);
	const res = await fetch(powerfinUrl('/api/pos/shifts/current'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (res.status === 404) return null;
	if (!res.ok) throw new Error('Error consultando turno');
	return res.json();
}

export async function closeShift(
	token: string, shiftId: number, data: { notes: string }
): Promise<CloseShiftResponse> {
	if (USE_MOCKS_POWERFIN) return mock.closeShift(token, shiftId, data);
	const res = await fetch(powerfinUrl(`/api/pos/shifts/${shiftId}/close`), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error cerrando turno');
	return res.json();
}

// ── Dispatches ───────────────────────────────────────────────

export async function createDispatch(
	token: string, data: CreateDispatchRequest
): Promise<CreateDispatchResponse> {
	if (USE_MOCKS_POWERFIN) return mock.createDispatch(token, data);
	const res = await fetch(powerfinUrl('/api/pos/dispatches'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) {
		let detail = 'Error creando despacho';
		try {
			const body = await res.json();
			detail = body.detail || detail;
		} catch { /* use default */ }
		const err = new Error(detail);
		(err as any).status = res.status;
		throw err;
	}
	return res.json();
}

export async function completeDispatch(
	token: string, orderId: string, saleData: SaleCompletedData
): Promise<void> {
	if (USE_MOCKS_POWERFIN) return mock.completeDispatch(token, orderId, saleData);
	const res = await fetch(powerfinUrl(`/api/pos/dispatches/${orderId}/complete`), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(saleData)
	});
	if (!res.ok) throw new Error('Error completando despacho');
}

export async function cancelDispatch(
	token: string, orderId: string
): Promise<void> {
	if (USE_MOCKS_POWERFIN) return mock.cancelDispatchApi(token, orderId);
	const res = await fetch(powerfinUrl(`/api/pos/dispatches/${orderId}/cancel`), {
		method: 'POST',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error cancelando despacho');
}

export async function getShiftDispatches(
	token: string, shiftId: number
): Promise<import('./types').DispatchOrder[]> {
	if (USE_MOCKS_POWERFIN) return mock.getShiftDispatches(token, shiftId);
	const res = await fetch(powerfinUrl(`/api/pos/shifts/${shiftId}/dispatches`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error obteniendo despachos del turno');
	return res.json();
}

/** Get ALL active dispatches across all open shifts (multi-device sync). */
export async function getActiveDispatches(
	token: string
): Promise<import('./types').DispatchOrder[]> {
	if (USE_MOCKS_POWERFIN) return [];
	const res = await fetch(powerfinUrl('/api/pos/dispatches/active'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error obteniendo despachos activos');
	return res.json();
}

// ── Vehicles ────────────────────────────────────────────────

export async function lookupVehicle(
	token: string, plate: string
): Promise<import('./types').VehicleResult> {
	if (USE_MOCKS_POWERFIN) return mock.lookupVehicle(token, plate);
	const res = await fetch(powerfinUrl(`/api/pos/vehicles?plate=${encodeURIComponent(plate)}`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error buscando vehículo');
	return res.json();
}

/** Get vehicles flagged for container sales (customer has no vehicle). */
export async function getPredefinedVehicles(
	token: string
): Promise<import('./types').PredefinedVehicle[]> {
	if (USE_MOCKS_POWERFIN) return mock.getPredefinedVehicles(token);
	const res = await fetch(powerfinUrl('/api/pos/vehicles/predefined'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error cargando vehículos predefinidos');
	return res.json();
}

/** Get the predefined vehicle with the fewest dispatches today (for container sales). */
export async function getNextPredefinedVehicle(
	token: string
): Promise<import('./types').PredefinedVehicle> {
	if (USE_MOCKS_POWERFIN) return mock.getNextPredefinedVehicle(token);
	const res = await fetch(powerfinUrl('/api/pos/vehicles/predefined/next'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error al obtener vehículo interno');
	return res.json();
}

/** Set or clear the preferred billing person for a vehicle. */
export async function setVehicleBillingPerson(
	token: string,
	vehicleId: number,
	personId: number | null
): Promise<void> {
	if (USE_MOCKS_POWERFIN) return mock.setVehicleBillingPerson(token, vehicleId, personId);
	const res = await fetch(powerfinUrl(`/api/pos/vehicles/${vehicleId}/billing-person`), {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify({ person_id: personId })
	});
	if (!res.ok) throw new Error('Error actualizando persona de facturación');
}

/** Update a person's contact fields (email, phone, address, name). */
export async function updatePerson(
	token: string,
	personId: number,
	data: { name?: string; email?: string; phone?: string; address?: string }
): Promise<void> {
	if (USE_MOCKS_POWERFIN) return mock.updatePerson(token, personId, data);
	const res = await fetch(powerfinUrl(`/api/pos/persons/${personId}`), {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error actualizando persona');
}

// ── Customer by ID ──────────────────────────────────────────

export async function getCustomerById(
	token: string,
	idType: 'CED' | 'RUC',
	idNumber: string,
	_updateBilling = false
): Promise<import('./types').Customer | null> {
	if (USE_MOCKS_POWERFIN) return mock.getCustomerById(token, idType, idNumber, _updateBilling);
	const results = await searchCustomers(token, idNumber);
	return results.find(c => c.id_type === idType && c.id_number === idNumber) ?? null;
}

/** Unified person lookup: local DB first, then external identity API (Sercobaco/SRI). */
export async function lookupPerson(
	token: string,
	idType: string,
	idNumber: string
): Promise<import('./types').PersonLookupResult> {
	if (USE_MOCKS_POWERFIN) return mock.lookupPerson(token, idType, idNumber);
	const res = await fetch(
		powerfinUrl(`/api/pos/persons/lookup?id_type=${encodeURIComponent(idType)}&id_number=${encodeURIComponent(idNumber)}`),
		{ headers: { Authorization: `Bearer ${token}` } }
	);
	if (!res.ok) throw new Error('Error buscando persona');
	return res.json();
}

// ── Register customer ───────────────────────────────────────

export async function registerCustomer(
	token: string,
	data: import('./types').CustomerFormData
): Promise<import('./types').RegisterCustomerResponse> {
	if (USE_MOCKS_POWERFIN) return mock.registerCustomer(token, data);
	const res = await fetch(powerfinUrl('/api/pos/customers'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error registrando cliente');
	return res.json();
}

// ── Collect dispatch ────────────────────────────────────────

export async function collectDispatch(
	token: string,
	orderId: string,
	data: import('./types').CollectDispatchRequest
): Promise<import('./types').CollectDispatchResponse> {
	if (USE_MOCKS_POWERFIN) return mock.collectDispatch(token, orderId, data);
	const res = await fetch(powerfinUrl(`/api/pos/dispatches/${orderId}/collect`), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) {
		let detail = 'Error cobrando despacho';
		try {
			const body = await res.json();
			detail = body?.detail || detail;
		} catch {}
		const err = new Error(detail) as any;
		err.status = res.status;
		throw err;
	}
	return res.json();
}

// ── Billing update (post-dispatch) ──────────────────────────

export async function updateDispatchBilling(
	token: string,
	orderId: string,
	data: import('./types').UpdateDispatchBillingRequest
): Promise<void> {
	if (USE_MOCKS_POWERFIN) return mock.updateDispatchBilling(token, orderId, data);
	const res = await fetch(powerfinUrl(`/api/pos/dispatches/${orderId}/billing`), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error actualizando facturación');
}

// ── Cash Management ──────────────────────────────────────────

export async function createCashMovement(
	token: string,
	data: import('./types').CreateCashMovementRequest
): Promise<import('./types').CashMovement> {
	if (USE_MOCKS_POWERFIN) return mock.createCashMovement(token, data);
	const res = await fetch(powerfinUrl('/api/pos/cash-movements'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error registrando movimiento');
	return res.json();
}

export async function getCashMovements(
	token: string,
	shiftId: number
): Promise<import('./types').CashMovement[]> {
	if (USE_MOCKS_POWERFIN) return mock.getCashMovements(token, shiftId);
	const res = await fetch(powerfinUrl(`/api/pos/shifts/${shiftId}/cash-movements`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error consultando movimientos');
	return res.json();
}

export async function getShiftCashSummary(
	token: string,
	shiftId: number
): Promise<import('./types').ShiftCashSummary> {
	if (USE_MOCKS_POWERFIN) return mock.getShiftCashSummary(token, shiftId);
	const res = await fetch(powerfinUrl(`/api/pos/shifts/${shiftId}/cash-summary`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error consultando saldo');
	return res.json();
}

export async function getShiftReceiptData(
	token: string,
	shiftId: number
): Promise<Record<string, unknown>> {
	if (USE_MOCKS_POWERFIN) return mock.getShiftCashSummary(token, shiftId) as unknown as Record<string, unknown>;
	const res = await fetch(powerfinUrl(`/api/pos/shifts/${shiftId}/receipt-data`), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error consultando datos de cierre');
	return res.json();
}

export async function getOnlineUsers(
	token: string
): Promise<import('./types').OnlineUser[]> {
	if (USE_MOCKS_POWERFIN) return mock.getOnlineUsers(token);
	const res = await fetch(powerfinUrl('/api/pos/users/online'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error consultando usuarios en línea');
	return res.json();
}

export async function createTransfer(
	token: string,
	data: import('./types').CreateTransferRequest
): Promise<import('./types').CashTransfer> {
	if (USE_MOCKS_POWERFIN) return mock.createTransfer(token, data);
	const res = await fetch(powerfinUrl('/api/pos/transfers'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error realizando transferencia');
	return res.json();
}

// ── Credit Contracts ────────────────────────────────────────

export async function getCreditContracts(token: string): Promise<any[]> {
	if (USE_MOCKS_POWERFIN) return [];
	const res = await fetch(powerfinUrl('/api/pos/credit-contracts'), {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) return [];
	return res.json();
}
