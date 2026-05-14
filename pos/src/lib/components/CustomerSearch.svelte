<script lang="ts">
	import type { Customer } from '$lib/api/types';

	export let onSelect: (customer: Customer | null) => void;
	export let disabled = false;

	let query = '';
	let results: Customer[] = [];
	let searching = false;
	let selectedCustomer: Customer | null = null;
	let showResults = false;
	let debounceTimer: ReturnType<typeof setTimeout>;

	// Mock imports
	import * as powerfin from '$lib/api/powerfin';

	async function handleInput() {
		clearTimeout(debounceTimer);
		selectedCustomer = null;
		onSelect(null);

		if (query.length < 2) {
			results = [];
			showResults = false;
			return;
		}

		debounceTimer = setTimeout(async () => {
			searching = true;
			try {
				results = await powerfin.searchCustomers('mock-token', query);
				showResults = true;
			} catch {
				results = [];
			} finally {
				searching = false;
			}
		}, 300);
	}

	function selectCustomer(customer: Customer) {
		selectedCustomer = customer;
		query = customer.name;
		showResults = false;
		onSelect(customer);
	}

	function clearCustomer() {
		selectedCustomer = null;
		query = '';
		results = [];
		showResults = false;
		onSelect(null);
	}
</script>

<div class="relative">
	<label for="customer-search" class="block text-sm font-semibold text-gray-700 mb-1">
		Cliente
	</label>

	<div class="relative">
		<input
			id="customer-search"
			type="text"
			bind:value={query}
			on:input={handleInput}
			on:focus={() => results.length > 0 && (showResults = true)}
			on:blur={() => setTimeout(() => showResults = false, 200)}
			placeholder="Buscar placa, cédula o nombre..."
			class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm
				focus:border-primary focus:outline-none pr-10"
			{disabled}
		/>

		{#if searching}
			<div class="absolute right-3 top-1/2 -translate-y-1/2">
				<div class="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
			</div>
		{:else if selectedCustomer}
			<button
				class="touch-btn absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
				on:click={clearCustomer}
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		{/if}
	</div>

	<!-- Results dropdown -->
	{#if showResults && results.length > 0}
		<div class="absolute z-10 left-0 right-0 mt-1 bg-white rounded-xl border border-gray-200 shadow-lg max-h-48 overflow-y-auto">
			{#each results as customer}
				<button
					class="touch-btn w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
					on:click={() => selectCustomer(customer)}
				>
					<div class="text-sm font-medium text-gray-800">{customer.name}</div>
					<div class="text-xs text-gray-500 mt-0.5">
						{customer.id_type}: {customer.id_number}
						{#if customer.price_list !== 'STANDARD'}
							<span class="ml-2 px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 text-xxs">
								{customer.price_list}
							</span>
						{/if}
					</div>
					{#if customer.plates.length > 0}
						<div class="text-xxs text-gray-400 mt-0.5">
							{customer.plates.join(', ')}
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{/if}

	{#if query.length >= 2 && !searching && results.length === 0 && showResults}
		<div class="absolute z-10 left-0 right-0 mt-1 bg-white rounded-xl border border-gray-200 shadow-lg p-4 text-center text-sm text-gray-400">
			Sin resultados
		</div>
	{/if}

	<!-- Selected customer summary -->
	{#if selectedCustomer}
		<div class="mt-2 bg-purple-50 rounded-xl px-3 py-2 text-xs">
			<span class="text-purple-700 font-medium">{selectedCustomer.price_list_name}</span>
			{#if selectedCustomer.plates.length > 0}
				<span class="text-purple-500 ml-2">{selectedCustomer.plates[0]}</span>
			{/if}
		</div>
	{/if}
</div>
