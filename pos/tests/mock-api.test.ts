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

	it('fetchConfig returns dispenser configuration with sides', async () => {
		const { fetchConfig } = await import('$lib/api/powerfin.mock');
		const config = await fetchConfig('mock-token');
		expect(config.dispensers).toHaveLength(1);
		expect(config.dispensers[0].sides.A[0].grade_id).toBe('DIESEL');
		expect(config.dispensers[0].sides.B[0].grade_id).toBe('DIESEL');
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

	it('getCustomerPrice returns standard price', async () => {
		const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
		const price = await getCustomerPrice('token', '0912345678', 'DIESEL');
		expect(price.unit_price).toBe(3.103);
		expect(price.price_list).toBe('STANDARD');
	});

	it('getCustomerPrice returns standard price for unknown', async () => {
		const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
		const price = await getCustomerPrice('token', 'UNKNOWN', 'SUPER');
		expect(price.unit_price).toBe(3.103);
		expect(price.price_list).toBe('STANDARD');
	});

	it('openShift returns a valid shift without dispenser_ids', async () => {
		const { openShift } = await import('$lib/api/powerfin.mock');
		const shift = await openShift('token', {
			opening_cash: 50.00,
			notes: 'turno mañana'
		});
		expect(shift.status).toBe('OPEN');
		expect(shift.opening_cash).toBe(50.00);
		expect(shift.shift_id).toBeGreaterThan(0);
		// dispenser_ids no longer exists — any user can sell on any dispenser
	});

	it('closeShift returns summary', async () => {
		const { closeShift } = await import('$lib/api/powerfin.mock');
		const result = await closeShift('token', 45, { notes: '' });
		expect(result.total_sales).toBeGreaterThan(0);
		expect(result.surplus).toBe(0);
		expect(result.shortage).toBe(0);
		expect(result.cash_income_count).toBe(2);
	});

	it('lookupVehicle finds existing plate with complete data', async () => {
		const { lookupVehicle } = await import('$lib/api/powerfin.mock');
		const result = await lookupVehicle('token', 'ABC1234');
		expect(result.vehicle_found).toBe(true);
		expect(result.plate).toBe('ABC1234');
		expect(result.owner?.name).toContain('Pérez');
		expect(result.incomplete_fields).toHaveLength(0);
		expect(result.price_list).toBe('STANDARD');
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
	it('getDispensers returns 4 dispensers with sides', async () => {
		const { getDispensers } = await import('$lib/api/bridge.mock');
		const result = await getDispensers();
		expect(result.fusionConnected).toBe(true);
		expect(result.dispensers).toHaveLength(4);
		// Check side/hose structure — Surtidor 1 has 4 hoses per side
		const d1 = result.dispensers[0];
		expect(d1.sides.A).toHaveLength(4);
		expect(d1.sides.B).toHaveLength(4);
		expect(d1.sides.A[0].gradeId).toBe('SUPER');
		expect(d1.sides.B[0].gradeId).toBe('SUPER');
	});

	it('getDispenser returns single dispenser with hose states', async () => {
		const { getDispenser } = await import('$lib/api/bridge.mock');
		const d = await getDispenser(1);
		expect(d.dispenserId).toBe(1);
		expect(d.sides.A[0].status).toBe('IDLE');
		expect(d.sides.B[0].status).toBe('IDLE');
	});

	it('authorizeDispatch changes hose status to AUTHORIZED', async () => {
		const { authorizeDispatch, getDispenser } = await import('$lib/api/bridge.mock');
		const result = await authorizeDispatch({
			order_id: 'OV-001',
			dispenser_id: 1,
			hose_id: 1,
			side: 'A',
			preset_type: 'MONEY',
			preset_value: '50.00',
			payment_method_id: 1,
			unit_price: 1.500
		});
		expect(result.status).toBe('AUTHORIZED');

		// Verify hose state changed
		const d = await getDispenser(1);
		expect(d.sides.A[0].status).toBe('AUTHORIZED');
		expect(d.sides.A[0].presetAmount).toBe(50.00);
		// Other hoses should remain IDLE
		expect(d.sides.B[0].status).toBe('IDLE');
	});

	it('cancelDispenser resets hose to IDLE', async () => {
		const { cancelDispenser, getDispenser } = await import('$lib/api/bridge.mock');
		const result = await cancelDispenser(1, 1);
		expect(result).toBe(true);

		const d = await getDispenser(1);
		expect(d.sides.A[0].status).toBe('IDLE');
	});

	it('MockEventSource sends INIT and HOSE_STATUS events', async () => {
		const { MockEventSource } = await import('$lib/api/bridge.mock');
		const events: Array<{ event: string; data: Record<string, unknown> }> = [];

		await new Promise<void>((resolve) => {
			const es = new MockEventSource();
			es.addEventListener('INIT', (data) => {
				events.push({ event: 'INIT', data });
			});
			es.addEventListener('HOSE_STATUS', (data) => {
				events.push({ event: 'HOSE_STATUS', data });
				// We expect many HOSE_STATUS events; resolve after first few
				if (events.length >= 5) {
					es.close();
					resolve();
				}
			});
			// Timeout safety
			setTimeout(() => { es.close(); resolve(); }, 2000);
		});

		const initEvent = events.find(e => e.event === 'INIT');
		expect(initEvent).toBeDefined();
		expect(initEvent?.data.fusionConnected).toBe(true);

		const hoseEvents = events.filter(e => e.event === 'HOSE_STATUS');
		expect(hoseEvents.length).toBeGreaterThan(0);
		// First hose event should have dispenserId and hoseId
		expect(hoseEvents[0].data.dispenserId).toBeDefined();
		expect(hoseEvents[0].data.hoseId).toBeDefined();
	});
});
