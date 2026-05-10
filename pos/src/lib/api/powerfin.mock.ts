import type {
	User, LoginRequest, LoginResponse, AppConfig, Customer,
	PriceInfo, Shift, OpenShiftRequest, CloseShiftResponse,
	VehicleResult, CustomerFormData, RegisterCustomerResponse
} from './types';

// ── Mock data ────────────────────────────────────────────────

const MOCK_USER: User = {
	user_id: 3,
	name: 'Carlos Sarmiento',
	role: 'DISPATCHER',
	location_id: 1,
	location_name: 'NEOPAUTE'
};

const MOCK_CONFIG: AppConfig = {
	location: {
		location_id: 1,
		name: 'NEOPAUTE',
		address: 'Av. Principal 123, Cuenca'
	},
	dispensers: [
		{
			dispenser_id: 1,
			fusion_pump_id: 1,
			name: 'Surtidor 1',
			hoses: [
				{ hose_id: 1, fusion_hose_id: 1, grade_id: 'SUPER', grade_name: 'Gasolina Super' },
				{ hose_id: 2, fusion_hose_id: 2, grade_id: 'SUPER', grade_name: 'Gasolina Super' }
			]
		},
		{
			dispenser_id: 2,
			fusion_pump_id: 2,
			name: 'Surtidor 2',
			hoses: [
				{ hose_id: 3, fusion_hose_id: 1, grade_id: 'SUPER', grade_name: 'Gasolina Super' },
				{ hose_id: 4, fusion_hose_id: 2, grade_id: 'SUPER', grade_name: 'Gasolina Super' }
			]
		}
	],
	grades: [
		{ grade_id: 'SUPER', name: 'Gasolina Super', unit: 'litros' }
	],
	price_lists: [
		{ code: 'STANDARD', name: 'Precio Normal' },
		{ code: 'VIP', name: 'Cliente VIP' }
	],
	payment_methods: [
		{ code: 'EFECTIVO', name: 'Efectivo', requires_reference: false },
		{ code: 'TARJETA', name: 'Tarjeta Crédito/Débito', requires_reference: true },
		{ code: 'QR', name: 'QR / Transferencia', requires_reference: false },
		{ code: 'CREDITO', name: 'Crédito', requires_reference: false },
		{ code: 'DEUNA', name: 'DeUna', requires_reference: true },
		{ code: 'JEPFAST', name: 'JepFast', requires_reference: true },
		{ code: 'SIPY', name: 'Sipy', requires_reference: true }
	]
};

const MOCK_CUSTOMERS: Customer[] = [
	{
		customer_id: '0912345678',
		id_type: 'CED',
		id_number: '0912345678',
		name: 'Juan Carlos Pérez',
		email: 'jperez@email.com',
		phone: '0991234567',
		price_list: 'VIP',
		price_list_name: 'Cliente VIP',
		credit_active: false,
		credit_balance: 0,
		plates: ['ABC-1234']
	},
	{
		customer_id: '1790012345001',
		id_type: 'RUC',
		id_number: '1790012345001',
		name: 'Transportes Andinos S.A.',
		email: 'trans@andinos.com',
		phone: '022345678',
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal',
		credit_active: true,
		credit_balance: 500,
		plates: ['XYZ-5678', 'XYZ-5679']
	},
	{
		customer_id: '1001234567001',
		id_type: 'RUC',
		id_number: '1001234567001',
		name: 'María Fernanda López',
		email: 'mflopez@email.com',
		phone: '0987654321',
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal',
		credit_active: false,
		credit_balance: 0,
		plates: []
	}
];

const MOCK_VEHICLES: Record<string, VehicleResult> = {
	'ABC-1234': {
		plate: 'ABC-1234',
		vehicle_found: true,
		incomplete_fields: [],
		owner: {
			customer_id: '0912345678',
			id_type: 'CED',
			id_number: '0912345678',
			name: 'Juan Carlos Pérez',
			email: 'jperez@email.com',
			phone: '0991234567'
		},
		price_list: 'VIP',
		price_list_name: 'Cliente VIP'
	},
	'XYZ-5678': {
		plate: 'XYZ-5678',
		vehicle_found: true,
		incomplete_fields: ['email'],
		owner: {
			customer_id: '1790012345001',
			id_type: 'RUC',
			id_number: '1790012345001',
			name: 'Transportes Andinos S.A.',
			email: null,
			phone: '022345678'
		},
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	}
};

// ── Mock delay ───────────────────────────────────────────────

function delay(ms = 300): Promise<void> {
	return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Mock implementation ──────────────────────────────────────

let mockToken = '';
let mockShift: Shift | null = null;
let shiftCounter = 45;

export async function login(data: LoginRequest): Promise<LoginResponse> {
	await delay(500);
	if (data.pin === '1234') {
		mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock_token';
		return {
			access_token: mockToken,
			expires_in: 28800,
			user: { ...MOCK_USER, name: data.username }
		};
	}
	throw new Error('Credenciales inválidas');
}

export async function fetchConfig(_token: string): Promise<AppConfig> {
	await delay(300);
	return MOCK_CONFIG;
}

export async function searchCustomers(_token: string, query: string): Promise<Customer[]> {
	await delay(200);
	const q = query.toLowerCase();
	return MOCK_CUSTOMERS.filter(c =>
		c.name.toLowerCase().includes(q) ||
		c.id_number.includes(q) ||
		c.plates.some(p => p.toLowerCase().includes(q))
	);
}

export async function getCustomerPrice(
	_token: string, customerId: string, _gradeId: string
): Promise<PriceInfo> {
	await delay(200);
	const customer = MOCK_CUSTOMERS.find(c => c.customer_id === customerId);
	const unitPrice = customer?.price_list === 'VIP' ? 1.100 : 1.500;
	return {
		grade_id: 'SUPER',
		grade_name: 'Gasolina Super',
		unit_price: unitPrice,
		price_list: customer?.price_list ?? 'STANDARD',
		currency: 'USD'
	};
}

export async function openShift(_token: string, data: OpenShiftRequest): Promise<Shift> {
	await delay(400);
	mockShift = {
		shift_id: ++shiftCounter,
		user_id: MOCK_USER.user_id,
		user_name: MOCK_USER.name,
		opened_at: new Date().toISOString(),
		accounting_date: new Date().toISOString().split('T')[0],
		status: 'OPEN',
		opening_cash: data.opening_cash,
		dispenser_ids: data.dispenser_ids
	};
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem('shift', JSON.stringify(mockShift));
	}
	return { ...mockShift };
}

export async function getCurrentShift(_token: string): Promise<Shift | null> {
	await delay(200);
	// In production, PowerFin is the source of truth.
	// The mock simulates persistence via localStorage on refresh.
	if (!mockShift && typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem('shift');
		if (stored) {
			try { mockShift = JSON.parse(stored); } catch { /* ignore */ }
		}
	}
	return mockShift ? { ...mockShift } : null;
}

export async function closeShift(
	_token: string, _shiftId: number, data: { closing_cash: number; notes: string }
): Promise<CloseShiftResponse> {
	await delay(500);
	mockShift = null;
	return {
		shift_id: shiftCounter,
		closed_at: new Date().toISOString(),
		opening_cash: 0,
		closing_cash: data.closing_cash,
		expected_cash: data.closing_cash,
		difference: 0,
		total_sales: 12,
		total_volume: 487.5,
		dispatch_count: 45
	};
}

export async function createDispatch(
	_token: string, _data: unknown
): Promise<{ order_id: string; status: string }> {
	await delay(300);
	const seq = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
	const date = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
	return {
		order_id: `OV-${date}-${seq}`,
		status: 'PENDING'
	};
}

export async function completeDispatch(
	_token: string, _orderId: string, _saleData: unknown
): Promise<void> {
	await delay(200);
}

export async function cancelDispatchApi(
	_token: string, _orderId: string
): Promise<void> {
	await delay(200);
}

export async function lookupVehicle(_token: string, plate: string): Promise<VehicleResult> {
	await delay(300);
	const normalized = plate.toUpperCase().replace(/\s+/g, '');
	const result = MOCK_VEHICLES[normalized];
	if (result) {
		return result;
	}
	return {
		plate: normalized,
		vehicle_found: false,
		incomplete_fields: [],
		owner: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	};
}

export async function getCustomerById(
	_token: string,
	idType: 'CED' | 'RUC',
	idNumber: string,
	_updateBilling = false
): Promise<Customer | null> {
	await delay(300);
	return MOCK_CUSTOMERS.find(c => c.id_type === idType && c.id_number === idNumber) ?? null;
}

export async function registerCustomer(
	_token: string,
	data: CustomerFormData
): Promise<RegisterCustomerResponse> {
	await delay(400);
	const newCustomer: Customer = {
		customer_id: data.id_number,
		id_type: data.id_type,
		id_number: data.id_number,
		name: data.name,
		email: data.email || null,
		phone: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal',
		credit_active: false,
		credit_balance: 0,
		plates: [data.plate]
	};
	MOCK_CUSTOMERS.push(newCustomer);
	MOCK_VEHICLES[data.plate.toUpperCase().replace(/\s+/g, '')] = {
		plate: data.plate.toUpperCase().replace(/\s+/g, ''),
		vehicle_found: true,
		incomplete_fields: [],
		owner: {
			customer_id: newCustomer.customer_id,
			id_type: newCustomer.id_type,
			id_number: newCustomer.id_number,
			name: newCustomer.name,
			email: newCustomer.email,
			phone: newCustomer.phone
		},
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	};
	return { customer_id: data.id_number, price_list: 'STANDARD' };
}
