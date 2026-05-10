
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	type MatcherParam<M> = M extends (param : string) => param is (infer U extends string) ? U : string;

	export interface AppTypes {
		RouteId(): "/(pos)" | "/" | "/(pos)/confirmation" | "/(pos)/fueling" | "/(pos)/history" | "/login" | "/(pos)/new-dispatch" | "/shift" | "/shift/close" | "/shift/open";
		RouteParams(): {
			
		};
		LayoutParams(): {
			"/(pos)": Record<string, never>;
			"/": Record<string, never>;
			"/(pos)/confirmation": Record<string, never>;
			"/(pos)/fueling": Record<string, never>;
			"/(pos)/history": Record<string, never>;
			"/login": Record<string, never>;
			"/(pos)/new-dispatch": Record<string, never>;
			"/shift": Record<string, never>;
			"/shift/close": Record<string, never>;
			"/shift/open": Record<string, never>
		};
		Pathname(): "/" | "/login" | "/shift/open";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): string & {};
	}
}