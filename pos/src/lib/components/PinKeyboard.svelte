<script lang="ts">
	export let onDigit: (digit: string) => void;
	export let onDelete: () => void;
	export let onEnter: () => void;
	export let loading = false;

	const digits = [
		['1', '2', '3'],
		['4', '5', '6'],
		['7', '8', '9'],
		['', '0', '⌫']
	];

	function handleClick(digit: string) {
		if (loading) return;
		if (digit === '⌫') onDelete();
		else if (digit !== '') onDigit(digit);
	}
</script>

<div class="grid grid-cols-3 gap-3">
	{#each digits as row}
		{#each row as digit}
			{#if digit === ''}
				<div></div>
			{:else}
				<button
					class="touch-btn bg-white/10 hover:bg-white/20 text-white rounded-2xl py-4
						text-2xl font-semibold border border-white/15
						{loading ? 'opacity-50' : ''}"
					on:click={() => handleClick(digit)}
					disabled={loading}
				>
					{digit}
				</button>
			{/if}
		{/each}
	{/each}
</div>

<div class="mt-4">
	<button
		class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-2xl py-4
			text-lg font-bold disabled:opacity-50"
		on:click={onEnter}
		disabled={loading}
	>
		{loading ? 'Ingresando...' : 'Ingresar'}
	</button>
</div>
