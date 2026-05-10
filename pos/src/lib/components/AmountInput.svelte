<script lang="ts">
	export let onAmount: (amount: string) => void;
	export let disabled = false;

	const quickAmounts = ['5', '10', '20', '50', '100'];
	let customAmount = '';
	let mode: 'quick' | 'custom' = 'quick';

	function selectQuick(amount: string) {
		customAmount = amount;
		onAmount(amount);
	}

	function handleCustomInput() {
		if (customAmount && parseFloat(customAmount) > 0) {
			onAmount(customAmount);
		}
	}
</script>

<div>
	<label class="block text-sm font-semibold text-gray-700 mb-2">
		Monto ($)
	</label>

	<!-- Quick amounts -->
	<div class="grid grid-cols-5 gap-2 mb-3">
		{#each quickAmounts as amount}
			<button
				class="touch-btn py-3 rounded-xl border-2 text-sm font-semibold transition-colors
					{customAmount === amount && mode === 'quick'
						? 'border-primary bg-primary/5 text-primary'
						: 'border-gray-200 text-gray-600 hover:border-gray-300'}"
				on:click={() => { mode = 'quick'; selectQuick(amount); }}
				{disabled}
			>
				${amount}
			</button>
		{/each}
	</div>

	<!-- Custom amount -->
	<div class="relative">
		<span class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-lg">$</span>
		<input
			type="number"
			bind:value={customAmount}
			on:focus={() => mode = 'custom'}
			on:input={handleCustomInput}
			step="0.01"
			min="0"
			placeholder="Otro monto"
			class="w-full rounded-xl border border-gray-200 pl-8 pr-4 py-3 text-lg
				focus:border-primary focus:outline-none"
			{disabled}
		/>
	</div>
</div>
