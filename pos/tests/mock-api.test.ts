import { describe, it, expect } from 'vitest';

// Test that mock APIs return data matching the type contracts

describe('PowerFin Mock API', () => {
	it('login with correct PIN returns user', async () => {
		const { login } = await import('$lib/api/powerfin.mock');
		const response = await login({ username: 'carlos', pin: '1234' });
		expect(response.access_token).toBeTruthy();
		expect(response.user.name).toBe('carlos');
		expect(response.user.role).toBe('DISPATCHER');
	});

	it('login with wrong PIN throws error', async () => {
		const { login } = await import('$lib/api/powerfin.mock');
		await expect(login({ username: 'carlos', pin: '0000' })).rejects.toThrow('Credenciales inválidas');
	});

	it('fetchConfig returns dispenser configuration', async () => {
		const { fetchConfig } = await import('$lib/api/powerfin.mock');
		const config = await fetchConfig('mock-token');
		expect(config.dispensers).toHaveLength(2);
		expect(config.dispensers[0].hoses[0].grade_id).toBe('SUPER');
	});

	it('searchCustomers finds by name', async () => {
		const { searchCustomers } = await import('$lib/api/powerfin.mock');
		const results = await searchCustomers('token', 'Pérez');
		expect(results.length).toBeGreaterThan(0);
		expect(results[0].name).toContain('Pérez');
	});

	it('searchCustomers finds by plate', async () => {
		const { searchCustomers } = await import('$lib/api/powerfin.mock');
		const results = await searchCustomers('token', 'ABC-1234');
		expect(results.length).toBeGreaterThan(0);
		expect(results[0].plates).toContain('ABC-1234');
	});

	it('searchCustomers returns empty for no match', async () => {
		const { searchCustomers } = await import('$lib/api/powerfin.mock');
		const results = await searchCustomers('token', 'ZZZ-NOT-FOUND');
		expect(results).toHaveLength(0);
	});

	it('getCustomerPrice returns VIP price', async () => {
		const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
		const price = await getCustomerPrice('token', '0912345678', 'SUPER');
		expect(price.unit_price).toBe(1.100);
		expect(price.price_list).toBe('VIP');
	});

	it('getCustomerPrice returns standard price for unknown', async () => {
		const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
		const price = await getCustomerPrice('token', 'UNKNOWN', 'SUPER');
		expect(price.unit_price).toBe(1.500);
		expect(price.price_list).toBe('STANDARD');
	});

	it('openShift returns a valid shift', async () => {
		const { openShift } = await import('$lib/api/powerfin.mock');
		const shift = await openShift('token', {
			dispenser_ids: [1, 2],
			opening_cash: 0,
			notes: ''
		});
		expect(shift.status).toBe('OPEN');
		expect(shift.dispenser_ids).toContain(1);
	});

	it('closeShift returns summary', async () => {
		const { closeShift } = await import('$lib/api/powerfin.mock');
		const result = await closeShift('token', 45, { closing_cash: 890.50, notes: '' });
		expect(result.total_sales).toBeGreaterThan(0);
		expect(result.difference).toBe(0);
	});

	it('lookupVehicle finds existing plate with complete data', async () => {
		const { lookupVehicle } = await import('$lib/api/powerfin.mock');
		const result = await lookupVehicle('token', 'ABC1234');
		expect(result.vehicle_found).toBe(true);
		expect(result.plate).toBe('ABC1234');
		expect(result.owner?.name).toContain('Pérez');
		expect(result.incomplete_fields).toHaveLength(0);
		expect(result.price_list).toBe('VIP');
	});

	it('lookupVehicle returns incomplete fields when email missing', async () => {
		const { lookupVehicle } = await import('$lib/api/powerfin.mock');
		const result = await lookupVehicle('token', 'XYZ5678');
		expect(result.vehicle_found).toBe(true);
		expect(result.owner?.email).toBeNull();
		expect(result.incomplete_fields).toContain('email');
	});

	it('lookupVehicle returns not found for unknown plate', async () => {
		const { lookupVehicle } = await import('$lib/api/powerfin.mock');
		const result = await lookupVehicle('token', 'ZZZ-9999');
		expect(result.vehicle_found).toBe(false);
		expect(result.owner).toBeNull();
	});

	it('getCustomerById finds by CED', async () => {
		const { getCustomerById } = await import('$lib/api/powerfin.mock');
		const customer = await getCustomerById('token', 'CED', '0912345678');
		expect(customer).not.toBeNull();
		expect(customer?.name).toContain('Pérez');
	});

	it('getCustomerById finds by RUC', async () => {
		const { getCustomerById } = await import('$lib/api/powerfin.mock');
		const customer = await getCustomerById('token', 'RUC', '1790012345001');
		expect(customer).not.toBeNull();
		expect(customer?.name).toBe('Transportes Andinos S.A.');
	});

	it('getCustomerById returns null for unknown', async () => {
		const { getCustomerById } = await import('$lib/api/powerfin.mock');
		const customer = await getCustomerById('token', 'CED', '0000000000');
		expect(customer).toBeNull();
	});

	it('registerCustomer creates new customer and vehicle', async () => {
		const { registerCustomer, lookupVehicle } = await import('$lib/api/powerfin.mock');
		const result = await registerCustomer('token', {
			id_type: 'CED',
			id_number: '0102030405',
			name: 'Test User',
			email: 'test@example.com',
			plate: 'TEST001'
		});
		expect(result.customer_id).toBe('0102030405');
		expect(result.price_list).toBe('STANDARD');

		const vehicle = await lookupVehicle('token', 'TEST001');
		expect(vehicle.vehicle_found).toBe(true);
		expect(vehicle.owner?.name).toBe('Test User');
	});
});

describe('Bridge Mock API', () => {
	it('getDispensers returns all dispensers', async () => {
		const { getDispensers } = await import('$lib/api/bridge.mock');
		const result = await getDispensers();
		expect(result.fusionConnected).toBe(true);
		expect(result.dispensers).toHaveLength(4);
	});

	it('getDispenser returns single dispenser', async () => {
		const { getDispenser } = await import('$lib/api/bridge.mock');
		const d = await getDispenser(1);
		expect(d.dispenserId).toBe(1);
		expect(d.status).toBe('IDLE');
	});

	it('authorizeDispatch changes status to AUTHORIZED', async () => {
		const { authorizeDispatch } = await import('$lib/api/bridge.mock');
		const result = await authorizeDispatch({
			order_id: 'OV-001',
			dispenser_id: 1,
			preset_type: 'MONEY',
			preset_value: '50.00',
			payment_method: 'EFECTIVO',
			unit_price: 1.500
		});
		expect(result.status).toBe('AUTHORIZED');
	});

	it('cancelDispenser returns true', async () => {
		const { cancelDispenser } = await import('$lib/api/bridge.mock');
		const result = await cancelDispenser(1);
		expect(result).toBe(true);
	});

	it('MockEventSource sends INIT event', async () => {
		const { MockEventSource } = await import('$lib/api/bridge.mock');
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];

		await new Promise<void>((resolve) => {
			const es = new MockEventSource();
			es.addEventListener('INIT', (data) => {
				events.push({ event: 'INIT', data });
				if (events.length >= 2) {
					es.close();
					resolve();
				}
			});
			es.addEventListener('PUMP_STATUS_CHANGE', (data) => {
				events.push({ event: 'PUMP_STATUS_CHANGE', data });
				if (events.length >= 2) {
					es.close();
					resolve();
				}
			});
		});

		const initEvent = events.find(e => e.event === 'INIT');
		expect(initEvent).toBeDefined();
		expect(initEvent?.data.fusionConnected).toBe(true);
	});
});
