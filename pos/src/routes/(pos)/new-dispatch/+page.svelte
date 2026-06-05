<script lang="ts">
	import { goto } from '$app/navigation';
	import { get } from 'svelte/store';
	import { page } from '$app/stores';
	import { config } from '$lib/stores/config';
	import Header from '$lib/components/Header.svelte';
	import PlateInput from '$lib/components/PlateInput.svelte';
	import BillingConfirmation from '$lib/components/BillingConfirmation.svelte';
	import CustomerForm from '$lib/components/CustomerForm.svelte';
	import AmountInput from '$lib/components/AmountInput.svelte';
	import type { VehicleResult, CustomerFormData, Customer, HoseConfig } from '$lib/api/types';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';
	import { auth } from '$lib/stores/auth';
	import { pendingOrders } from '$lib/stores/pendingOrders';

	let dispenserId = 0;
	let side: 'A' | 'B' = 'A';
	let selectedHoseId = 0;
	let selectedFusionHoseId = 0;
	let selectedFusionPumpId = 0;
	let selectedGradeId = '';
	let selectedGradeName = '';

	$: dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
	$: side = ($page.url.searchParams.get('side') ?? 'A') as 'A' | 'B';

	// Get hoses for the current side from config
	$: dispenserConfig = $config?.dispensers?.find(d => d.dispenser_id === dispenserId);
	$: sideHoses = (dispenserConfig?.sides?.[side] ?? []) as HoseConfig[];

	type Step = 'hose' | 'plate' | 'billing' | 'idLookup' | 'form';
	let currentStep: Step = 'hose';
	let showAmountSection = false;
	let vehicleResult: VehicleResult | null = null;
	let confirmedOwner: VehicleResult['owner'] = null;
	let billingCustomer: Customer | null = null;
	let plate = '';
	let amount = '';
	let loading = false;
	let error = '';
	let unitPrice = 1.500;
	let idLookupError = '';
	let idType: 'CED' | 'RUC' = 'CED';
	let idNumber = '';

	$: idValid = idType === 'CED' ? idNumber.length === 10 : idNumber.length === 13;

	function selectHose(hose: HoseConfig) {
		selectedHoseId = hose.hose_id;
		selectedFusionHoseId = hose.fusion_hose_id;
		selectedFusionPumpId = hose.fusion_pump_id;
		selectedGradeId = hose.grade_id;
		selectedGradeName = hose.grade_name;
		currentStep = 'plate';
	}

	function handleVehicleResult(result: VehicleResult) {
		vehicleResult = result;
		plate = result.plate;

		// Set price based on vehicle result
		unitPrice = result.price_list === 'VIP' ? 1.100 : 1.500;

		if (!result.vehicle_found) {
			currentStep = 'idLookup';
			idLookupError = '';
			idNumber = '';
		} else if (result.incomplete_fields.length > 0) {
			currentStep = 'form';
		} else {
			confirmedOwner = result.owner;
			currentStep = 'billing';
		}
	}

	function handleBillingConfirm() {
		if (vehicleResult?.owner) {
			confirmedOwner = vehicleResult.owner;
		}
		showAmountSection = true;
	}

	function handleBillingChange() {
		currentStep = 'idLookup';
		idLookupError = '';
		idNumber = '';
	}

	async function handleIdLookup() {
		if (!idValid) { idLookupError = idType === 'CED' ? 'La cédula debe tener 10 dígitos' : 'El RUC debe tener 13 dígitos'; return; }
		loading = true;
		idLookupError = '';
		try {
			const result = await powerfin.lookupPerson(get(auth).token || '', idType, idNumber);
			if (result.found && result.data) {
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
				unitPrice = result.data.price_list === 'VIP' ? 1.100 : 1.500;
				currentStep = 'billing';
			} else {
				vehicleResult = {
					vehicle_id: 0,
					plate: plate,
					vehicle_found: false,
					incomplete_fields: [],
					owner: null,
					billing_person: null,
					price_list: 'STANDARD',
					price_list_name: 'Precio Normal'
				};
				currentStep = 'form';
			}
		} catch {
			idLookupError = 'Error al buscar';
		} finally {
			loading = false;
		}
	}

	async function handleFormSubmit(formData: CustomerFormData) {
		loading = true;
		error = '';
		try {
			await powerfin.registerCustomer(get(auth).token || '', formData);
			plate = formData.plate;
			vehicleResult = {
				vehicle_id: 0,
				plate: formData.plate,
				vehicle_found: true,
				incomplete_fields: [],
				owner: {
					person_id: null,
					customer_id: formData.id_number,
					id_type: formData.id_type,
					id_number: formData.id_number,
					name: formData.name,
					address: null,
					email: formData.email,
					phone: null
				},
				billing_person: null,
				price_list: 'STANDARD',
				price_list_name: 'Precio Normal'
			};
			confirmedOwner = vehicleResult.owner;
			currentStep = 'billing';
		} catch {
			error = 'Error al registrar';
		} finally {
			loading = false;
		}
	}

	function handleFormCancel() {
		currentStep = 'plate';
		vehicleResult = null;
		plate = '';
	}

	async function handleAuthorize() {
		if (!amount || parseFloat(amount) <= 0) {
			error = 'Ingrese un monto válido';
			return;
		}

		loading = true;
		error = '';

		try {
			const dispatchOwner = billingCustomer ?? confirmedOwner ?? vehicleResult?.owner;

			const orderResult = await powerfin.createDispatch(get(auth).token || '', {
				dispenser_id: dispenserId,
				hose_id: selectedHoseId,
				side: side,
				preset_type: 'MONEY',
				preset_value: amount,
				unit_price: 3.103,
				payment_method: 'EFECTIVO',
				customer_id: dispatchOwner?.customer_id,
				plate: plate
			});

			const orderId = orderResult.order_id;

			await bridge.authorizeDispatch({
				order_id: orderId,
				dispenser_id: selectedFusionPumpId,
				hose_id: selectedFusionHoseId,
				side: side,
				preset_type: 'MONEY',
				preset_value: amount,
				payment_method: 'EFECTIVO',
				customer_id: dispatchOwner?.customer_id,
				plate: plate,
				unit_price: unitPrice,
				price_list: vehicleResult?.price_list ?? 'STANDARD'
			});

			pendingOrders.addOrder({
				orderId,
				dispenserId,
				fusionPumpId: selectedFusionPumpId,
				fusionHoseId: selectedFusionHoseId,
				hoseId: selectedHoseId,
				side: side,
				customerName: dispatchOwner?.name ?? '',
				plate,
				presetAmount: parseFloat(amount),
				finalAmount: 0,
				finalVolume: '0.00',
				unitPrice,
				priceList: vehicleResult?.price_list ?? 'STANDARD',
				status: 'FUELLING',
				createdAt: new Date().toISOString()
			});

			goto(`/fueling?order=${orderId}&dispenser=${dispenserId}&hose=${selectedHoseId}&side=${side}&amount=${amount}&price=${unitPrice}&customerName=${encodeURIComponent(dispatchOwner?.name ?? '')}&priceList=${vehicleResult?.price_list ?? 'STANDARD'}&plate=${encodeURIComponent(plate)}`);
		} catch {
			error = 'Error al autorizar el despacho';
		} finally {
			loading = false;
		}
	}
</script>

<Header title="Nueva Venta" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 overflow-y-auto">
	<!-- Dispenser + Side info -->
	<div class="card p-4 mb-4">
		<div class="flex items-center justify-between">
			<div>
				<div class="text-xs text-gray-400">Surtidor {dispenserId} — Lado {side}</div>
				{#if selectedHoseId > 0}
					<div class="text-lg font-bold text-gray-800">{selectedGradeName}</div>
				{/if}
			</div>
			<div class="text-right">
				<div class="text-xs text-gray-400">Precio</div>
				<div class="text-lg font-bold text-primary">${unitPrice.toFixed(3)}/L</div>
			</div>
		</div>
	</div>

	<!-- Step 1: Hose/grade selection -->
	{#if currentStep === 'hose'}
		<div class="card p-4 mb-4">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">
				Seleccione el combustible:
			</h3>
			{#if sideHoses.length === 0}
				<div class="text-center py-4 text-gray-400 text-sm">
					No hay mangueras configuradas para este lado
				</div>
			{:else if sideHoses.length === 1}
				<!-- Single hose: auto-select -->
				{@const hose = sideHoses[0]}
				<button
					class="touch-btn w-full p-4 rounded-xl bg-primary text-white font-semibold text-lg"
					on:click={() => selectHose(hose)}
				>
					{hose.grade_name}
				</button>
			{:else}
				<!-- Multiple hoses: let user pick -->
				<div class="grid gap-2">
					{#each sideHoses as hose (hose.hose_id)}
						<button
							class="touch-btn w-full p-4 rounded-xl border-2 border-gray-200 hover:border-primary
								text-left transition-colors"
							on:click={() => selectHose(hose)}
						>
							<div class="font-semibold text-gray-800">{hose.grade_name}</div>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Step 2: Plate input -->
	{#if currentStep === 'plate'}
		<div class="card p-4 mb-4">
			<PlateInput onResult={handleVehicleResult} />
		</div>
	{:else if currentStep === 'billing' && vehicleResult}
		<BillingConfirmation
			vehicle={vehicleResult}
			onConfirm={handleBillingConfirm}
			onChangeBilling={handleBillingChange}
		/>
	{:else if currentStep === 'idLookup'}
		<div class="card p-4">
			<div class="text-center mb-4">
				<div class="text-sm font-medium text-gray-700">
					{!vehicleResult?.vehicle_found ? 'Vehículo no encontrado' : 'Datos de facturación diferentes'}
				</div>
				<div class="text-xs text-gray-400 mt-1">
					{!vehicleResult?.vehicle_found
						? 'Ingrese la identificación para buscar en PowerFin'
						: 'Ingrese la identificación de la persona para la factura'}
				</div>
			</div>

			<div class="bg-gray-50 rounded-xl p-3 mb-4 text-center">
				<div class="text-xs text-gray-500">Placa</div>
				<div class="text-lg font-mono font-bold text-gray-700">{plate}</div>
			</div>

			<div class="mb-3">
				<label class="block text-xs text-gray-500 mb-1">Tipo de ID</label>
				<div class="flex gap-2">
					<button
						type="button"
						class="flex-1 py-2 rounded-lg text-sm font-medium transition-colors
						{idType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}"
						on:click={() => idType = 'CED'}
					>
						Cédula
					</button>
					<button
						type="button"
						class="flex-1 py-2 rounded-lg text-sm font-medium transition-colors
						{idType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}"
						on:click={() => idType = 'RUC'}
					>
						RUC
					</button>
				</div>
			</div>

			<div class="mb-4">
				<label for="id-lookup" class="block text-xs text-gray-500 mb-1">Número de identificación</label>
				<input
					id="id-lookup"
					type="text"
					inputmode="numeric"
					bind:value={idNumber}
					maxlength={idType === 'CED' ? 10 : 13}
					on:keydown={(e) => e.key === 'Enter' && handleIdLookup()}
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm
						focus:border-primary focus:outline-none"
					placeholder={idType === 'CED' ? '0912345678' : '1790012345001'}
				/>
			</div>

			{#if idLookupError}
				<div class="text-red-500 text-xs text-center mb-3">{idLookupError}</div>
			{/if}

			<div class="flex gap-3">
				<button
					class="touch-btn flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl py-3 font-medium"
					on:click={() => {
						currentStep = 'plate';
						vehicleResult = null;
						plate = '';
					}}
				>
					Volver
				</button>
				<button
					class="touch-btn flex-1 bg-primary hover:bg-primary/90 text-white rounded-xl py-3 font-bold disabled:opacity-50"
					on:click={handleIdLookup}
					disabled={loading || !idValid}
				>
					{loading ? 'Buscando...' : 'Buscar'}
				</button>
			</div>
		</div>
	{:else if currentStep === 'form'}
		<CustomerForm
			mode={vehicleResult?.vehicle_found ? 'incomplete' : 'registration'}
			{plate}
			initialIdType={idType}
			initialIdNumber={idNumber}
			onSubmit={handleFormSubmit}
			onCancel={handleFormCancel}
			{loading}
		/>
	{/if}

	<!-- Amount + Authorize (shown after billing confirmed or for unidentified plates) -->
	{#if showAmountSection || currentStep === 'plate'}
		{#if plate}
			<div class="card p-3 mb-4 bg-blue-50 border-blue-100 text-center">
				<div class="text-xs text-blue-500">Placa</div>
				<div class="text-lg font-mono font-bold text-blue-700">{plate}</div>
			</div>
		{/if}

		<div class="card p-4 mb-4">
			<AmountInput onAmount={(a) => amount = a} disabled={loading} />
		</div>

		{#if amount}
			<div class="card p-4 mb-4 bg-primary/5 border-primary/20">
				<div class="flex justify-between text-sm">
					<span class="text-gray-600">Litros estimados:</span>
					<span class="font-semibold">{(parseFloat(amount) / unitPrice).toFixed(2)} L</span>
				</div>
				<div class="flex justify-between text-sm mt-1">
					<span class="text-gray-600">Precio unitario:</span>
					<span class="font-semibold">${unitPrice.toFixed(3)}</span>
				</div>
				<div class="flex justify-between text-sm mt-1">
					<span class="text-gray-600">Combustible:</span>
					<span class="font-semibold">{selectedGradeName}</span>
				</div>
				{#if vehicleResult}
					<div class="flex justify-between text-sm mt-1">
						<span class="text-gray-600">Lista:</span>
						<span class="font-semibold text-purple-600">{vehicleResult.price_list_name}</span>
					</div>
				{/if}
			</div>
		{/if}

		{#if error}
			<div class="bg-red-50 text-red-600 text-sm text-center rounded-xl py-3 mb-4">{error}</div>
		{/if}

		<button
			class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4
				text-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed"
			on:click={handleAuthorize}
			disabled={loading || !amount || !plate}
		>
			{loading ? 'Autorizando...' : 'Autorizar Despacho'}
		</button>
	{/if}
</main>
