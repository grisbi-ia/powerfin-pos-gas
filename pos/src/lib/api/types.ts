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
		address: string;
	};
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
	code: string;
	name: string;
	requires_reference: boolean;
}

export interface DispenserConfig {
	dispenser_id: number;
	fusion_pump_id: number;
	name: string;
	printer_island?: number;
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
	id_type: string;
	id_number: string;
	name: string;
	email: string | null;
	phone: string | null;
	price_list: string;
	price_list_name: string;
	credit_active: boolean;
	credit_balance: number;
	plates: string[];
}

export interface VehicleResult {
	plate: string;
	vehicle_found: boolean;
	incomplete_fields: string[];
	owner: {
		customer_id: string;
		id_type: string;
		id_number: string;
		name: string;
		email: string | null;
		phone: string | null;
	} | null;
	price_list: string;
	price_list_name: string;
}

export interface CustomerFormData {
	id_type: 'CED' | 'RUC';
	id_number: string;
	name: string;
	email: string;
	plate: string;
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
}

export interface CloseShiftRequest {
	closing_cash: number;
	notes: string;
}

export interface CloseShiftResponse {
	shift_id: number;
	closed_at: string;
	opening_cash: number;
	closing_cash: number;
	expected_cash: number;
	difference: number;
	total_sales: number;
	total_volume: number;
	dispatch_count: number;
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
	payment_method: string;
	customer_id?: string;
	customer_name?: string;
	plate?: string;
	status: 'PENDING' | 'AUTHORIZED' | 'FUELLING' | 'COMPLETED' | 'CANCELLED' | 'COLLECTED';
	created_at: string;
	shift_id: number;
	authorized_by?: string;
	final_amount?: number;
	final_volume?: string;
	invoice_number?: string;
}

export interface CreateDispatchRequest {
	dispenser_id: number;
	hose_id: number;
	side: 'A' | 'B';
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	payment_method: string;
	customer_id?: string;
	plate?: string;
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
	payment_method: string;
	completed_at: string;
}

export type PresetType = 'MONEY' | 'VOLUME' | 'FULL';

export interface CollectDispatchRequest {
	collected_by_shift_id: number;
	payment_method: string;
	collected_amount: number;
	change_amount: number;
	reference_code?: string;
}

export interface CollectDispatchResponse {
	order_id: string;
	status: 'COLLECTED';
	collected_by_shift_id: number;
	collected_by_name: string;
	payment_method: string;
	collected_amount: number;
	change_amount: number;
}

export interface AuthorizeData {
	order_id: string;
	dispenser_id: number;
	hose_id: number;
	side: 'A' | 'B';
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	payment_method: string;
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
	fusionPumpId: number;
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

export type CashMovementType = 'INCOME' | 'EXPENSE' | 'TRANSFER_IN' | 'TRANSFER_OUT' | 'SAFE_DROP';

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
	type: 'INCOME' | 'EXPENSE';
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
