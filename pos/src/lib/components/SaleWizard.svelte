<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { config } from '$lib/stores/config';
	import { shift } from '$lib/stores/shift';
	import { currentUser, auth } from '$lib/stores/auth';
	import { pendingOrders } from '$lib/stores/pendingOrders';
	import type { HoseConfig, VehicleResult, CustomerFormData, Customer, PresetType } from '$lib/api/types';
	import type { PendingOrder } from '$lib/stores/pendingOrders';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';

	const dispatch = createEventDispatcher();

	function token() { return get(auth).token || ''; }

	export let dispenserId: number;
	export let side: 'A' | 'B';
	export let mode: 'sale' | 'collect' = 'sale';
	export let collectOrder: PendingOrder | null = null;

	$: dispenserConfig = $config?.dispensers?.find(d => d.dispenser_id === dispenserId);
	$: sideHoses = (dispenserConfig?.sides?.[side] ?? []) as HoseConfig[];

	type Step =
		| 'plate' | 'product' | 'billing' | 'incomplete' | 'idLookup'
		| 'registration' | 'presetType' | 'presetValue' | 'authorizing'
		| 'summary' | 'payment' | 'printing' | 'done' | 'changeBilling';

	let step: Step = 'plate';
	let selectedHose: HoseConfig | null = null;
	let plate = '';
	let vehicleResult: VehicleResult | null = null;
	let confirmedOwner: VehicleResult['owner'] | Customer | null = null;
	let billingCustomer: Customer | null = null;
	let billingPersonId: number | null = null;  // person_id from lookupPerson, for saving preference
	let editingCustomer = false;
	let editName = '';
	let editEmail = '';
	let editPhone = '';
	let editAddress = '';
	let presetType: PresetType = 'MONEY';
	let presetValue = '';
	let unitPrice = 3.103;
	$: gradeUnit = $config?.grades?.find(g => g.grade_id === selectedHose?.grade_id)?.unit || 'GALONES';
	$: unitAbbr = gradeUnit === 'GALONES' ? 'gal' : 'L';
	let loading = false;
	let error = '';
	let idType: 'CED' | 'RUC' = 'CED';
	let idNumber = '';
	let idLookupError = '';
	let idLookupFrom: 'plate' | 'billing' = 'plate';  // track where we came from
	let idLookupMode: 'id' | 'name' = 'id';  // CED/RUC vs name search
	let nameSearchQuery = '';
	let nameSearchResults: Array<{ customer_id: string; person_id?: number | null; id_type: string; id_number: string; name: string; address?: string | null; email: string | null; phone: string | null; price_list: string; price_list_name: string; credit_active: boolean; credit_balance: number; plates: string[] }> = [];

	$: idValid = idType === 'CED' ? idNumber.length === 10 : idNumber.length === 13;

	// Collection state
	let paymentMethod = '';
	let receivedAmount = '';
	let confirmingPayment = false;
	let referenceCode = '';
	let confirmed = false;
	let printing = false;
	let hasPrinted = false;
	let printSent = false;  // set after successful print, triggers auto-redirect
	let printError = false;
	let receiptData: any = null;  // from collect response, DB-persisted
	let printPolicy: 'ALWAYS' | 'ASK' | 'NEVER' = 'ASK';
	let autoReturnTimer: ReturnType<typeof setTimeout> | null = null;

	// Change billing state (collect mode)
	let changeBillingIdType: 'CED' | 'RUC' = 'CED';
	let changeBillingIdNumber = '';
	let changeBillingLoading = false;
	let changeBillingError = '';
	let saveBillingPreferential = false;

	$: changeBillingValid = changeBillingIdType === 'CED' ? changeBillingIdNumber.length === 10 : changeBillingIdNumber.length === 13;

	// Form fields
	let incompleteEmail = '';
	let incompletePhone = '';
	let incompleteAddress = '';
	let regIdNumber = '';
	let regName = '';
	let regEmail = '';
	let regPhone = '';
	let regAddress = '';

	$: regValid = regIdNumber.length > 0 && regName.trim().length > 0 && regEmail.trim().length > 0;

	$: paymentMethods = $config?.payment_methods ?? [];
	$: selectedPaymentMethod = paymentMethods.find(m => m.code === paymentMethod);
	$: needsReference = selectedPaymentMethod?.requires_reference ?? false;
	$: canConfirmPayment = paymentMethod !== '' && (!needsReference || referenceCode.trim() !== '');

	$: finalAmount = collectOrder
		? (collectOrder.finalAmount || collectOrder.presetAmount)
		: 0;
	$: finalVolume = collectOrder
		? (parseFloat(collectOrder.finalVolume) > 0
			? collectOrder.finalVolume
			: (finalAmount / (collectOrder.unitPrice || 1.5)).toFixed(3))
		: '0';

	// Product selection — always shown, regardless of hose count.
	// User explicitly selects the hose before proceeding.

	$: if (mode === 'collect') {
		step = 'summary';
		loadPrintPolicy();
	}

	async function loadPrintPolicy() {
		try {
			// Use printer_policy from backend config (database).
			// Fallback to bridge.getPrintPolicy() for backward compat.
			const policy = $config?.printer_policy;
			if (policy) { printPolicy = policy as 'ALWAYS' | 'ASK' | 'NEVER'; return; }
			const result = await bridge.getPrintPolicy();
			printPolicy = result.policy as 'ALWAYS' | 'ASK' | 'NEVER';
		} catch { /* */ }
	}

	function submitIncomplete() { if (vehicleResult?.owner) { handleIncompleteSubmit({ id_type: vehicleResult.owner.id_type as "CED" | "RUC", id_number: vehicleResult.owner.id_number, name: vehicleResult.owner.name, email: incompleteEmail || vehicleResult.owner.email || '', phone: incompletePhone, address: incompleteAddress, plate }); } }
	function submitRegistration() { if (!regValid) return; handleRegistrationSubmit({ id_type: idType, id_number: regIdNumber, name: regName.trim(), email: regEmail.trim(), phone: regPhone.trim(), address: regAddress.trim(), plate }); }

	async function selectHose(hose: HoseConfig) {
		selectedHose = hose;
		step = 'presetType';  // billing already done, go to preset

		let price = hose.unit_price || 3.103;
		const owner = billingCustomer ?? confirmedOwner ?? vehicleResult?.billing_person ?? vehicleResult?.owner;
		const priceList = vehicleResult?.price_list ?? billingCustomer?.price_list ?? 'STANDARD';
		const customerId = owner?.customer_id ?? owner?.id_number;
		if (hose.grade_id && customerId && priceList !== 'STANDARD') {
			try {
				const priceInfo = await powerfin.getCustomerPrice(token(), customerId, hose.grade_id, vehicleResult?.plate);
				if (priceInfo.unit_price > 0) price = priceInfo.unit_price;
			} catch { /* keep hose default */ }
		}
		unitPrice = price;
	}

	async function handlePlateSearch() {
		if (plate.length < 3) return;
		loading = true; error = '';
		try {
			const result = await powerfin.lookupVehicle(token(), plate);
			vehicleResult = result; plate = result.plate;
			billingCustomer = null;  // Reset billing override on new plate search
			if (!result.vehicle_found) { step = 'idLookup'; idLookupError = ''; idNumber = ''; idLookupFrom = 'plate'; }
			else if (result.incomplete_fields.length > 0) { step = 'incomplete'; }
			else { confirmedOwner = result.owner; step = 'billing'; }
		} catch { error = 'Error al buscar placa'; }
		finally { loading = false; }
	}

	function handleBillingConfirm() {
		// Prefer billing_person (persistent) over owner, unless billingCustomer is set (manual override)
		const owner = billingCustomer ?? (vehicleResult?.billing_person ?? confirmedOwner ?? vehicleResult?.owner);
		if (owner) confirmedOwner = owner;

		// Save as preferential billing person if checkbox is checked
		if (saveBillingPreferential && billingPersonId && vehicleResult?.vehicle_id) {
			powerfin.setVehicleBillingPerson(token(), vehicleResult.vehicle_id, billingPersonId)
				.catch(() => {});  // fire-and-forget, non-blocking
		}

		step = 'product';  // confirm customer, now select product
	}
	function handleBillingChange() { step = 'idLookup'; idLookupError = ''; idNumber = ''; idLookupFrom = 'billing'; saveBillingPreferential = false; }

	async function handleIncompleteSubmit(formData: CustomerFormData) {
		loading = true;
		try {
			await powerfin.registerCustomer(token(), formData);
			if (vehicleResult) { vehicleResult.incomplete_fields = []; if (vehicleResult.owner) vehicleResult.owner.email = formData.email; confirmedOwner = vehicleResult.owner; }
			step = 'billing';
		} catch { error = 'Error al actualizar datos'; }
		finally { loading = false; }
	}
	function handleIncompleteCancel() { step = 'plate'; vehicleResult = null; billingCustomer = null; plate = ''; }

	async function handleIdLookup() {
		if (!idValid) { idLookupError = idType === 'CED' ? 'La cédula debe tener 10 dígitos' : 'El RUC debe tener 13 dígitos'; return; }
		loading = true; idLookupError = '';
		try {
			const result = await powerfin.lookupPerson(token(), idType, idNumber);
			if (result.found && result.data) {
				billingPersonId = result.data.person_id ?? null;
				billingCustomer = {
					person_id: result.data.person_id,
					customer_id: result.data.id_number,
					id_type: result.data.id_type,
					id_number: result.data.id_number,
					name: result.data.name,
					email: result.data.email,
					phone: result.data.phone,
					price_list: result.data.price_list,
					price_list_name: result.data.price_list_name,
					credit_active: false,
					credit_balance: 0,
					plates: result.data.plates
				};
				step = 'billing';
			} else {
				regIdNumber = idNumber;
				regName = '';
				regEmail = '';
				regPhone = '';
				regAddress = '';
				step = 'registration';
			}
		} catch { idLookupError = 'Error al buscar'; }
		finally { loading = false; }
	}

	async function handleNameSearch() {
		const q = nameSearchQuery.trim();
		if (q.length < 2) { idLookupError = 'Ingrese al menos 2 caracteres'; return; }
		loading = true; idLookupError = ''; nameSearchResults = [];
		try {
			nameSearchResults = await powerfin.searchCustomers(token(), q);
			if (nameSearchResults.length === 0) idLookupError = 'No se encontraron resultados';
		} catch { idLookupError = 'Error al buscar'; }
		finally { loading = false; }
	}

	function selectNameResult(customer: { customer_id: string; person_id?: number | null; id_type: string; id_number: string; name: string; address?: string | null; email: string | null; phone: string | null; price_list: string; price_list_name: string; credit_active: boolean; credit_balance: number; plates: string[] }) {
		billingPersonId = customer.person_id ?? null;
		billingCustomer = { ...customer };
		step = 'billing';
	}
	function handleIdLookupBack() {
		if (idLookupFrom === 'billing') {
			step = 'billing';
		} else {
			step = 'plate'; vehicleResult = null; plate = '';
		}
		billingCustomer = null; billingPersonId = null; saveBillingPreferential = false;
	}

	async function handleRegistrationSubmit(formData: CustomerFormData) {
		loading = true; error = '';
		try {
			await powerfin.registerCustomer(token(), formData);
			plate = formData.plate;
			vehicleResult = { vehicle_id: 0, plate: formData.plate, vehicle_found: true, incomplete_fields: [], owner: { person_id: null, customer_id: formData.id_number, id_type: formData.id_type, id_number: formData.id_number, name: formData.name, address: formData.address || null, email: formData.email, phone: formData.phone || null }, billing_person: null, price_list: 'STANDARD', price_list_name: 'Precio Normal' };
			billingCustomer = { person_id: null, customer_id: formData.id_number, id_type: formData.id_type, id_number: formData.id_number, name: formData.name, address: formData.address || null, email: formData.email, phone: formData.phone || null, price_list: 'STANDARD', price_list_name: 'Precio Normal', credit_active: false, credit_balance: 0, plates: [formData.plate] };
			confirmedOwner = vehicleResult.owner; step = 'billing';
		} catch { error = 'Error al registrar'; }
		finally { loading = false; }
	}
	function handleRegistrationCancel() { regName = ''; regEmail = ''; regPhone = ''; regAddress = ''; step = 'idLookup'; }

	function handleProductBack() { step = 'billing'; }
	function handleBillingBack() { step = 'plate'; }
	function handlePresetTypeBack() { step = 'product'; }
	function handlePresetValueBack() { step = 'presetType'; }

	function startEditCustomer() {
		const p = billingCustomer ?? vehicleResult?.billing_person ?? vehicleResult?.owner;
		if (!p) return;
		editName = p.name;
		editEmail = p.email ?? '';
		editPhone = p.phone ?? '';
		editAddress = (p as any).address ?? '';
		editingCustomer = true;
	}

	async function saveEditCustomer() {
		const personId = billingPersonId ?? vehicleResult?.billing_person?.person_id ?? vehicleResult?.owner?.person_id;
		if (!personId) return;
		try {
			await powerfin.updatePerson(token(), personId, {
				name: editName || undefined,
				email: editEmail || undefined,
				phone: editPhone || undefined,
				address: editAddress || undefined
			});
			// Refresh displayed data
			if (billingCustomer) {
				billingCustomer.name = editName;
				billingCustomer.email = editEmail || null;
				billingCustomer.phone = editPhone || null;
			}
			if (vehicleResult?.owner && personId === vehicleResult.owner.person_id) {
				vehicleResult.owner.name = editName;
				vehicleResult.owner.email = editEmail || null;
				vehicleResult.owner.phone = editPhone || null;
			}
			if (vehicleResult?.billing_person && personId === vehicleResult.billing_person.person_id) {
				vehicleResult.billing_person.name = editName;
				vehicleResult.billing_person.email = editEmail || null;
				vehicleResult.billing_person.phone = editPhone || null;
			}
			editingCustomer = false;
		} catch { /* silently fail, non-critical */ }
	}

	function selectPresetType(type: PresetType) { presetType = type; presetValue = ''; step = 'presetValue'; }

	async function handleAuthorize() {
		const val = parseFloat(presetValue);
		if (presetType !== 'FULL' && (!val || val <= 0)) { error = presetType === 'MONEY' ? 'Ingrese un monto válido' : 'Ingrese galones válidos'; return; }
		loading = true; error = ''; step = 'authorizing';
		let orderId: string | null = null;  // tracked for rollback on partial failure
		try {
			const owner = billingCustomer ?? confirmedOwner ?? vehicleResult?.billing_person ?? vehicleResult?.owner;
			const hose = selectedHose!;
			const pl = vehicleResult?.price_list ?? billingCustomer?.price_list ?? 'STANDARD';
			const customerName = owner?.name || (plate ? 'Cliente ' + plate : 'Sin nombre');
			const orderResult = await powerfin.createDispatch(token(), { dispenser_id: dispenserId, hose_id: hose.hose_id, side, preset_type: presetType === 'FULL' ? 'VOLUME' : presetType, preset_value: presetType === 'FULL' ? 'FULL' : String(presetValue), unit_price: unitPrice, payment_method: 'EFECTIVO', customer_id: owner?.customer_id, plate });
			orderId = orderResult.order_id;
			await bridge.authorizeDispatch({ order_id: orderId, dispenser_id: hose.fusion_pump_id, hose_id: hose.fusion_hose_id, side, preset_type: presetType === 'FULL' ? 'VOLUME' : presetType, preset_value: presetType === 'FULL' ? 'FULL' : String(presetValue), payment_method: 'EFECTIVO', customer_id: owner?.customer_id, plate, unit_price: unitPrice, price_list: pl });
			const authorizedByUserId = $currentUser?.user_id;
			const authorizedBy = $currentUser?.name ?? '';
			pendingOrders.addOrder({
				orderId, dispenserId, fusionPumpId: hose.fusion_pump_id, fusionHoseId: hose.fusion_hose_id, hoseId: hose.hose_id, side,
				customerId: owner?.customer_id, customerName, plate,
				presetAmount: presetType === 'MONEY' ? val : presetType === 'FULL' ? 0 : (val * unitPrice),
				finalAmount: 0, finalVolume: '0.00', unitPrice, priceList: pl,
				status: 'FUELLING', createdAt: new Date().toISOString(),
				authorizedBy, authorizedByUserId
			});
			step = 'done';
			// Auto-redirect to dashboard after 1.5s so user sees live state transitions
			autoReturnTimer = setTimeout(() => {
				dispatch('done');
			}, 1500);
		} catch {
			// Rollback: if dispatch was created but preset failed, cancel the dispatch
			if (orderId) {
				try { await powerfin.cancelDispatch(token(), orderId); } catch { /* reconciliation will clean up */ }
			}
			error = 'Error al autorizar'; step = 'presetValue';
		}
		finally { loading = false; }
	}

	async function handleCollect() {
		if (!canConfirmPayment) { error = 'Seleccione una forma de pago'; return; }
		if (!collectOrder) { error = 'Orden no encontrada — regrese al inicio'; return; }
		confirmed = true;
		error = '';
		try {
			const shiftId = $shift?.shift_id ?? 0;
			const received = paymentMethod === 'EFECTIVO' ? (parseFloat(receivedAmount) || 0) : 0;
			const realChange = Math.max(0, received - finalAmount);
			const collectResult = await powerfin.collectDispatch(token(), collectOrder.orderId, { collected_by_shift_id: shiftId, payment_method: paymentMethod, collected_amount: finalAmount, change_amount: realChange, reference_code: referenceCode || undefined });
		// Store receipt data from backend (DB-persisted, same as reprint)
		receiptData = (collectResult as any)?.receipt_data ?? null;
			// Note: do NOT removeOrder here — it would nullify collectOrder reactively
			// and destroy the collect UI before the user sees the print/confirmation.
			// The order is removed in handleNewSale() when the user clicks "Nueva Venta".
			if (printPolicy === 'ALWAYS') await doPrint();
		} catch { error = 'Error al registrar cobro'; confirmed = false; }
	}

	async function doPrint() {
		printing = true;
		printError = false;
		try {
			// Use receipt_data from backend (DB-persisted, same as reprint) if available
			if (receiptData) {
				await bridge.printReceipt({
					type: 'FUEL_RECEIPT',
					printerIp: receiptData.printerIp || '',
					printerPort: receiptData.printerPort || 9100,
					dispenserId: receiptData.dispenserId || dispenserId,
					fuelData: {
						...receiptData.fuelData,
						date: new Date().toLocaleDateString('es-EC'),
						time: new Date().toLocaleTimeString('es-EC'),
					},
				});
			} else {
				// Fallback: build from wizard state (legacy, no DB data available yet)
				const printerIp = dispenserConfig?.printer_ip || '';
				const printerPort = dispenserConfig?.printer_port || 9100;
				const loc = $config?.location;
				const gradeUnit = $config?.grades?.find(g => g.grade_id === selectedHose?.grade_id)?.unit || 'GALONES';
				const owner = billingCustomer ?? confirmedOwner ?? vehicleResult?.billing_person ?? vehicleResult?.owner;
				const hoseId = collectOrder?.hoseId ?? selectedHose?.hose_id ?? 0;
				const gradeName = selectedHose?.grade_name || 'SUPER';
				await bridge.printReceipt({
					type: 'FUEL_RECEIPT', printerIp, printerPort, dispenserId,
					fuelData: {
						dispenserId, hoseId, orderId: collectOrder?.orderId ?? '',
						volume: finalVolume, amount: finalAmount.toFixed(2),
						unitPrice: Number(collectOrder?.unitPrice ?? selectedHose?.unit_price ?? 0).toFixed(7),
						paymentMethod, grade: gradeName,
						unit: gradeUnit === 'GALONES' ? 'GAL' : 'L',
						priceWithoutSubsidy: Number(selectedHose?.base_price ?? 0).toFixed(4),
						subsidyPerUnit: Number(selectedHose?.subsidy_per_unit ?? 0).toFixed(4),
						subsidyAmount: '',
						invoiceId: '',
						invoiceAuth: '',
						subtotal: finalAmount > 0 ? (finalAmount / 1.15).toFixed(2) : '0.00',
						taxLabel: 'IVA 15%',
						taxAmount: finalAmount > 0 ? (finalAmount - finalAmount / 1.15).toFixed(2) : '0.00',
						locationName: loc?.name ?? '',
						locationAddress: loc?.address ?? '',
						locationRuc: loc?.ruc ?? '',
						locationPhone: loc?.phone ?? '',
						locationCity: loc?.city ?? '',
						locationProvince: loc?.province ?? '',
						locationCountry: loc?.country ?? '',
						fiscalRegime: loc?.fiscal_regime ?? '',
						sriEnvironment: loc?.sri_environment ?? 0,
						emissionType: loc?.emission_type ?? 0,
						customerName: owner?.name ?? '',
						customerId: owner?.id_number ?? '',
						customerAddress: (owner as any)?.address ?? '',
						customerPhone: owner?.phone ?? '',
						customerEmail: owner?.email ?? '',
						plate: collectOrder?.plate ?? vehicleResult?.plate ?? '',
						date: new Date().toLocaleDateString('es-EC'),
						time: new Date().toLocaleTimeString('es-EC'),
						shiftId: String($shift?.shift_id ?? ''),
						cashierName: $shift?.user_name ?? '',
					}
				});
			}
			hasPrinted = true;
		// Auto-redirect to dashboard after 2.5s
		printSent = true;
		setTimeout(() => { if (printSent) handleNewSale(); }, 2500);
		} catch {
			printError = true;
		}
		finally { printing = false; }
	}

	function handleNewSale() { if (collectOrder) pendingOrders.removeOrder(collectOrder.orderId); receiptData = null; printSent = false; dispatch('done'); }
	function handleBackToDashboard() {
		if (confirmed && collectOrder) pendingOrders.removeOrder(collectOrder.orderId);
		dispatch('done');
	}

	/** Start a new sale keeping the current plate and vehicle data. */
	function handleNewSaleSamePlate() {
		if (autoReturnTimer) clearTimeout(autoReturnTimer);
		// Clear sale-specific state, keep plate + vehicle data
		selectedHose = null;
		billingCustomer = null;
		billingPersonId = null;
		saveBillingPreferential = false;
		confirmedOwner = vehicleResult?.owner ?? null;
		presetType = 'MONEY';
		presetValue = '';
		unitPrice = 3.103;
		error = '';
		step = 'billing';
	}

	// ── Change billing (collect mode) ──────────────────────
	function startChangeBilling() {
		changeBillingIdNumber = '';
		changeBillingError = '';
		step = 'changeBilling';
	}

	async function handleChangeBillingSearch() {
		if (!changeBillingValid) { changeBillingError = changeBillingIdType === 'CED' ? 'La cédula debe tener 10 dígitos' : 'El RUC debe tener 13 dígitos'; return; }
		changeBillingLoading = true;
		changeBillingError = '';
		try {
			const result = await powerfin.lookupPerson(token(), changeBillingIdType, changeBillingIdNumber);
			if (result.found && result.data) {
				await applyBillingChange(result.data.id_number, result.data.name);
			} else {
				changeBillingError = 'Cliente no encontrado';
			}
		} catch {
			changeBillingError = 'Error al buscar';
		} finally {
			changeBillingLoading = false;
		}
	}

	async function applyBillingChange(customerId: string | undefined, customerName: string) {
		if (!collectOrder) return;
		try {
			await powerfin.updateDispatchBilling(token(), collectOrder.orderId, {
				customer_id: customerId,
				customer_name: customerName
			});
		} catch {
			// PowerFin update failed — still update local state
		}
		pendingOrders.updateOrderBilling(collectOrder.orderId, customerName, collectOrder.plate, customerId);
		step = 'summary';
	}

	function cancelChangeBilling() {
		step = 'summary';
	}

	function setQuickAmount(val: number) { presetValue = String(val); }
	const moneyQuick = [5, 10, 20, 50, 100];
	const gallonQuick = [1, 2, 5, 10, 20];

	$: estimatedLiters = presetType === 'MONEY' && parseFloat(presetValue) > 0 ? (parseFloat(presetValue) / unitPrice).toFixed(2) : '';
	$: estimatedTotal = presetType === 'VOLUME' && parseFloat(presetValue) > 0 ? (parseFloat(presetValue) * unitPrice).toFixed(2) : '';
</script>

<div class="flex flex-col min-h-full">
	<div class="px-4 py-3 bg-white border-b border-gray-200 flex items-center gap-3">
		<button class="touch-btn text-gray-400 p-1" on:click={handleBackToDashboard}>←</button>
		<div>
			<div class="text-sm font-semibold text-gray-800">{mode === 'collect' ? 'Cobrar Venta' : 'Nueva Venta'}</div>
			<div class="text-xs text-gray-500">Surtidor {dispenserId} · Lado {side}</div>
		</div>
	</div>

	<main class="flex-1 px-4 py-4 overflow-y-auto">
		{#if !$shift}
			<div class="card p-6 text-center mt-8">
				<div class="text-3xl mb-3">🔒</div>
				<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
				<p class="text-sm text-gray-500">Debe abrir su turno para realizar ventas o cobros.</p>
			</div>
		{:else}
		{#if mode === 'sale'}
			<div class="flex items-center gap-1 mb-4 text-xs text-gray-400">
				<span class={step === 'plate' || step === 'idLookup' || step === 'registration' ? 'text-primary font-medium' : ''}>Placa</span><span>→</span>
				<span class={step === 'billing' || step === 'incomplete' ? 'text-primary font-medium' : ''}>Cliente</span><span>→</span>
				<span class={step === 'product' ? 'text-primary font-medium' : ''}>Producto</span><span>→</span>
				<span class={step === 'presetType' || step === 'presetValue' ? 'text-primary font-medium' : ''}>Monto</span><span>→</span>
				<span class={step === 'authorizing' || step === 'done' ? 'text-primary font-medium' : ''}>Autorizar</span>
			</div>

			{#if step === 'plate'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Placa del vehículo</h3>
					<div class="flex gap-2 mb-3">
						<input type="text" bind:value={plate} placeholder="ABC1234"
							class="flex-1 min-w-0 rounded-xl border border-gray-200 px-3 py-3 text-base uppercase focus:border-primary focus:outline-none"
							on:keydown={(e) => e.key === 'Enter' && handlePlateSearch()} />
						<button class="touch-btn bg-primary text-white rounded-xl px-6 py-3 font-semibold disabled:opacity-50"
							on:click={handlePlateSearch} disabled={plate.length < 3 || loading}>
							{loading ? '...' : 'Buscar'}
						</button>
					</div>
				</div>
			{/if}

			{#if step === 'product'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Seleccione el combustible:</h3>
					<div class="grid gap-2">
						{#each sideHoses as hose (hose.hose_id)}
							<button class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary text-left"
								on:click={() => selectHose(hose)}>
								<div class="font-semibold text-gray-800">Pistola {hose.hose_id} · ⛽ {hose.grade_name}</div>
								<div class="text-xs text-gray-500">${Number(hose.unit_price ?? 0).toFixed(3)}/{unitAbbr}</div>
							</button>
						{/each}
					</div>
					<button class="touch-btn w-full mt-3 bg-gray-100 text-gray-500 rounded-xl py-2 text-sm" on:click={handleProductBack}>← Volver</button>
				</div>
			{/if}

			{#if step === 'billing' && (vehicleResult || billingCustomer)}
				{@const effectiveOwner = billingCustomer ?? vehicleResult?.billing_person ?? vehicleResult?.owner}
				{@const isPreferential = !!vehicleResult?.billing_person && !billingCustomer}
				{#if editingCustomer}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">✏️ Editar datos del cliente</h3>
					<input type="text" bind:value={editName} placeholder="Nombre"
						class="w-full rounded-xl border border-gray-200 px-4 py-2 mb-2 text-sm focus:border-primary focus:outline-none" />
					<input type="email" bind:value={editEmail} placeholder="Correo electrónico"
						class="w-full rounded-xl border border-gray-200 px-4 py-2 mb-2 text-sm focus:border-primary focus:outline-none" />
					<input type="tel" bind:value={editPhone} placeholder="Teléfono"
						class="w-full rounded-xl border border-gray-200 px-4 py-2 mb-2 text-sm focus:border-primary focus:outline-none" />
					<input type="text" bind:value={editAddress} placeholder="Dirección"
						class="w-full rounded-xl border border-gray-200 px-4 py-2 mb-3 text-sm focus:border-primary focus:outline-none" />
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-2 text-sm" on:click={() => editingCustomer = false}>Cancelar</button>
						<button class="touch-btn bg-primary text-white rounded-xl py-2 text-sm font-semibold" on:click={saveEditCustomer}>Guardar</button>
					</div>
				</div>
				{:else}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">¿Facturar a este cliente?</h3>
					<div class="bg-green-50 rounded-xl p-4 mb-3">
						{#if isPreferential}
							<div class="text-xs text-amber-600 font-semibold mb-1">⭐ Facturación preferencial</div>
							<div class="text-xs text-gray-400 mb-2">Titular: {vehicleResult?.owner?.name}</div>
						{/if}
						<div class="font-semibold text-gray-800">{effectiveOwner?.name}</div>
						<div class="text-sm text-gray-500">{effectiveOwner?.id_type}: {effectiveOwner?.id_number}</div>
						{#if effectiveOwner?.email}
							<div class="text-sm text-gray-500">✉️ {effectiveOwner?.email}</div>
						{/if}
						{#if effectiveOwner?.phone}
							<div class="text-sm text-gray-500">📞 {effectiveOwner?.phone}</div>
						{/if}
						<div class="text-sm text-purple-600 font-medium mt-1">Lista: {vehicleResult?.price_list_name ?? billingCustomer?.price_list_name ?? 'STANDARD'}</div>
						<button class="touch-btn mt-2 w-full bg-gray-100 text-gray-500 rounded-xl py-1.5 text-xs" on:click={startEditCustomer}>✏️ Editar datos</button>
					</div>
					{#if billingCustomer && billingPersonId && vehicleResult?.vehicle_id}
						<label class="flex items-center gap-2 mb-3 p-2 bg-amber-50 rounded-xl cursor-pointer">
							<input type="checkbox" bind:checked={saveBillingPreferential} class="w-4 h-4 text-primary rounded" />
							<span class="text-xs text-amber-700">Guardar como facturación preferencial para este vehículo</span>
						</label>
					{/if}
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-500 rounded-xl py-3 font-medium" on:click={handleBillingBack}>← Volver</button>
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold" on:click={handleBillingConfirm}>✓ Correcto</button>
					</div>
					<div class="mt-2">
						<button class="touch-btn w-full bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleBillingChange}>Cambiar</button>
					</div>
				</div>
			{/if}
			{/if}

			{#if step === 'incomplete'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">⚠️ Datos faltantes</h3>
					<p class="text-sm text-gray-500 mb-3">Completa los datos del cliente. Falta: {vehicleResult?.incomplete_fields?.join(', ') || 'datos'}</p>
					{#if vehicleResult?.owner}
						<div class="bg-gray-50 rounded-xl p-3 mb-3 text-sm text-gray-600">{vehicleResult.owner.name} · {vehicleResult.owner.id_number}</div>
					{/if}
					{#if vehicleResult?.incomplete_fields?.includes('email')}
						<input type="email" bind:value={incompleteEmail} placeholder="Correo electrónico"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none" />
					{/if}
					{#if vehicleResult?.incomplete_fields?.includes('phone')}
						<input type="tel" bind:value={incompletePhone} placeholder="Teléfono"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none" />
					{/if}
					{#if vehicleResult?.incomplete_fields?.includes('address')}
						<input type="text" bind:value={incompleteAddress} placeholder="Dirección"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none" />
					{/if}
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50"
							on:click={submitIncomplete}
							disabled={loading}>{loading ? 'Guardando...' : 'Continuar'}</button>
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleIncompleteCancel}>Cancelar</button>
					</div>
				</div>
			{/if}

			{#if step === 'idLookup'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-1">{!vehicleResult?.vehicle_found ? '❌ Vehículo no encontrado' : 'Datos de facturación diferentes'}</h3>
					<p class="text-xs text-gray-400 mb-3">{!vehicleResult?.vehicle_found ? 'Busque al cliente por identificación o nombre' : 'Ingrese la identificación para la factura'}</p>
					{#if plate}
						<div class="bg-gray-50 rounded-xl p-3 mb-3 text-center"><span class="text-xs text-gray-500">Placa: </span><span class="font-mono font-bold text-gray-700">{plate}</span></div>
					{/if}

					<!-- Search mode tabs -->
					<div class="flex gap-2 mb-3">
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idLookupMode === 'id' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => { idLookupMode = 'id'; idLookupError = ''; }}>Por Cédula/RUC</button>
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idLookupMode === 'name' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => { idLookupMode = 'name'; idLookupError = ''; nameSearchQuery = ''; nameSearchResults = []; }}>Por Nombre</button>
					</div>

					{#if idLookupMode === 'id'}
						<!-- CED/RUC mode -->
						<div class="flex gap-2 mb-3">
							<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'CED'}>Cédula</button>
							<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'RUC'}>RUC</button>
						</div>
						<input type="text" inputmode="numeric" bind:value={idNumber} maxlength={idType === 'CED' ? 10 : 13}
							placeholder={idType === 'CED' ? '0912345678' : '1790012345001'}
							class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none"
							on:keydown={(e) => e.key === 'Enter' && handleIdLookup()} />
					{:else}
						<!-- Name search mode (local DB only) -->
						<div class="flex gap-2 mb-3">
							<input type="text" bind:value={nameSearchQuery} placeholder="Buscar por nombre..."
								class="flex-1 rounded-xl border border-gray-200 px-4 py-3 focus:border-primary focus:outline-none text-sm"
								on:keydown={(e) => e.key === 'Enter' && handleNameSearch()} />
							<button class="touch-btn bg-primary text-white rounded-xl px-4 py-3 font-semibold disabled:opacity-50" on:click={handleNameSearch} disabled={loading || nameSearchQuery.trim().length < 2}>
								{loading ? '...' : '🔍'}
							</button>
						</div>
						{#if nameSearchResults.length > 0}
							<div class="space-y-2 max-h-48 overflow-y-auto mb-3">
								{#each nameSearchResults as c}
									<button class="touch-btn w-full p-3 rounded-xl border border-gray-200 hover:border-primary text-left" on:click={() => selectNameResult(c)}>
										<div class="text-sm font-semibold text-gray-800">{c.name}</div>
										<div class="text-xs text-gray-500">{c.id_type}: {c.id_number}{#if c.plates.length > 0} · {c.plates[0]}{/if}</div>
									</button>
								{/each}
							</div>
						{/if}
					{/if}

					{#if idLookupError}<div class="text-red-500 text-xs text-center mb-3">{idLookupError}</div>{/if}

					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleIdLookupBack}>Volver</button>
						{#if idLookupMode === 'id'}
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50" on:click={handleIdLookup} disabled={loading || !idValid}>{loading ? 'Buscando...' : 'Buscar'}</button>
						{/if}
					</div>
				</div>
			{/if}

			{#if step === 'registration'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Registrar nuevo cliente</h3>
					<div class="flex gap-2 mb-3">
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'CED'}>Cédula</button>
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'RUC'}>RUC</button>
					</div>
					{#if plate}<div class="bg-gray-50 rounded-xl p-3 mb-3 text-center"><span class="text-xs text-gray-500">Placa: </span><span class="font-mono font-bold text-gray-700">{plate}</span></div>{/if}
					<input type="text" bind:value={regIdNumber} placeholder="Número de identificación" readonly class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 bg-gray-50 text-gray-600 focus:outline-none text-sm" />
					<input type="text" bind:value={regName} placeholder="Nombre completo *" required class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none text-sm" />
					<input type="email" bind:value={regEmail} placeholder="Correo electrónico *" required class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none text-sm" />
					<input type="tel" bind:value={regPhone} placeholder="Teléfono" class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none text-sm" />
					<input type="text" bind:value={regAddress} placeholder="Dirección" class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none text-sm" />
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleRegistrationCancel}>Cancelar</button>
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50"
							on:click={submitRegistration}
							disabled={loading || !regValid}>{loading ? 'Registrando...' : 'Continuar'}</button>
					</div>
				</div>
			{/if}

			{#if step === 'presetType'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">¿Cómo desea despachar?</h3>
					<div class="grid gap-2">
						<button class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary text-left" on:click={() => selectPresetType('MONEY')}>
							<div class="font-semibold text-gray-800">💵 Por Monto</div>
							<div class="text-xs text-gray-500">"Póngame $20 de {selectedHose?.grade_name}"</div>
						</button>
						<button class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary text-left" on:click={() => selectPresetType('VOLUME')}>
							<div class="font-semibold text-gray-800">⛽ Por Galones</div>
							<div class="text-xs text-gray-500">"Póngame 5 galones de {selectedHose?.grade_name}"</div>
						</button>
						<button class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary text-left" on:click={() => selectPresetType('FULL')}>
							<div class="font-semibold text-gray-800">🛢️ Llenar Tanque</div>
							<div class="text-xs text-gray-500">Sin límite, hasta que se llene</div>
						</button>
					</div>
					<button class="touch-btn w-full mt-2 bg-gray-100 text-gray-500 rounded-xl py-2 text-sm" on:click={handlePresetTypeBack}>← Volver</button>
				</div>
			{/if}

			{#if step === 'presetValue'}
				<div class="card p-4 mb-4">
					{#if presetType === 'MONEY'}
						<h3 class="text-sm font-semibold text-gray-700 mb-3">Monto a despachar</h3>
						<input type="number" bind:value={presetValue} placeholder="0.00" step="0.01" min="1"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 text-2xl text-center font-bold focus:border-primary focus:outline-none mb-3" />
						<div class="flex flex-wrap gap-2 mb-3">
							{#each moneyQuick as btn}
								<button class="touch-btn px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200" on:click={() => setQuickAmount(btn)}>${btn}</button>
							{/each}
						</div>
					{:else if presetType === 'VOLUME'}
						<h3 class="text-sm font-semibold text-gray-700 mb-3">Galones a despachar</h3>
						<input type="number" bind:value={presetValue} placeholder="0.00" step="0.01" min="0.1"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 text-2xl text-center font-bold focus:border-primary focus:outline-none mb-3" />
						<div class="flex flex-wrap gap-2 mb-3">
							{#each gallonQuick as btn}
								<button class="touch-btn px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200" on:click={() => setQuickAmount(btn)}>{btn} gal</button>
							{/each}
						</div>
					{:else}
						<h3 class="text-sm font-semibold text-gray-700 mb-3">Llenar tanque</h3>
						<p class="text-sm text-gray-500 mb-3">El despacho continuará hasta que el tanque esté lleno.</p>
					{/if}

					{#if error}<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{error}</div>{/if}

					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-500 rounded-xl py-3 font-medium" on:click={handlePresetValueBack}>← Volver</button>
						<button class="touch-btn bg-green-500 hover:bg-green-600 text-white rounded-xl py-3 text-lg font-bold disabled:opacity-50"
							on:click={handleAuthorize}
							disabled={loading || (presetType !== 'FULL' && (!presetValue || parseFloat(presetValue) <= 0))}>
							{loading ? 'Autorizando...' : 'Autorizar'}
						</button>
					</div>
				</div>
			{/if}

			{#if step === 'authorizing'}
				<div class="text-center py-10">
					<div class="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
					<p class="text-gray-500">Autorizando despacho...</p>
				</div>
			{/if}

			{#if step === 'done'}
				<div class="text-center py-8">
					<div class="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4"><span class="text-3xl">✅</span></div>
					<h3 class="text-lg font-semibold text-gray-800 mb-1">Despacho Autorizado</h3>
					<p class="text-sm text-gray-500 mb-4">El cliente puede cargar combustible.</p>
					<button class="touch-btn w-full bg-gray-100 text-gray-700 rounded-xl py-4 font-medium" on:click={handleBackToDashboard}>Volver al Inicio</button>
				</div>
			{/if}
		{/if}

		<!-- COLLECT MODE -->
		{#if mode === 'collect' && collectOrder}
			{#if step === 'summary'}
				<div class="text-center mb-6">
					<div class="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3"><span class="text-3xl">✅</span></div>
					<h3 class="text-lg font-semibold text-gray-800">Despacho Completado</h3>
					<p class="text-sm text-gray-500">#{collectOrder.orderId}</p>
				</div>
				<div class="card p-4 mb-4">
					<div class="space-y-2">
						<div class="flex justify-between text-sm"><span class="text-gray-500">Volumen</span><span class="font-medium">{finalVolume} {unitAbbr}</span></div>
						<div class="flex justify-between text-sm"><span class="text-gray-500">Precio</span><span class="font-medium">${Number(collectOrder.unitPrice ?? 0).toFixed(3)}/{unitAbbr}</span></div>
						{#if collectOrder.customerName}<div class="flex justify-between text-sm"><span class="text-gray-500">Cliente</span><span class="font-medium">{collectOrder.customerName}</span></div>{/if}
						{#if collectOrder.plate}<div class="flex justify-between text-sm"><span class="text-gray-500">Placa</span><span class="font-medium font-mono">{collectOrder.plate}</span></div>{/if}
						<hr class="border-gray-100" />
						<div class="flex justify-between text-lg font-bold"><span>TOTAL</span><span class="text-primary">${finalAmount.toFixed(2)}</span></div>
					</div>
				</div>
				<button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" on:click={() => step = 'payment'}>Cobrar Venta</button>
				<button class="touch-btn w-full mt-2 py-2 text-sm text-gray-400 hover:text-gray-600" on:click={startChangeBilling}>
					Cambiar facturación →
				</button>
			{/if}

			{#if step === 'changeBilling'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-1">Cambiar facturación</h3>
					<p class="text-xs text-gray-400 mb-3">La placa <span class="font-mono font-semibold">{collectOrder.plate || 'sin placa'}</span> no cambia. Busque a quién facturar por cédula o RUC.</p>
					<div class="flex gap-2 mb-3">
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {changeBillingIdType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => changeBillingIdType = 'CED'}>Cédula</button>
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {changeBillingIdType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => changeBillingIdType = 'RUC'}>RUC</button>
					</div>
					<div class="flex gap-2 mb-3">
						<input type="text" inputmode="numeric" bind:value={changeBillingIdNumber} maxlength={changeBillingIdType === 'CED' ? 10 : 13}
							placeholder={changeBillingIdType === 'CED' ? '0912345678' : '1790012345001'}
							class="flex-1 rounded-xl border border-gray-200 px-4 py-3 focus:border-primary focus:outline-none"
							on:keydown={(e) => e.key === 'Enter' && handleChangeBillingSearch()} />
						<button class="touch-btn bg-primary text-white rounded-xl px-6 py-3 font-semibold disabled:opacity-50"
							on:click={handleChangeBillingSearch} disabled={!changeBillingValid || changeBillingLoading}>
							{changeBillingLoading ? '...' : 'Buscar'}
						</button>
					</div>
					{#if changeBillingError}
						<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{changeBillingError}</div>
					{/if}
					<div class="mt-3">
						<button class="touch-btn w-full bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={cancelChangeBilling}>
							Cancelar
						</button>
					</div>
				</div>
			{/if}

			{#if step === 'payment' && !confirmed}
				{@const received = parseFloat(receivedAmount) || 0}
				{@const realChange = Math.max(0, received - finalAmount)}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Forma de pago</h3>
					<div class="grid grid-cols-2 gap-2 mb-3">
						{#each paymentMethods as method}
							<button class="touch-btn py-3 rounded-xl border-2 text-sm font-medium transition-colors {paymentMethod === method.code ? 'border-primary bg-primary/5 text-primary' : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
								on:click={() => { paymentMethod = method.code; referenceCode = ''; }}>{method.name}</button>
						{/each}
					</div>
					{#if needsReference}
						<input type="text" bind:value={referenceCode} placeholder="Nro. de transacción / voucher" class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm mb-3 focus:border-primary focus:outline-none" />
					{/if}
					<div class="bg-gray-50 rounded-xl p-3 mb-3">
						<div class="flex justify-between text-sm mb-2"><span class="text-gray-500">Total a cobrar</span><span class="font-bold">${finalAmount.toFixed(2)}</span></div>
						{#if paymentMethod === 'EFECTIVO'}
							<div class="flex items-center gap-2">
								<span class="text-sm text-gray-500">Recibido</span>
								<span class="text-lg">$</span>
								<input type="number" bind:value={receivedAmount} placeholder="0.00" step="0.01" min="0"
									class="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-right font-bold focus:border-primary focus:outline-none" />
							</div>
							{#if realChange > 0}
								<div class="flex justify-between text-sm mt-2 pt-2 border-t border-gray-200"><span class="text-green-600">Vuelto</span><span class="font-bold text-green-600">${realChange.toFixed(2)}</span></div>
							{/if}
						{/if}
					</div>
					{#if error}<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{error}</div>{/if}
					<button class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4 text-lg font-bold disabled:opacity-50"
						on:click={() => confirmingPayment = true} disabled={!canConfirmPayment || loading}>Confirmar — Cobrar ${finalAmount.toFixed(2)}</button>
				</div>
			{/if}

			{#if confirmingPayment}
				<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" on:click={() => confirmingPayment = false}>
					<div class="bg-white rounded-2xl p-6 m-4 max-w-sm w-full shadow-xl" on:click|stopPropagation>
						<h3 class="text-lg font-semibold text-gray-800 mb-2">¿Confirmar cobro?</h3>
						<div class="text-sm text-gray-500 mb-4">
							<div class="flex justify-between"><span>Total</span><span class="font-bold">${finalAmount.toFixed(2)}</span></div>
							<div class="flex justify-between"><span>Método</span><span>{selectedPaymentMethod?.name}</span></div>
							{#if paymentMethod === 'EFECTIVO' && parseFloat(receivedAmount) > 0}
								<div class="flex justify-between"><span>Recibido</span><span>${parseFloat(receivedAmount).toFixed(2)}</span></div>
								{#if Math.max(0, parseFloat(receivedAmount) - finalAmount) > 0}
									<div class="flex justify-between text-green-600"><span>Vuelto</span><span class="font-bold">${Math.max(0, parseFloat(receivedAmount) - finalAmount).toFixed(2)}</span></div>
								{/if}
							{/if}
						</div>
						<div class="grid grid-cols-2 gap-2">
							<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={() => confirmingPayment = false}>Cancelar</button>
							<button class="touch-btn bg-green-500 text-white rounded-xl py-3 font-semibold"
								on:click={() => { confirmingPayment = false; handleCollect(); }}>Sí, Cobrar</button>
						</div>
					</div>
				</div>
			{/if}

			{#if confirmed}
				<div class="card p-4 mb-4 bg-green-50 border-green-200">
					<div class="text-center text-green-700 font-semibold mb-1">✅ Cobrado</div>
					<div class="text-center text-green-600">{selectedPaymentMethod?.name} · ${finalAmount.toFixed(2)}</div>
					{#if referenceCode}<div class="text-xs text-green-500 text-center mt-1">Transacción: {referenceCode}</div>{/if}
				</div>

				{#if printPolicy === 'ASK' && !printing && !hasPrinted}
					<div class="card p-4 mb-4 text-center">
						<p class="text-gray-700 mb-3">¿El cliente desea ticket?</p>
						{#if printError}
							<div class="bg-red-50 text-red-600 text-sm rounded-lg py-2 mb-3">⚠️ Impresora no disponible</div>
						{/if}
						<div class="grid grid-cols-2 gap-2">
							<button class="touch-btn bg-blue-600 text-white rounded-xl py-3 font-semibold" on:click={doPrint}>🖨 SÍ</button>
							<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-medium" on:click={handleNewSale}>✗ NO</button>
						</div>
					</div>
				{:else if printing}
					<div class="text-center text-sm text-blue-600 py-4">🖨 Imprimiendo ticket...</div>
				{:else}
					{#if hasPrinted}
						<div class="card p-4 mb-4 bg-green-50 border-green-200 text-center">
							{#if printSent}
								<p class="text-green-700 font-semibold mb-1">✅ Impresión enviada</p>
								<p class="text-green-500 text-xs">Regresando al dashboard...</p>
							{/if}
							<div class="grid grid-cols-2 gap-2 mt-2">
								<button class="touch-btn bg-blue-600 text-white rounded-xl py-3 font-semibold" on:click={doPrint}>🖨 Reimprimir</button>
								<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-medium" on:click={handleNewSale}>Nueva Venta</button>
							</div>
						</div>
					{:else if printError}
						<div class="card p-4 mb-4 text-center">
							<div class="bg-red-50 text-red-600 text-sm rounded-lg py-2 mb-3">⚠️ Impresora no disponible</div>
							<div class="grid grid-cols-2 gap-2">
								<button class="touch-btn bg-blue-600 text-white rounded-xl py-3 font-semibold" on:click={doPrint}>🖨 Reintentar</button>
								<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-medium" on:click={handleNewSale}>Continuar sin ticket</button>
							</div>
						</div>
					{:else}
						<button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" on:click={handleNewSale}>Nueva Venta</button>
					{/if}
				{/if}
			{/if}
		{/if}
		{/if}
	</main>
</div>
