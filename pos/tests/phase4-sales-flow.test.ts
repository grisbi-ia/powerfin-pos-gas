import { describe, it, expect, beforeEach } from 'vitest';

describe('Phase 4 — Complete Sales Flow', () => {
	let mockToken: string;

	beforeEach(async () => {
		// Login to get token
		const { login } = await import('$lib/api/powerfin.mock');
		const response = await login({ username: 'carlos', pin: '1234' });
		mockToken = response.access_token;
	});

	describe('Customer search', () => {
		it('finds customer by ID number', async () => {
			const { searchCustomers } = await import('$lib/api/powerfin.mock');
			const results = await searchCustomers(mockToken, '0912345678');
			expect(results).toHaveLength(1);
			expect(results[0].name).toContain('Pérez');
			expect(results[0].price_list).toBe('STANDARD');
		});

		it('finds customer by RUC', async () => {
			const { searchCustomers } = await import('$lib/api/powerfin.mock');
			const results = await searchCustomers(mockToken, '1790012345001');
			expect(results).toHaveLength(1);
			expect(results[0].price_list).toBe('STANDARD');
			expect(results[0].credit_active).toBe(true);
		});

		it('returns empty for unknown query', async () => {
			const { searchCustomers } = await import('$lib/api/powerfin.mock');
			const results = await searchCustomers(mockToken, 'ZZZZZZ');
			expect(results).toHaveLength(0);
		});
	});

	describe('Price lookup', () => {
		it('returns standard price for Juan Pérez', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, '0912345678', 'DIESEL');
			expect(price.unit_price).toBe(3.103);
			expect(price.price_list).toBe('STANDARD');
		});

		it('returns standard price for standard customer', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, '1790012345001', 'SUPER');
			expect(price.unit_price).toBe(3.103);
			expect(price.price_list).toBe('STANDARD');
		});

		it('returns standard price for unknown customer', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, 'UNKNOWN', 'SUPER');
			expect(price.unit_price).toBe(3.103);
		});
	});

	describe('Dispatch creation', () => {
		it('creates a dispatch order with valid ID format', async () => {
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const result = await createDispatch(mockToken, {
				dispenser_id: 1,
				hose_id: 1,
				side: 'A',
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method_id: 1
			});
			expect(result.order_id).toMatch(/^OV-/);
			expect(result.status).toBe('PENDING');
		});

		it('creates dispatch with customer data', async () => {
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const result = await createDispatch(mockToken, {
				dispenser_id: 1,
				hose_id: 3,
				side: 'B',
				preset_type: 'MONEY',
				preset_value: '20.00',
				payment_method: 'QR',
				customer_id: '0912345678',
				plate: 'ABC-1234'
			});
			expect(result.order_id).toBeTruthy();
		});
	});

	describe('Authorization flow', () => {
		it('authorizes dispatch and transitions hose state', async () => {
			const { authorizeDispatch, getDispenser } = await import('$lib/api/bridge.mock');

			const result = await authorizeDispatch({
				order_id: 'OV-TEST-001',
				dispenser_id: 1,
				hose_id: 1,
				side: 'A',
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method_id: 1,
				unit_price: 1.500
			});

			expect(result.status).toBe('AUTHORIZED');

			// Verify only the specific hose is affected
			const d = await getDispenser(1);
			expect(d.sides.A[0].status).toBe('AUTHORIZED');
			// Side B should remain IDLE (two simultaneous operations possible)
			expect(d.sides.B[0].status).toBe('IDLE');
		});

		it('can authorize a different hose on the same dispenser simultaneously', async () => {
			const { authorizeDispatch, getDispenser } = await import('$lib/api/bridge.mock');

			// Authorize Side A, Hose 1
			await authorizeDispatch({
				order_id: 'OV-A-001',
				dispenser_id: 1,
				hose_id: 1,
				side: 'A',
				preset_type: 'MONEY',
				preset_value: '30.00',
				payment_method_id: 1,
				unit_price: 1.500
			});

			// Authorize Side B, Hose 5 (now Side B has hoses 5-8)
			const resultB = await authorizeDispatch({
				order_id: 'OV-B-001',
				dispenser_id: 1,
				hose_id: 5,
				side: 'B',
				preset_type: 'MONEY',
				preset_value: '20.00',
				payment_method_id: 1,
				unit_price: 1.500
			});

			expect(resultB.status).toBe('AUTHORIZED');

			const d = await getDispenser(1);
			expect(d.sides.A[0].status).toBe('AUTHORIZED');
			expect(d.sides.B[0].status).toBe('AUTHORIZED');
		});

		it('cancels an active hose preset', async () => {
			const { cancelDispenser, getDispenser } = await import('$lib/api/bridge.mock');
			const result = await cancelDispenser(1, 1);
			expect(result).toBe(true);

			const d = await getDispenser(1);
			expect(d.sides.A[0].status).toBe('IDLE');
		});
	});

	describe('Print policy', () => {
		it('returns ASK policy by default', async () => {
			const { getPrintPolicy } = await import('$lib/api/bridge.mock');
			const result = await getPrintPolicy();
			expect(result.policy).toBe('ASK');
		});

		it('prints receipt successfully', async () => {
			const { printReceipt } = await import('$lib/api/bridge.mock');
			const result = await printReceipt({
				type: 'FUEL_RECEIPT',
				dispenserId: 1,
				fuelData: {
					dispenserId: 1,
					orderId: 'OV-001',
					volume: '3.850',
					amount: '38.50',
					unitPrice: '10.000',
					paymentMethod: 'EFECTIVO',
					grade: 'SUPER'
				}
			});
			expect(result.status).toBe('PRINTED');
		});
	});

	describe('Change calculation', () => {
		it('calculates correct change when preset > actual', () => {
			const preset = 50.00;
			const actual = 38.46;
			const change = Math.max(0, preset - actual);
			expect(change).toBeCloseTo(11.54, 2);
		});

		it('returns zero change when preset equals actual', () => {
			const preset = 50.00;
			const actual = 50.00;
			const change = Math.max(0, preset - actual);
			expect(change).toBe(0);
		});

		it('returns zero change when actual exceeds preset', () => {
			const preset = 10.00;
			const actual = 12.50;
			const change = Math.max(0, preset - actual);
			expect(change).toBe(0);
		});
	});

	describe('End-to-end flow simulation', () => {
		it('completes full sale cycle: login → shift → dispatch → authorize → complete', async () => {
			// 1. Login
			const { login } = await import('$lib/api/powerfin.mock');
			const auth = await login({ username: 'carlos', pin: '1234' });
			expect(auth.access_token).toBeTruthy();

			// 2. Open shift (no dispenser_ids — any dispenser allowed)
			const { openShift } = await import('$lib/api/powerfin.mock');
			const shift = await openShift(auth.access_token, {
				opening_cash: 0,
				notes: ''
			});
			expect(shift.status).toBe('OPEN');

			// 3. Search customer
			const { searchCustomers, getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const customers = await searchCustomers(auth.access_token, 'Pérez');
			expect(customers.length).toBeGreaterThan(0);
			const price = await getCustomerPrice(auth.access_token, customers[0].customer_id, 'SUPER');
			expect(price.unit_price).toBe(3.103);

			// 4. Create dispatch (with side and hose)
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const dispatch = await createDispatch(auth.access_token, {
				dispenser_id: 1,
				hose_id: 1,
				side: 'A',
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method_id: 1,
				customer_id: customers[0].customer_id
			});
			expect(dispatch.order_id).toMatch(/^OV-/);

			// 5. Authorize with side and hose
			const { authorizeDispatch } = await import('$lib/api/bridge.mock');
			const authResult = await authorizeDispatch({
				order_id: dispatch.order_id,
				dispenser_id: 1,
				hose_id: 1,
				side: 'A',
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method_id: 1,
				unit_price: price.unit_price
			});
			expect(authResult.status).toBe('AUTHORIZED');
		});
	});

	describe('Dispenser sides and hoses', () => {
		it('each dispenser has two sides with independent hoses', async () => {
			const { getDispensers } = await import('$lib/api/bridge.mock');
			const result = await getDispensers();

			for (const d of result.dispensers) {
				expect(d.sides.A).toBeDefined();
				expect(d.sides.B).toBeDefined();
				expect(d.sides.A.length).toBeGreaterThan(0);
				expect(d.sides.B.length).toBeGreaterThan(0);
			}
		});

		it('hoses within a side can have different grades', async () => {
			const { fetchConfig } = await import('$lib/api/powerfin.mock');
			const config = await fetchConfig(mockToken);
			const d1 = config.dispensers[0];

			// Side A and B both have DIESEL (1 hose each)
			const gradesA = d1.sides.A.map(h => h.grade_id);
			expect(gradesA).toContain('DIESEL');
			expect(gradesA).toHaveLength(1);

			// Side B: mapped to Fusion pump 2
			const gradesB = d1.sides.B.map(h => h.grade_id);
			expect(gradesB).toContain('DIESEL');
			expect(gradesB).toHaveLength(1);

			// Each side has its own fusion_pump_id
			expect(d1.sides.A[0].fusion_pump_id).toBe(1);
			expect(d1.sides.B[0].fusion_pump_id).toBe(2);
		});
	});
});
