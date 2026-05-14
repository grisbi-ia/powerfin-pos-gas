<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { config } from '$lib/stores/config';
	import { shift } from '$lib/stores/shift';
	import { pendingOrders } from '$lib/stores/pendingOrders';
	import type { HoseConfig, VehicleResult, CustomerFormData, Customer, PresetType } from '$lib/api/types';
	import type { PendingOrder } from '$lib/stores/pendingOrders';
	import * as powerfin from '$lib/api/powerfin.mock';
	import * as bridge from '$lib/api/bridge';

	const dispatch = createEventDispatcher();

	export let dispenserId: number;
	export let side: 'A' | 'B';
	export let mode: 'sale' | 'collect' = 'sale';
	export let collectOrder: PendingOrder | null = null;

	$: dispenserConfig = $config?.dispensers?.find(d => d.dispenser_id === dispenserId);
	$: sideHoses = (dispenserConfig?.sides?.[side] ?? []) as HoseConfig[];

	type Step =
		| 'hose' | 'plate' | 'billing' | 'incomplete' | 'idLookup'
		| 'registration' | 'presetType' | 'presetValue' | 'authorizing'
		| 'summary' | 'payment' | 'printing' | 'done';

	let step: Step = 'hose';
	let selectedHose: HoseConfig | null = null;
	let plate = '';
	let vehicleResult: VehicleResult | null = null;
	let confirmedOwner: VehicleResult['owner'] = null;
	let billingCustomer: Customer | null = null;
	let presetType: PresetType = 'MONEY';
	let presetValue = '';
	let unitPrice = 1.500;
	let loading = false;
	let error = '';
	let idType: 'CED' | 'RUC' = 'CED';
	let idNumber = '';
	let idLookupError = '';

	// Collection state
	let paymentMethod = '';
	let referenceCode = '';
	let confirmed = false;
	let printing = false;
	let printPolicy: 'ALWAYS' | 'ASK' | 'NEVER' = 'ASK';

	// Form fields
	let incompleteEmail = '';
	let regIdNumber = '';
	let regName = '';
	let regEmail = '';

	$: paymentMethods = $config?.payment_methods ?? [];
	$: selectedPaymentMethod = paymentMethods.find(m => m.code === paymentMethod);
	$: needsReference = selectedPaymentMethod?.requires_reference ?? false;
	$: canConfirmPayment = paymentMethod !== '' && (!needsReference || referenceCode.trim() !== '');

	$: finalAmount = collectOrder
		? (collectOrder.finalAmount || collectOrder.presetAmount * 0.85)
		: 0;
	$: finalVolume = collectOrder
		? (collectOrder.finalVolume || (finalAmount / (collectOrder.unitPrice || 1.5)).toFixed(3))
		: '0';
	$: changeAmount = Math.max(0, (collectOrder?.presetAmount ?? 0) - finalAmount);

	$: if (mode === 'sale' && sideHoses.length === 1) {
		selectedHose = sideHoses[0];
		unitPrice = 1.500;
		step = 'plate';
	}
	$: if (mode === 'collect') {
		step = 'summary';
		loadPrintPolicy();
	}

	async function loadPrintPolicy() {
		try { const result = await bridge.getPrintPolicy(); printPolicy = result.policy as 'ALWAYS' | 'ASK' | 'NEVER'; } catch { /* */ }
	}

	function submitIncomplete() { if (incompleteEmail && vehicleResult?.owner) { handleIncompleteSubmit({ id_type: vehicleResult.owner.id_type as "CED" | "RUC", id_number: vehicleResult.owner.id_number, name: vehicleResult.owner.name, email: incompleteEmail, plate }); } }
	function submitRegistration() { if (regIdNumber && regName && regEmail) { handleRegistrationSubmit({ id_type: idType, id_number: regIdNumber, name: regName, email: regEmail, plate }); } }

	function selectHose(hose: HoseConfig) { selectedHose = hose; unitPrice = 1.500; step = 'plate'; }

	async function handlePlateSearch() {
		if (plate.length < 3) return;
		loading = true; error = '';
		try {
			const result = await powerfin.lookupVehicle('token', plate);
			vehicleResult = result; plate = result.plate;
			if (!result.vehicle_found) { step = 'idLookup'; idLookupError = ''; idNumber = ''; }
			else if (result.incomplete_fields.length > 0) { step = 'incomplete'; }
			else { confirmedOwner = result.owner; unitPrice = result.price_list === 'VIP' ? 1.100 : 1.500; step = 'billing'; }
		} catch { error = 'Error al buscar placa'; }
		finally { loading = false; }
	}

	function handleSkipPlate() { vehicleResult = null; confirmedOwner = null; unitPrice = 1.500; step = 'presetType'; }
	function handleBillingConfirm() { if (vehicleResult?.owner) confirmedOwner = vehicleResult.owner; step = 'presetType'; }
	function handleBillingChange() { step = 'idLookup'; idLookupError = ''; idNumber = ''; }

	async function handleIncompleteSubmit(formData: CustomerFormData) {
		loading = true;
		try {
			await powerfin.registerCustomer('token', formData);
			if (vehicleResult) { vehicleResult.incomplete_fields = []; if (vehicleResult.owner) vehicleResult.owner.email = formData.email; confirmedOwner = vehicleResult.owner; }
			step = 'billing';
		} catch { error = 'Error al actualizar datos'; }
		finally { loading = false; }
	}
	function handleIncompleteCancel() { step = 'plate'; vehicleResult = null; plate = ''; }

	async function handleIdLookup() {
		if (idNumber.length < 5) return;
		loading = true; idLookupError = '';
		try {
			const customer = await powerfin.getCustomerById('token', idType, idNumber, true);
			if (customer) { billingCustomer = customer; unitPrice = customer.price_list === 'VIP' ? 1.100 : 1.500; step = 'billing'; }
			else { step = 'registration'; }
		} catch { idLookupError = 'Error al buscar'; }
		finally { loading = false; }
	}
	function handleIdLookupBack() { step = 'plate'; vehicleResult = null; plate = ''; }

	async function handleRegistrationSubmit(formData: CustomerFormData) {
		loading = true; error = '';
		try {
			await powerfin.registerCustomer('token', formData);
			plate = formData.plate;
			vehicleResult = { plate: formData.plate, vehicle_found: true, incomplete_fields: [], owner: { customer_id: formData.id_number, id_type: formData.id_type, id_number: formData.id_number, name: formData.name, email: formData.email, phone: null }, price_list: 'STANDARD', price_list_name: 'Precio Normal' };
			confirmedOwner = vehicleResult.owner; unitPrice = 1.500; step = 'billing';
		} catch { error = 'Error al registrar'; }
		finally { loading = false; }
	}
	function handleRegistrationCancel() { step = 'idLookup'; }

	function selectPresetType(type: PresetType) { presetType = type; presetValue = ''; step = 'presetValue'; }

	async function handleAuthorize() {
		const val = parseFloat(presetValue);
		if (presetType !== 'FULL' && (!val || val <= 0)) { error = presetType === 'MONEY' ? 'Ingrese un monto válido' : 'Ingrese galones válidos'; return; }
		loading = true; error = ''; step = 'authorizing';
		try {
			const owner = billingCustomer ?? confirmedOwner ?? vehicleResult?.owner;
			const hose = selectedHose!;
			const pl = vehicleResult?.price_list ?? 'STANDARD';
			const orderResult = await powerfin.createDispatch('token', { dispenser_id: dispenserId, hose_id: hose.hose_id, side, preset_type: presetType === 'FULL' ? 'VOLUME' : presetType, preset_value: presetType === 'FULL' ? 'FULL' : presetValue, payment_method: 'EFECTIVO', customer_id: owner?.customer_id, plate });
			await bridge.authorizeDispatch({ order_id: orderResult.order_id, dispenser_id: dispenserId, hose_id: hose.hose_id, side, preset_type: presetType === 'FULL' ? 'VOLUME' : presetType, preset_value: presetType === 'FULL' ? 'FULL' : presetValue, payment_method: 'EFECTIVO', customer_id: owner?.customer_id, plate, unit_price: unitPrice, price_list: pl });
			pendingOrders.addOrder({ orderId: orderResult.order_id, dispenserId, hoseId: hose.hose_id, side, customerName: owner?.name ?? '', plate, presetAmount: presetType === 'MONEY' ? val : (val * unitPrice), finalAmount: 0, finalVolume: '0.00', unitPrice, priceList: pl, status: 'FUELLING', createdAt: new Date().toISOString() });
			step = 'done';
		} catch { error = 'Error al autorizar'; step = 'presetValue'; }
		finally { loading = false; }
	}

	async function handleCollect() {
		if (!canConfirmPayment || !collectOrder) return;
		confirmed = true;
		try {
			const shiftId = $shift?.shift_id ?? 0;
			await powerfin.collectDispatch('token', collectOrder.orderId, { collected_by_shift_id: shiftId, payment_method: paymentMethod, collected_amount: finalAmount, change_amount: changeAmount, reference_code: referenceCode || undefined });
			if (printPolicy === 'ALWAYS') await doPrint();
		} catch { error = 'Error al registrar cobro'; confirmed = false; }
	}

	async function doPrint() {
		printing = true;
		try { await bridge.printReceipt({ type: 'FUEL_RECEIPT', dispenserId, fuelData: { dispenserId, orderId: collectOrder?.orderId ?? '', volume: finalVolume, amount: finalAmount.toFixed(2), unitPrice: (collectOrder?.unitPrice ?? 0).toFixed(3), paymentMethod, grade: 'SUPER' } }); }
		finally { printing = false; }
	}

	function handleNewSale() { if (collectOrder) pendingOrders.removeOrder(collectOrder.orderId); dispatch('done'); }
	function handleBackToDashboard() { dispatch('done'); }

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
		{#if mode === 'sale'}
			<div class="flex items-center gap-1 mb-4 text-xs text-gray-400">
				<span class={step === 'hose' ? 'text-primary font-medium' : ''}>Pistola</span><span>→</span>
				<span class={step === 'plate' || step === 'idLookup' || step === 'registration' ? 'text-primary font-medium' : ''}>Placa</span><span>→</span>
				<span class={step === 'billing' || step === 'incomplete' ? 'text-primary font-medium' : ''}>Cliente</span><span>→</span>
				<span class={step === 'presetType' || step === 'presetValue' ? 'text-primary font-medium' : ''}>Monto</span><span>→</span>
				<span class={step === 'authorizing' || step === 'done' ? 'text-primary font-medium' : ''}>Autorizar</span>
			</div>

			{#if step === 'hose'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Seleccione el combustible:</h3>
					<div class="grid gap-2">
						{#each sideHoses as hose (hose.hose_id)}
							<button class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary text-left"
								on:click={() => selectHose(hose)}>
								<div class="font-semibold text-gray-800">Pistola {hose.hose_id} · ⛽ {hose.grade_name}</div>
								<div class="text-xs text-gray-500">${unitPrice.toFixed(3)}/L</div>
							</button>
						{/each}
					</div>
				</div>
			{/if}

			{#if step === 'plate'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">Placa del vehículo</h3>
					<div class="bg-gray-50 rounded-xl p-3 mb-3 flex items-center gap-2">
						<span class="text-xs text-gray-500">⛽</span>
						<span class="text-sm font-medium">{selectedHose?.grade_name ?? ''}</span>
					</div>
					<div class="flex gap-2 mb-3">
						<input type="text" bind:value={plate} placeholder="ABC1234"
							class="flex-1 rounded-xl border border-gray-200 px-4 py-3 text-lg uppercase focus:border-primary focus:outline-none"
							on:keydown={(e) => e.key === 'Enter' && handlePlateSearch()} />
						<button class="touch-btn bg-primary text-white rounded-xl px-6 py-3 font-semibold disabled:opacity-50"
							on:click={handlePlateSearch} disabled={plate.length < 3 || loading}>
							{loading ? '...' : 'Buscar'}
						</button>
					</div>
					<button class="touch-btn w-full text-sm text-gray-400 py-2" on:click={handleSkipPlate}>
						Sin identificar (Consumidor Final)
					</button>
				</div>
			{/if}

			{#if step === 'billing' && (vehicleResult || billingCustomer)}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">¿Facturar al dueño del vehículo?</h3>
					<div class="bg-green-50 rounded-xl p-4 mb-3">
						<div class="font-semibold text-gray-800">{(billingCustomer ?? vehicleResult?.owner)?.name}</div>
						<div class="text-sm text-gray-500">{(billingCustomer ?? vehicleResult?.owner)?.id_type}: {(billingCustomer ?? vehicleResult?.owner)?.id_number}</div>
						<div class="text-sm text-purple-600 font-medium mt-1">{vehicleResult?.price_list_name ?? billingCustomer?.price_list_name ?? ''} · ${unitPrice.toFixed(3)}/L</div>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold" on:click={handleBillingConfirm}>✓ Correcto</button>
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleBillingChange}>Cambiar</button>
					</div>
				</div>
			{/if}

			{#if step === 'incomplete'}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-semibold text-gray-700 mb-3">⚠️ Datos faltantes</h3>
					<p class="text-sm text-gray-500 mb-3">El cliente no tiene email registrado. Es necesario para la factura.</p>
					{#if vehicleResult?.owner}
						<div class="bg-gray-50 rounded-xl p-3 mb-3 text-sm text-gray-600">{vehicleResult.owner.name} · {vehicleResult.owner.id_number}</div>
					{/if}
					<input type="email" bind:value={incompleteEmail} placeholder="Correo electrónico"
						class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none" />
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
					<p class="text-xs text-gray-400 mb-3">{!vehicleResult?.vehicle_found ? 'Ingrese la identificación para buscar en PowerFin' : 'Ingrese la identificación para la factura'}</p>
					{#if plate}
						<div class="bg-gray-50 rounded-xl p-3 mb-3 text-center"><span class="text-xs text-gray-500">Placa: </span><span class="font-mono font-bold text-gray-700">{plate}</span></div>
					{/if}
					<div class="flex gap-2 mb-3">
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'CED'}>Cédula</button>
						<button class="flex-1 py-2 rounded-lg text-sm font-medium {idType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}" on:click={() => idType = 'RUC'}>RUC</button>
					</div>
					<input type="text" bind:value={idNumber} placeholder={idType === 'CED' ? '0912345678' : '1790012345001'}
						class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none"
						on:keydown={(e) => e.key === 'Enter' && handleIdLookup()} />
					{#if idLookupError}<div class="text-red-500 text-xs text-center mb-3">{idLookupError}</div>{/if}
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleIdLookupBack}>Volver</button>
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50" on:click={handleIdLookup} disabled={loading || idNumber.length < 5}>{loading ? 'Buscando...' : 'Buscar'}</button>
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
					<input type="text" bind:value={regIdNumber} placeholder="Número de identificación" class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none text-sm" />
					<input type="text" bind:value={regName} placeholder="Nombre completo" class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-2 focus:border-primary focus:outline-none text-sm" />
					<input type="email" bind:value={regEmail} placeholder="Correo electrónico" class="w-full rounded-xl border border-gray-200 px-4 py-3 mb-3 focus:border-primary focus:outline-none text-sm" />
					<div class="grid grid-cols-2 gap-2">
						<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-3 font-medium" on:click={handleRegistrationCancel}>Cancelar</button>
						<button class="touch-btn bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50"
							on:click={submitRegistration}
							disabled={loading}>{loading ? 'Registrando...' : 'Continuar'}</button>
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
				</div>
			{/if}

			{#if step === 'presetValue'}
				<div class="card p-4 mb-4">
					{#if presetType === 'MONEY'}
						<h3 class="text-sm font-semibold text-gray-700 mb-1">Monto a despachar</h3>
						<div class="text-xs text-gray-500 mb-3">Precio: ${unitPrice.toFixed(3)}/L</div>
						<input type="number" bind:value={presetValue} placeholder="0.00" step="0.01" min="1"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 text-2xl text-center font-bold focus:border-primary focus:outline-none mb-3" />
						<div class="flex flex-wrap gap-2 mb-3">
							{#each moneyQuick as btn}
								<button class="touch-btn px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200" on:click={() => setQuickAmount(btn)}>${btn}</button>
							{/each}
						</div>
						{#if estimatedLiters}<div class="text-sm text-gray-500 text-center">≈ {estimatedLiters} litros</div>{/if}
					{:else if presetType === 'VOLUME'}
						<h3 class="text-sm font-semibold text-gray-700 mb-1">Galones a despachar</h3>
						<div class="text-xs text-gray-500 mb-3">Precio: ${unitPrice.toFixed(3)}/L</div>
						<input type="number" bind:value={presetValue} placeholder="0.00" step="0.01" min="0.1"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 text-2xl text-center font-bold focus:border-primary focus:outline-none mb-3" />
						<div class="flex flex-wrap gap-2 mb-3">
							{#each gallonQuick as btn}
								<button class="touch-btn px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200" on:click={() => setQuickAmount(btn)}>{btn} gal</button>
							{/each}
						</div>
						{#if estimatedTotal}<div class="text-sm text-gray-500 text-center">≈ ${estimatedTotal}</div>{/if}
					{:else}
						<h3 class="text-sm font-semibold text-gray-700 mb-3">Llenar tanque</h3>
						<p class="text-sm text-gray-500 mb-3">El despacho continuará hasta que el tanque esté lleno.</p>
					{/if}

					{#if error}<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{error}</div>{/if}

					<button class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4 text-lg font-bold disabled:opacity-50"
						on:click={handleAuthorize}
						disabled={loading || (presetType !== 'FULL' && (!presetValue || parseFloat(presetValue) <= 0))}>
						{loading ? 'Autorizando...' : 'Autorizar Despacho'}
					</button>
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
					<p class="text-sm text-gray-500 mb-4">El cliente puede cargar combustible.<br />Puede volver al inicio y atender otros surtidores.</p>
					<button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" on:click={handleBackToDashboard}>Volver al Inicio</button>
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
						<div class="flex justify-between text-sm"><span class="text-gray-500">Volumen</span><span class="font-medium">{finalVolume} L</span></div>
						<div class="flex justify-between text-sm"><span class="text-gray-500">Precio</span><span class="font-medium">${collectOrder.unitPrice.toFixed(3)}/L</span></div>
						{#if collectOrder.customerName}<div class="flex justify-between text-sm"><span class="text-gray-500">Cliente</span><span class="font-medium">{collectOrder.customerName}</span></div>{/if}
						{#if collectOrder.plate}<div class="flex justify-between text-sm"><span class="text-gray-500">Placa</span><span class="font-medium font-mono">{collectOrder.plate}</span></div>{/if}
						<hr class="border-gray-100" />
						<div class="flex justify-between text-lg font-bold"><span>TOTAL</span><span class="text-primary">${finalAmount.toFixed(2)}</span></div>
					</div>
				</div>
				{#if changeAmount > 0}
					<div class="card p-4 mb-4 bg-green-50 border-green-200">
						<div class="flex justify-between items-center"><span class="text-sm text-green-700">Vuelto</span><span class="text-xl font-bold text-green-700">${changeAmount.toFixed(2)}</span></div>
						<div class="text-xs text-green-600 mt-1">Preset: ${collectOrder.presetAmount.toFixed(2)} — Despachado: ${finalAmount.toFixed(2)}</div>
					</div>
				{/if}
				<button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" on:click={() => step = 'payment'}>Cobrar Venta</button>
			{/if}

			{#if step === 'payment' && !confirmed}
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
					{#if error}<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{error}</div>{/if}
					<button class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4 text-lg font-bold disabled:opacity-50"
						on:click={handleCollect} disabled={!canConfirmPayment || loading}>Confirmar — Cobrar ${finalAmount.toFixed(2)}</button>
				</div>
			{/if}

			{#if confirmed}
				<div class="card p-4 mb-4 bg-green-50 border-green-200">
					<div class="text-center text-green-700 font-semibold mb-1">✅ Cobrado</div>
					<div class="text-center text-green-600">{selectedPaymentMethod?.name} · ${finalAmount.toFixed(2)}</div>
					{#if referenceCode}<div class="text-xs text-green-500 text-center mt-1">Transacción: {referenceCode}</div>{/if}
				</div>

				{#if printPolicy === 'ASK' && !printing}
					<div class="card p-4 mb-4 text-center">
						<p class="text-gray-700 mb-3">¿El cliente desea ticket?</p>
						<div class="grid grid-cols-2 gap-2">
							<button class="touch-btn bg-blue-600 text-white rounded-xl py-3 font-semibold" on:click={doPrint}>🖨 SÍ</button>
							<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-medium" on:click={handleNewSale}>✗ NO</button>
						</div>
					</div>
				{:else if printing}
					<div class="text-center text-sm text-blue-600 py-4">🖨 Imprimiendo ticket...</div>
				{:else}
					<button class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold" on:click={handleNewSale}>Nueva Venta</button>
				{/if}
			{/if}
		{/if}
	</main>
</div>
