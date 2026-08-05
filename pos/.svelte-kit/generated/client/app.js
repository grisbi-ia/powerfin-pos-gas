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
	() => import('./nodes/15'),
	() => import('./nodes/16'),
	() => import('./nodes/17')
];

export const server_loads = [];

export const dictionary = {
		"/(pos)": [3,[2]],
		"/(pos)/cash": [4,[2]],
		"/(pos)/cash/movement": [5,[2]],
		"/(pos)/cash/summary": [6,[2]],
		"/(pos)/cash/transfer": [7,[2]],
		"/(pos)/confirmation": [8,[2]],
		"/(pos)/fueling": [9,[2]],
		"/(pos)/history": [10,[2]],
		"/login": [14],
		"/(pos)/new-dispatch": [11,[2]],
		"/(pos)/sale": [12,[2]],
		"/shift/close": [15],
		"/shift/meters": [16],
		"/shift/open": [17],
		"/(pos)/users": [13,[2]]
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