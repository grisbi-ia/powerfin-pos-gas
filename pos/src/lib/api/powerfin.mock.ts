import type {
	User, LoginRequest, LoginResponse, AppConfig, Customer,
	PriceInfo, Shift, OpenShiftRequest, CloseShiftResponse
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
	}
];

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
	return { ...mockShift };
}

export async function getCurrentShift(_token: string): Promise<Shift | null> {
	await delay(200);
	return mockShift;
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
