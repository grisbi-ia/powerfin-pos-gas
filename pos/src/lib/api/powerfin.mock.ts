import type {
	User, LoginRequest, LoginResponse, AppConfig, Customer,
	PriceInfo, Shift, OpenShiftRequest, CloseShiftResponse,
	VehicleResult, CustomerFormData, RegisterCustomerResponse,
	CollectDispatchRequest, CollectDispatchResponse,
	DispatchOrder,
	CashMovement, CashTransfer, OnlineUser, ShiftCashSummary,
	CreateCashMovementRequest, CreateTransferRequest
} from './types';
import { SAFE_VAULT_USER_ID, SAFE_VAULT_ROLE } from './types';
import type { PredefinedVehicle } from './types';

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
		name: 'NEOGAS',
		address: 'Av. Principal 123, Cuenca'
	},
	dispensers: [
		{
			dispenser_id: 1,
			name: 'Surtidor DIESEL',
			printer_ip: '192.168.1.21',
		printer_port: 9100,
			sides: {
				A: [
					{ hose_id: 1, fusion_pump_id: 1, fusion_hose_id: 1, grade_id: 'DIESEL', grade_name: 'Diesel', unit_price: 3.103 }
				],
				B: [
					{ hose_id: 2, fusion_pump_id: 2, fusion_hose_id: 1, grade_id: 'DIESEL', grade_name: 'Diesel', unit_price: 3.103 }
				]
			}
		}
	],
	grades: [
		{ grade_id: 'DIESEL', name: 'Diesel', unit: 'GALONES' }
	],
	price_lists: [
		{ code: 'STANDARD', name: 'Precio Normal' },
		{ code: 'VIP', name: 'Cliente VIP' }
	],
	payment_methods: [
		{ payment_method_id: 1, code: 'CASH', name: 'Efectivo', sri_code: '01', requires_reference: false },
		{ payment_method_id: 4, code: 'TCTD', name: 'Tarjeta Crédito/Débito', sri_code: '19', requires_reference: true },
		{ payment_method_id: 5, code: 'DEUNA', name: 'QR / Transferencia', sri_code: '20', requires_reference: false },
		{ payment_method_id: 2, code: 'CREDITPR', name: 'Crédito', sri_code: '20', requires_reference: false },
		{ payment_method_id: 5, code: 'DEUNA', name: 'DeUna', sri_code: '20', requires_reference: true },
		{ payment_method_id: 6, code: 'JEPFAST', name: 'JepFast', sri_code: '20', requires_reference: true },
		{ payment_method_id: 7, code: 'JAZ', name: 'Sipy', sri_code: '20', requires_reference: true }
	],
	polling: {
		interval_ms: 2000,
		enabled: true
	}
};

const MOCK_CUSTOMERS: Customer[] = [
	{
		customer_id: '0912345678',
		id_type: 'CED',
		id_number: '0912345678',
		name: 'Juan Carlos Pérez',
		email: 'jperez@email.com',
		phone: '0991234567',
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal',
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
	'ABC1234': {
		vehicle_id: 1,
		plate: 'ABC1234',
		vehicle_found: true,
		incomplete_fields: [],
		owner: {
			person_id: 1,
			customer_id: '0912345678',
			id_type: 'CED',
			id_number: '0912345678',
			name: 'Juan Carlos Pérez',
			address: 'Av. Siempre Viva 742',
			email: 'jperez@email.com',
			phone: '0991234567'
		},
		billing_person: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	},
	'XYZ5678': {
		vehicle_id: 2,
		plate: 'XYZ5678',
		vehicle_found: true,
		incomplete_fields: ['email'],
		owner: {
			person_id: 2,
			customer_id: '1790012345001',
			id_type: 'RUC',
			id_number: '1790012345001',
			name: 'Transportes Andinos S.A.',
			address: null,
			email: null,
			phone: '022345678'
		},
		billing_person: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	}
};

// ── Mock delay ───────────────────────────────────────────────

function delay(ms = 300): Promise<void> {
	return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Mock implementation ──────────────────────────────────────

const MOCK_SERVER_ORDERS_KEY = 'mockServerOrders';

let mockToken = '';
let mockShift: Shift | null = null;
let shiftCounter = 45;
let orderSeq = 0;

// ── Mock server persistence (simula la base de datos de PowerFin) ──
function loadMockOrders(): DispatchOrder[] {
	try {
		if (typeof localStorage === 'undefined') return [];
		const stored = localStorage.getItem(MOCK_SERVER_ORDERS_KEY);
		if (!stored) return [];
		return JSON.parse(stored) as DispatchOrder[];
	} catch {
		return [];
	}
}

function saveMockOrders() {
	try {
		if (typeof localStorage === 'undefined') return;
		localStorage.setItem(MOCK_SERVER_ORDERS_KEY, JSON.stringify(mockOrders));
	} catch { /* quota exceeded */ }
}

const mockOrders: DispatchOrder[] = loadMockOrders();

// Restore sequence counter to avoid duplicate order IDs after refresh
if (mockOrders.length > 0) {
	orderSeq = mockOrders.length;
}

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
	const unitPrice = customer?.price_list === 'VIP' ? 2.950 : 3.103;
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
		opening_cash: data.opening_cash
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
	_token: string, _shiftId: number, _data: { notes: string }
): Promise<CloseShiftResponse> {
	await delay(500);
	mockShift = null;
	return {
		shift_id: shiftCounter,
		closed_at: new Date().toISOString(),
		opening_cash: 0,
		surplus: 0,
		shortage: 0,
		total_sales: 12,
		total_volume: 487.5,
		dispatch_count: 45,
		cash_income: 100,
		cash_income_count: 2,
		cash_expense: 50,
		cash_expense_count: 1,
		cash_deposits: 200,
		cash_deposits_count: 2,
		cash_transfers_out: 75,
		cash_transfers_out_count: 1,
		cash_transfers_in: 0,
		cash_transfers_in_count: 0,
		cash_safe_drops: 0,
		cash_safe_drops_count: 0,
		sales_cash: 450,
		sales_cash_count: 8,
		non_cash_sales: [
			{ method_code: 'TARJETA', method_name: 'Tarjeta', total: 120, count: 2 },
			{ method_code: 'QR', method_name: 'QR', total: 80, count: 2 },
		],
	};
}

export async function createDispatch(
	_token: string, _data: unknown
): Promise<{ order_id: string; status: string }> {
	await delay(300);
	const data = _data as Record<string, unknown>;
	orderSeq++;
	const seq = String(orderSeq).padStart(3, '0');
	const date = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
	const orderId = `OV-${date}-${seq}`;
	const order: DispatchOrder = {
		order_id: orderId,
		dispenser_id: data.dispenser_id as number,
		hose_id: data.hose_id as number,
		side: (data.side as 'A' | 'B') ?? 'A',
		grade: 'SUPER',
		preset_type: (data.preset_type as 'MONEY' | 'VOLUME') ?? 'MONEY',
		preset_value: data.preset_value as string,
		unit_price: (data as Record<string, number>).unit_price ?? 1.500,
		payment_method_id: (data.payment_method_id as number) ?? 1,
		customer_id: data.customer_id as string | undefined,
		plate: data.plate as string | undefined,
		status: 'AUTHORIZED',
		created_at: new Date().toISOString(),
		shift_id: mockShift?.shift_id ?? 0,
		cashier_name: mockShift?.user_name ?? '',
		authorized_by_user_id: mockShift?.user_id
	};
	mockOrders.push(order);
	saveMockOrders();
	return { order_id: orderId, status: 'PENDING' };
}

export async function completeDispatch(
	_token: string, _orderId: string, _saleData: unknown
): Promise<void> {
	await delay(200);
	const sale = _saleData as Record<string, unknown>;
	const order = mockOrders.find(o => o.order_id === _orderId);
	if (order) {
		order.status = 'COMPLETED';
		order.final_amount = sale.amount as number;
		order.final_volume = sale.volume as string;
		order.invoice_number = sale.invoice_number as string | undefined;
		saveMockOrders();
	}
}

export async function cancelDispatchApi(
	_token: string, _orderId: string
): Promise<void> {
	await delay(200);
	const order = mockOrders.find(o => o.order_id === _orderId);
	if (order) {
		order.status = 'CANCELLED';
		saveMockOrders();
	}
}

export async function collectDispatch(
	_token: string, orderId: string, _data: CollectDispatchRequest
): Promise<CollectDispatchResponse> {
	await delay(300);
	// Mark order as collected in mock storage
	const order = mockOrders.find(o => o.order_id === orderId);
	if (order) {
		order.status = 'COLLECTED';
		order.shift_id = _data.collected_by_shift_id;
		saveMockOrders();
	}
	return {
		order_id: orderId,
		status: 'COLLECTED',
		collected_by_shift_id: _data.collected_by_shift_id,
		collected_by_name: MOCK_USER.name,
		payment_method_id: _data.payment_method_id,
		collected_amount: _data.collected_amount,
		change_amount: _data.change_amount
	};
}

export async function updateDispatchBilling(
	_token: string,
	orderId: string,
	data: import('./types').UpdateDispatchBillingRequest
): Promise<void> {
	await delay(200);
	const order = mockOrders.find(o => o.order_id === orderId);
	if (order) {
		if (data.customer_id !== undefined) order.customer_id = data.customer_id;
		if (data.customer_name !== undefined) order.customer_name = data.customer_name;
		if (data.plate !== undefined) order.plate = data.plate;
		saveMockOrders();
	}
}

export async function lookupVehicle(_token: string, plate: string): Promise<VehicleResult> {
	await delay(300);
	const normalized = plate.toUpperCase().replace(/\s+/g, '');
	const result = MOCK_VEHICLES[normalized];
	if (result) {
		// Inject mock billing person if set
		const billing = _mockVehicleBilling[normalized] ?? null;
		return { ...result, billing_person: billing };
	}
	return {
		vehicle_id: 0,
		plate: normalized,
		vehicle_found: false,
		incomplete_fields: [],
		owner: null,
		billing_person: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	};
}

const _mockVehicleBilling: Record<string, VehicleResult['billing_person']> = {};

export async function setVehicleBillingPerson(
	_token: string,
	_vehicleId: number,
	personId: number | null
): Promise<void> {
	await delay(200);
	// Mock: use ABC1234 as the only vehicle for testing
	if (personId !== null) {
		const person = MOCK_CUSTOMERS.find(c => parseInt(c.customer_id) === personId);
		if (person) {
			_mockVehicleBilling['ABC1234'] = {
				person_id: personId,
				customer_id: person.customer_id,
				id_type: person.id_type,
				id_number: person.id_number,
				name: person.name,
				address: null,
				email: person.email,
				phone: person.phone
			};
		}
	} else {
		delete _mockVehicleBilling['ABC1234'];
	}
}

export async function getPredefinedVehicles(_token: string): Promise<PredefinedVehicle[]> {
	await delay(100);
	return [
		{ vehicle_id: 1, plate: 'ABC001', owner_name: 'Juan Pérez' },
		{ vehicle_id: 2, plate: 'ABC002', owner_name: 'María López' },
		{ vehicle_id: 3, plate: 'ABC003', owner_name: 'Empresa Tanques S.A.' },
	];
}

export async function updatePerson(
	_token: string,
	personId: number,
	data: { name?: string; email?: string; phone?: string; address?: string }
): Promise<void> {
	await delay(200);
	const person = MOCK_CUSTOMERS.find(c => parseInt(c.customer_id) === personId);
	if (person) {
		if (data.name) person.name = data.name;
		if (data.email) person.email = data.email;
		if (data.phone) person.phone = data.phone;
	}
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

export async function lookupPerson(
	_token: string,
	idType: string,
	idNumber: string
): Promise<import('./types').PersonLookupResult> {
	await delay(300);
	const person = MOCK_CUSTOMERS.find(c => c.id_type === idType && c.id_number === idNumber);
	if (person) {
		return {
			found: true,
			local: true,
			source: 'database',
			data: {
				person_id: parseInt(person.customer_id) || 0,
				name: person.name,
				id_type: person.id_type,
				id_number: person.id_number,
				address: null,
				email: person.email,
				phone: person.phone,
				plates: person.plates,
				price_list: person.price_list,
				price_list_name: person.price_list_name
			}
		};
	}
	return { found: false, local: false, source: null, data: null };
}

export async function getShiftDispatches(_token: string, _shiftId: number): Promise<DispatchOrder[]> {
	await delay(200);
	// Return all mock orders created during this session (in-memory)
	return [...mockOrders];
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
		vehicle_id: 999,
		plate: data.plate.toUpperCase().replace(/\s+/g, ''),
		vehicle_found: true,
		incomplete_fields: [],
		owner: {
			person_id: null,
			customer_id: newCustomer.customer_id,
			id_type: newCustomer.id_type,
			id_number: newCustomer.id_number,
			name: newCustomer.name,
			address: null,
			email: newCustomer.email,
			phone: newCustomer.phone
		},
		billing_person: null,
		price_list: 'STANDARD',
		price_list_name: 'Precio Normal'
	};
	return { customer_id: data.id_number, price_list: 'STANDARD' };
}

// ═══════════════════════════════════════════════════════════════
// Cash Management Mocks
// ═══════════════════════════════════════════════════════════════

const MOCK_CASH_MOVEMENTS_KEY = 'mockCashMovements';
const MOCK_TRANSFERS_KEY = 'mockTransfers';

function loadMockMovements(): CashMovement[] {
	try {
		if (typeof localStorage === 'undefined') return [];
		const stored = localStorage.getItem(MOCK_CASH_MOVEMENTS_KEY);
		return stored ? JSON.parse(stored) as CashMovement[] : [];
	} catch { return []; }
}

function saveMockMovements(movements: CashMovement[]) {
	try {
		if (typeof localStorage === 'undefined') return;
		localStorage.setItem(MOCK_CASH_MOVEMENTS_KEY, JSON.stringify(movements));
	} catch { /* quota exceeded */ }
}

function loadMockTransfers(): CashTransfer[] {
	try {
		if (typeof localStorage === 'undefined') return [];
		const stored = localStorage.getItem(MOCK_TRANSFERS_KEY);
		return stored ? JSON.parse(stored) as CashTransfer[] : [];
	} catch { return []; }
}

function saveMockTransfers(transfers: CashTransfer[]) {
	try {
		if (typeof localStorage === 'undefined') return;
		localStorage.setItem(MOCK_TRANSFERS_KEY, JSON.stringify(transfers));
	} catch { /* quota exceeded */ }
}

const mockMovements: CashMovement[] = loadMockMovements();
const mockTransfers: CashTransfer[] = loadMockTransfers();
let movementSeq = mockMovements.length;
let transferSeq = mockTransfers.length;

const MOCK_ONLINE_USERS: OnlineUser[] = [
	{ user_id: 3, name: 'Carlos Sarmiento', role: 'DISPATCHER', shift_id: 45, sales_count: 12, total_amount: 587.50 },
	{ user_id: 4, name: 'María Fernanda López', role: 'DISPATCHER', shift_id: 46, sales_count: 8, total_amount: 342.00 },
	{ user_id: 5, name: 'Pedro Ramírez', role: 'DISPATCHER', shift_id: 47, sales_count: 15, total_amount: 723.80 },
	{ user_id: SAFE_VAULT_USER_ID, name: 'Caja Fuerte', role: SAFE_VAULT_ROLE, shift_id: 0, sales_count: 0, total_amount: 0 }
];

export async function createCashMovement(
	_token: string, data: CreateCashMovementRequest
): Promise<CashMovement> {
	await delay(300);

	// Calculate running balance
	const shiftMovements = mockMovements.filter(m => m.shift_id === data.shift_id);
	const lastBalance = shiftMovements.length > 0
		? shiftMovements[shiftMovements.length - 1].running_balance
		: 0;

	movementSeq++;
	const amount = data.type === 'INCOME' ? data.amount : -data.amount;
	const movement: CashMovement = {
		movement_id: movementSeq,
		shift_id: data.shift_id,
		type: data.type,
		amount: data.amount,
		observation: data.observation,
		created_at: new Date().toISOString(),
		running_balance: lastBalance + amount
	};

	mockMovements.push(movement);
	saveMockMovements(mockMovements);
	return movement;
}

export async function getCashMovements(
	_token: string, shiftId: number
): Promise<CashMovement[]> {
	await delay(200);
	return mockMovements
		.filter(m => m.shift_id === shiftId)
		.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

export async function getShiftCashSummary(
	_token: string, shiftId: number
): Promise<ShiftCashSummary> {
	await delay(200);
	const movements = mockMovements.filter(m => m.shift_id === shiftId);
	const transfers = mockTransfers.filter(t => t.from_shift_id === shiftId || t.to_user_id === shiftId);

	const total_income = movements
		.filter(m => m.type === 'INCOME')
		.reduce((sum, m) => sum + m.amount, 0);
	const total_expense = movements
		.filter(m => m.type === 'EXPENSE')
		.reduce((sum, m) => sum + m.amount, 0);

	// Sales cash: sum of COMPLETED orders with CASH payment for this shift
	const salesCash = mockOrders
		.filter(o => o.shift_id === shiftId && o.status === 'COMPLETED' && o.payment_method_id === 1)
		.reduce((sum, o) => sum + (o.final_amount ?? 0), 0);

	const openingCash = mockShift?.opening_cash ?? 0;

	return {
		shift_id: shiftId,
		opening_cash: openingCash,
		current_balance: openingCash + total_income + salesCash - total_expense,
		total_income,
		total_expense,
		total_sales_cash: salesCash,
		total_transfers_received: 0,
		total_transfers_sent: 0,
		total_safe_drops: 0
	};
}

export async function getOnlineUsers(_token: string): Promise<OnlineUser[]> {
	await delay(200);
	// Calculate real sales data from mock orders
	return MOCK_ONLINE_USERS.map(u => {
		if (u.role === SAFE_VAULT_ROLE) return { ...u, sales_count: 0, total_amount: 0 };
		const userOrders = mockOrders.filter(o => o.shift_id === u.shift_id && o.status === 'COMPLETED');
		return {
			...u,
			sales_count: userOrders.length,
			total_amount: userOrders.reduce((sum, o) => sum + (o.final_amount ?? 0), 0)
		};
	});
}

export async function createTransfer(
	_token: string, data: CreateTransferRequest
): Promise<CashTransfer> {
	await delay(300);

	const fromUser = MOCK_ONLINE_USERS.find(u => u.shift_id === data.from_shift_id);
	const toUser = MOCK_ONLINE_USERS.find(u => u.user_id === data.to_user_id);

	transferSeq++;
	const transfer: CashTransfer = {
		transfer_id: transferSeq,
		sender_movement_id: movementSeq + 1,
		from_shift_id: data.from_shift_id,
		from_user_name: fromUser?.name ?? 'Desconocido',
		to_user_id: data.to_user_id,
		to_user_name: toUser?.name ?? 'Desconocido',
		amount: data.amount,
		observation: data.observation,
		created_at: new Date().toISOString()
	};

	mockTransfers.push(transfer);
	saveMockTransfers(mockTransfers);

	// Also create a cash movement for the sender (EXPENSE)
	movementSeq++;
	const shiftMovements = mockMovements.filter(m => m.shift_id === data.from_shift_id);
	const lastBalance = shiftMovements.length > 0
		? shiftMovements[shiftMovements.length - 1].running_balance
		: 0;

	const movement: CashMovement = {
		movement_id: movementSeq,
		shift_id: data.from_shift_id,
		type: toUser?.role === SAFE_VAULT_ROLE ? 'SAFE_DROP' : 'TRANSFER_OUT',
		amount: data.amount,
		observation: data.observation,
		related_user_id: data.to_user_id,
		related_user_name: toUser?.name,
		created_at: new Date().toISOString(),
		running_balance: lastBalance - data.amount
	};
	mockMovements.push(movement);
	saveMockMovements(mockMovements);

	return transfer;
}
