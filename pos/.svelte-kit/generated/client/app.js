export { matchers } from './matchers.js';

export const nodes = [
	() => import('./nodes/0'),
	() => import('./nodes/1'),
	() => import('./nodes/2'),
	() => import('./nodes/3'),
	() => import('./nodes/4'),
	() => import('./nodes/5'),
	() => import('./nodes/6'),
	() => import('./nodes/7'),
	() => import('./nodes/8'),
	() => import('./nodes/9'),
	() => import('./nodes/10'),
	() => import('./nodes/11'),
	() => import('./nodes/12'),
	() => import('./nodes/13'),
	() => import('./nodes/14'),
	() => import('./nodes/15')
];

export const server_loads = [];

export const dictionary = {
		"/(pos)": [3,[2]],
		"/(pos)/cash": [4,[2]],
		"/(pos)/cash/movement": [5,[2]],
		"/(pos)/cash/transfer": [6,[2]],
		"/(pos)/confirmation": [7,[2]],
		"/(pos)/fueling": [8,[2]],
		"/(pos)/history": [9,[2]],
		"/login": [13],
		"/(pos)/new-dispatch": [10,[2]],
		"/(pos)/sale": [11,[2]],
		"/shift/close": [14],
		"/shift/open": [15],
		"/(pos)/users": [12,[2]]
	};

export const hooks = {
	handleError: (({ error }) => { console.error(error) }),
	
	reroute: (() => {}),
	transport: {}
};

export const decoders = Object.fromEntries(Object.entries(hooks.transport).map(([k, v]) => [k, v.decode]));
export const encoders = Object.fromEntries(Object.entries(hooks.transport).map(([k, v]) => [k, v.encode]));

export const hash = false;

export const decode = (type, value) => decoders[type](value);

export { default as root } from '../root.svelte';