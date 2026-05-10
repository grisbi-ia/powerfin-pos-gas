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
	hoses: HoseConfig[];
}

export interface HoseConfig {
	hose_id: number;
	fusion_hose_id: number;
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
	dispenser_ids: number[];
}

export interface OpenShiftRequest {
	dispenser_ids: number[];
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
	grade: string;
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	unit_price: number;
	payment_method: string;
	customer_id?: string;
	customer_name?: string;
	plate?: string;
	status: 'PENDING' | 'AUTHORIZED' | 'FUELLING' | 'COMPLETED' | 'CANCELLED';
	created_at: string;
}

export interface CreateDispatchRequest {
	dispenser_id: number;
	hose_id: number;
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

export interface AuthorizeData {
	order_id: string;
	dispenser_id: number;
	preset_type: 'MONEY' | 'VOLUME';
	preset_value: string;
	payment_method: string;
	customer_id?: string;
	plate?: string;
	unit_price: number;
	price_list?: string;
}

export interface DispenserState {
	dispenserId: number;
	status: string;
	subStatus: string;
	presetAmount: number;
	grade?: string;
	hoseCount: number;
	connected: boolean;
	online: boolean;
}

export type PrintPolicy = 'ALWAYS' | 'ASK' | 'NEVER';

export interface SseEvent {
	event: string;
	data: Record<string, unknown>;
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
