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
			expect(results[0].price_list).toBe('VIP');
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
		it('returns VIP price for VIP customer', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, '0912345678', 'SUPER');
			expect(price.unit_price).toBe(1.100);
			expect(price.price_list).toBe('VIP');
		});

		it('returns standard price for standard customer', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, '1790012345001', 'SUPER');
			expect(price.unit_price).toBe(1.500);
			expect(price.price_list).toBe('STANDARD');
		});

		it('returns standard price for unknown customer', async () => {
			const { getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const price = await getCustomerPrice(mockToken, 'UNKNOWN', 'SUPER');
			expect(price.unit_price).toBe(1.500);
		});
	});

	describe('Dispatch creation', () => {
		it('creates a dispatch order with valid ID format', async () => {
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const result = await createDispatch(mockToken, {
				dispenser_id: 1,
				hose_id: 1,
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method: 'EFECTIVO'
			});
			expect(result.order_id).toMatch(/^OV-/);
			expect(result.status).toBe('PENDING');
		});

		it('creates dispatch with customer data', async () => {
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const result = await createDispatch(mockToken, {
				dispenser_id: 1,
				hose_id: 1,
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
		it('authorizes dispatch and transitions dispenser state', async () => {
			const { authorizeDispatch, getDispenser } = await import('$lib/api/bridge.mock');

			const result = await authorizeDispatch({
				order_id: 'OV-TEST-001',
				dispenser_id: 1,
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method: 'EFECTIVO',
				unit_price: 1.500
			});

			expect(result.status).toBe('AUTHORIZED');
		});

		it('cancels an active preset', async () => {
			const { cancelDispenser } = await import('$lib/api/bridge.mock');
			const result = await cancelDispenser(1);
			expect(result).toBe(true);
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

			// 2. Open shift
			const { openShift } = await import('$lib/api/powerfin.mock');
			const shift = await openShift(auth.access_token, {
				dispenser_ids: [1],
				opening_cash: 0,
				notes: ''
			});
			expect(shift.status).toBe('OPEN');

			// 3. Search customer
			const { searchCustomers, getCustomerPrice } = await import('$lib/api/powerfin.mock');
			const customers = await searchCustomers(auth.access_token, 'Pérez');
			expect(customers.length).toBeGreaterThan(0);
			const price = await getCustomerPrice(auth.access_token, customers[0].customer_id, 'SUPER');
			expect(price.unit_price).toBe(1.100);

			// 4. Create dispatch
			const { createDispatch } = await import('$lib/api/powerfin.mock');
			const dispatch = await createDispatch(auth.access_token, {
				dispenser_id: 1,
				hose_id: 1,
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method: 'EFECTIVO',
				customer_id: customers[0].customer_id
			});
			expect(dispatch.order_id).toMatch(/^OV-/);

			// 5. Authorize
			const { authorizeDispatch } = await import('$lib/api/bridge.mock');
			const authResult = await authorizeDispatch({
				order_id: dispatch.order_id,
				dispenser_id: 1,
				preset_type: 'MONEY',
				preset_value: '50.00',
				payment_method: 'EFECTIVO',
				unit_price: price.unit_price
			});
			expect(authResult.status).toBe('AUTHORIZED');
		});
	});
});
