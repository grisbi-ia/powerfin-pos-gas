export interface User {
	user_id: number;
	name: string;
	role: 'DISPATCHER' | 'SUPERVISOR';
	location_id: number;
	location_name: string;
}

export interface LoginResponse {
	access_token: string;
	expires_in: number;
	user: User;
}

export interface LoginRequest {
	username: string;
	pin: string;
}

export interface AppConfig {
	location: {
		location_id: number;
		name: string;
		ruc?: string;
		address?: string;
		phone?: string;
		city?: string;
		province?: string;
		country?: string;
		fiscal_regime?: string;
		sri_environment?: number;
		emission_type?: number;
	};
	printer_policy?: string;
	max_cash_in_hand?: number;
	cash_printer_ip?: string;
	cash_printer_port?: number;
	dispensers: DispenserConfig[];
	grades: GradeConfig[];
	price_lists: PriceListConfig[];
	payment_methods: PaymentMethodConfig[];
	polling?: {
		interval_ms: number;
		enabled: boolean;
	};
}

export interface PaymentMethodConfig {
	payment_method_id: number;
	code: string;
	name: string;
	sri_code: string;
	requires_reference: boolean;
}

export interface DispenserConfig {
	dispenser_id: number;
	name: string;
	printer_ip?: string | null;
	printer_port?: number;
	sides: {
		A: HoseConfig[];
		B: HoseConfig[];
	};
}

export interface HoseConfig {
	hose_id: number;
	fusion_hose_id: number;
	fusion_pump_id: number;
	grade_id: string;
	grade_name: string;
	unit_price: number;
	base_price?: number;
	subsidy_per_unit?: number;
}

export interface GradeConfig {
	grade_id: string;
	name: string;
	unit: string;
}

export interface PriceListConfig {
	code: string;
	name: string;
}

export interface Customer {
	customer_id: string;
	person_id?: number | null;
	id_type: string;
	id_number: string;
	name: string;
	address?: string | null;
	email: string | null;
	phone: string | null;
	price_list: string;
	price_list_name: string;
	credit_active: boolean;
	credit_balance: number;
	plates: string[];
}

export interface VehicleResult {
	vehicle_id: number;
	plate: string;
	vehicle_found: boolean;
	incomplete_fields: string[];
	owner: {
		person_id: number | null;
		customer_id: string;
		id_type: string;
		id_number: string;
		name: string;
		address: string | null;
		email: string | null;
		phone: string | null;
	} | null;
	/** Preferred billing person (set via PUT /vehicles/{id}/billing-person). Null = use owner. */
	billing_person: {
		person_id: number | null;
		customer_id: string;
		id_type: string;
		id_number: string;
		name: string;
		address: string | null;
		email: string | null;
		phone: string | null;
	} | null;
	price_list: string;
	price_list_name: string;
}

export interface PredefinedVehicle {
	vehicle_id: number;
	plate: string;
	owner_name: string;
}

export interface CustomerFormData {
	id_type: 'CED' | 'RUC';
	id_number: string;
	name: string;
	email: string;
	phone?: string;
	address?: string;
	plate: string;
}

/** Unified person lookup via /api/pos/persons/lookup */
export interface PersonLookupData {
	person_id: number | null;
	name: string;
	id_type: string;
	id_number: string;
	address: string | null;
	email: string | null;
	phone: string | null;
	plates: string[];
	price_list: string;
	price_list_name: string;
}

export interface PersonLookupResult {
	found: boolean;
	local: boolean;
	source: string | null;
	data: PersonLookupData | null;
}

export interface RegisterCustomerResponse {
	customer_id: string;
	price_list: string;
}

export interface PriceInfo {
	grade_id: string;
	grade_name: string;
	unit_price: number;
	price_list: string;
	currency: string;
}

export interface Shift {
	shift_id: number;
	user_id: number;
	user_name: string;
	opened_at: string;
	accounting_date: string;
	status: 'OPEN' | 'CLOSED';
	opening_cash: number;
}

export interface OpenShiftRequest {
	opening_cash: number;
	notes: string;
	user_name?: string;
}

export interface CloseShiftRequest {
	notes: string;
}

export interface CloseShiftResponse {
	shift_id: number;
	closed_at: string;
	opening_cash: number;
	surplus: number;
	shortage: number;
	total_sales: number;
	total_volume: number;
	dispatch_count: number;
	cash_income: number;
	cash_income_count: number;
	cash_expense: number;
	cash_expense_count: number;
	cash_deposits: number;
	cash_deposits_count: number;
	cash_transfers_out: number;
	cash_transfers_out_count: number;
	cash_transfers_in: number;
	cash_transfers_in_count: number;
	cash_safe_drops: number;
	cash_safe_drops_count: number;
	sales_cash: number;
	sales_cash_count: number;
	non_cash_sales: { method_code: string; method_name: string; total: number; count: number }[];
}

export interface DispatchOrder {
	order_id: string;
	dispenser_id: number;
	hose_id: number;
	side: 'A' | 'B';
	grade: string;
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	unit_price: number;
	price_without_subsidy?: number;
	subsidy_per_unit?: number;
	subsidy_amount?: number;
	payment_method_id: number;
	payment_method_name?: string;
	customer_id?: string;
	customer_name?: string;
	customer_address?: string;
	customer_phone?: string;
	customer_email?: string;
	plate?: string;
	status: 'PENDING' | 'AUTHORIZED' | 'FUELLING' | 'COMPLETED' | 'CANCELLED' | 'COLLECTED';
	created_at: string;
	shift_id: number;
	cashier_name?: string;
	authorized_by_user_id?: number;
	final_amount?: number;
	final_volume?: string;
	invoice_number?: string;
	access_key?: string;
	credit_contract_id?: number;
	credit_status?: string;
	contract_code?: string;
	sri_status?: string;
	key49_access_key?: string;
}

export interface CreateDispatchRequest {
	dispenser_id: number;
	hose_id: number;
	side: 'A' | 'B';
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	unit_price: number;
	payment_method_id: number;
	customer_id?: string;
	plate?: string;
	dispatch_type_code?: string;
	credit_contract_id?: number;
}

export interface CreateDispatchResponse {
	order_id: string;
	status: string;
}

export interface SaleCompletedData {
	order_id: string;
	fusion_sale_id: string;
	volume: string;
	amount: string;
	unit_price: string;
	payment_method_id: number;
	completed_at: string;
}

export type PresetType = 'MONEY' | 'VOLUME' | 'FULL';

export interface CollectDispatchRequest {
	collected_by_shift_id: number;
	payment_method_id: number;
	collected_amount: number;
	change_amount: number;
	reference_code?: string;
}

export interface UpdateDispatchBillingRequest {
	customer_id?: string;
	customer_name?: string;
	plate?: string;
}

export interface CollectDispatchResponse {
	order_id: string;
	status: 'COLLECTED';
	collected_by_shift_id: number;
	collected_by_name: string;
	payment_method_id: number;
	collected_amount: number;
	change_amount: number;
	receipt_data?: {
		printerIp: string;
		printerPort: number;
		dispenserId: number;
		fuelData: Record<string, unknown>;
	};
}

export interface AuthorizeData {
	order_id: string;
	dispenser_id: number;
	hose_id: number;
	side: 'A' | 'B';
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	payment_method_id: number;
	customer_id?: string;
	plate?: string;
	unit_price: number;
	price_list?: string;
}

/** Estado en tiempo real de una manguera individual */
export interface HoseState {
	hoseId: number;
	dispenserId: number;
	side: 'A' | 'B';
	fusionHoseId: number;
	gradeId: string;
	gradeName: string;
	status: string;        // IDLE | CALLING | AUTHORIZED | STARTING | FUELLING | PAUSED | STOPPED | ERROR | CLOSED
	subStatus: string;
	presetAmount: number;
	attendantName: string | null;
	shiftId: number | null;
}

/** Estado completo de un surtidor con sus dos lados */
export interface DispenserState {
	dispenserId: number;
	name: string;
	connected: boolean;
	online: boolean;
	sides: {
		A: HoseState[];
		B: HoseState[];
	};
}

export type PrintPolicy = 'ALWAYS' | 'ASK' | 'NEVER';

export interface SseEvent {
	event: string;
	data: Record<string, unknown>;
}

/** Evento SSE: cambio de estado de una manguera */
export interface HoseStatusEvent {
	type: 'HOSE_STATUS';
	dispenserId: number;
	hoseId: number;
	side: 'A' | 'B';
	fusionHoseId: number;
	status: string;
	subStatus: string;
	attendantName?: string;
	presetAmount?: number;
}

/** Evento SSE: progreso de despacho en una manguera */
export interface FuelingProgressEvent {
	type: 'FUELING_PROGRESS';
	dispenserId: number;
	hoseId: number;
	side: 'A' | 'B';
	volume: string;
	amount: string;
}

/** Evento SSE: venta completada en una manguera */
export interface SaleCompletedEvent {
	type: 'SALE_COMPLETED';
	dispenserId: number;
	hoseId: number;
	side: 'A' | 'B';
	orderId: string;
	volume: string;
	amount: string;
}

// ═══════════════════════════════════════════════════════════════
// Cash Management — Ingresos, Egresos, Transferencias
// ═══════════════════════════════════════════════════════════════

/** Special user_id representing the safe vault (Caja Fuerte) */
export const SAFE_VAULT_USER_ID = 0;
export const SAFE_VAULT_ROLE = 'SAFE_VAULT';

export type CashMovementType = 'INCOME' | 'EXPENSE' | 'DEPOSIT' | 'TRANSFER_IN' | 'TRANSFER_OUT' | 'SAFE_DROP';

export interface CashMovement {
	movement_id: number;
	shift_id: number;
	type: CashMovementType;
	amount: number;
	observation: string;
	related_user_id?: number;
	related_user_name?: string;
	created_at: string;
	running_balance: number;
}

export interface CashTransfer {
	transfer_id: number;
	sender_movement_id: number;
	from_shift_id: number;
	from_user_name: string;
	to_user_id: number;
	to_user_name: string;
	amount: number;
	observation: string;
	created_at: string;
}

export interface OnlineUser {
	user_id: number;
	name: string;
	role: string;
	shift_id: number;
	sales_count: number;
	total_amount: number;
}

export interface ShiftCashSummary {
	shift_id: number;
	opening_cash: number;
	current_balance: number;
	total_income: number;
	total_expense: number;
	total_sales_cash: number;
	total_transfers_received: number;
	total_transfers_sent: number;
	total_safe_drops: number;
}

export interface CreateCashMovementRequest {
	shift_id: number;
	type: 'INCOME' | 'EXPENSE' | 'DEPOSIT';
	amount: number;
	observation: string;
}

export interface CreateTransferRequest {
	from_shift_id: number;
	to_user_id: number;
	amount: number;
	observation: string;
}

export interface AuthStore {
	token: string | null;
	user: User | null;
	isAuthenticated: boolean;
}

export interface ShiftStore {
	currentShift: Shift | null;
	isOpen: boolean;
}

export interface ConfigStore {
	config: AppConfig | null;
	loaded: boolean;
}

export interface DispensersStore {
	dispensers: Map<number, DispenserState>;
	fusionConnected: boolean;
}
