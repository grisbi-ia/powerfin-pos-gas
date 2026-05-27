/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				primary: '#1E3A5F',
				'primary-light': '#2D5A8E',
				success: '#10B981',
				warning: '#F59E0B',
				danger: '#EF4444',
				'dispenser-idle': '#10B981',
				'dispenser-calling': '#F59E0B',
				'dispenser-fuelling': '#3B82F6',
				'dispenser-authorized': '#8B5CF6',
				'dispenser-error': '#EF4444',
				'dispenser-closed': '#9CA3AF'
			},
			fontSize: {
				'xxs': '0.625rem'
			}
		}
	},
	plugins: []
};
