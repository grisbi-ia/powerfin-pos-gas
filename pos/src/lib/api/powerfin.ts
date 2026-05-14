import type {
	User, LoginRequest, LoginResponse, AppConfig, Customer,
	PriceInfo, Shift, OpenShiftRequest, CloseShiftResponse,
	CreateDispatchRequest, CreateDispatchResponse, SaleCompletedData
} from './types';

const BASE_URL = 'http://localhost:8080';

// ── Auth ─────────────────────────────────────────────────────

export async function login(data: LoginRequest): Promise<LoginResponse> {
	const res = await fetch(`${BASE_URL}/api/pos/auth/login`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Credenciales inválidas');
	return res.json();
}

// ── Config ───────────────────────────────────────────────────

export async function fetchConfig(token: string): Promise<AppConfig> {
	const res = await fetch(`${BASE_URL}/api/pos/config`, {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error al cargar configuración');
	return res.json();
}

// ── Customers ────────────────────────────────────────────────

export async function searchCustomers(token: string, query: string): Promise<Customer[]> {
	const res = await fetch(`${BASE_URL}/api/pos/customers?q=${encodeURIComponent(query)}`, {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (res.status === 404) return [];
	if (!res.ok) throw new Error('Error buscando clientes');
	return res.json();
}

export async function getCustomerPrice(
	token: string, customerId: string, gradeId: string
): Promise<PriceInfo> {
	const res = await fetch(
		`${BASE_URL}/api/pos/prices?customerId=${customerId}&gradeId=${gradeId}`,
		{ headers: { Authorization: `Bearer ${token}` } }
	);
	if (!res.ok) throw new Error('Error obteniendo precio');
	return res.json();
}

// ── Shifts ───────────────────────────────────────────────────

export async function openShift(token: string, data: OpenShiftRequest): Promise<Shift> {
	const res = await fetch(`${BASE_URL}/api/pos/shifts/open`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error abriendo turno');
	return res.json();
}

export async function getCurrentShift(token: string): Promise<Shift | null> {
	const res = await fetch(`${BASE_URL}/api/pos/shifts/current`, {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (res.status === 404) return null;
	if (!res.ok) throw new Error('Error consultando turno');
	return res.json();
}

export async function closeShift(
	token: string, shiftId: number, data: { closing_cash: number; notes: string }
): Promise<CloseShiftResponse> {
	const res = await fetch(`${BASE_URL}/api/pos/shifts/${shiftId}/close`, {
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
	const res = await fetch(`${BASE_URL}/api/pos/dispatches`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Error creando despacho');
	return res.json();
}

export async function completeDispatch(
	token: string, orderId: string, saleData: SaleCompletedData
): Promise<void> {
	const res = await fetch(`${BASE_URL}/api/pos/dispatches/${orderId}/complete`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify(saleData)
	});
	if (!res.ok) throw new Error('Error completando despacho');
}

export async function cancelDispatch(
	token: string, orderId: string
): Promise<void> {
	const res = await fetch(`${BASE_URL}/api/pos/dispatches/${orderId}/cancel`, {
		method: 'POST',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error cancelando despacho');
}

export async function getShiftDispatches(
	token: string, shiftId: number
): Promise<import('./types').DispatchOrder[]> {
	const res = await fetch(`${BASE_URL}/api/pos/shifts/${shiftId}/dispatches`, {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error('Error obteniendo despachos del turno');
	return res.json();
}
