/** @type {import('tailwindcss').Config} */
module.exports = {
	darkMode: ['class'],
	content: [
		'./pages/**/*.{ts,tsx}',
		'./components/**/*.{ts,tsx}',
		'./app/**/*.{ts,tsx}',
		'./src/**/*.{ts,tsx}',
	],
	theme: {
		container: {
			center: true,
			padding: '2rem',
			screens: {
				'2xl': '1400px',
			},
		},
		extend: {
			colors: {
				border: 'hsl(var(--border))',
				input: 'hsl(var(--input))',
				ring: 'hsl(var(--ring))',
				background: 'hsl(var(--background))',
				foreground: 'hsl(var(--foreground))',
				primary: {
					DEFAULT: '#2B5D3A',
					foreground: 'hsl(var(--primary-foreground))',
				},
				secondary: {
					DEFAULT: '#4A90E2',
					foreground: 'hsl(var(--secondary-foreground))',
				},
				accent: {
					DEFAULT: '#F5A623',
					foreground: 'hsl(var(--accent-foreground))',
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive))',
					foreground: 'hsl(var(--destructive-foreground))',
				},
				muted: {
					DEFAULT: 'hsl(var(--muted))',
					foreground: 'hsl(var(--muted-foreground))',
				},
				popover: {
					DEFAULT: 'hsl(var(--popover))',
					foreground: 'hsl(var(--popover-foreground))',
				},
				card: {
					DEFAULT: 'hsl(var(--card))',
					foreground: 'hsl(var(--card-foreground))',
				},
				// 科技感暗色主题配色
				'cyber': {
					'bg': '#0a0e17',
					'surface': '#111827',
					'surface-light': '#1f2937',
					'border': '#374151',
					'text': '#e5e7eb',
					'text-muted': '#9ca3af',
					'accent': '#00d4ff',
					'accent-purple': '#a855f7',
					'accent-green': '#22c55e',
					'glow': '#00d4ff',
				},
			},
			borderRadius: {
				lg: 'var(--radius)',
				md: 'calc(var(--radius) - 2px)',
				sm: 'calc(var(--radius) - 4px)',
			},
			boxShadow: {
				'cyber-glow': '0 0 20px rgba(0, 212, 255, 0.3)',
				'cyber-glow-lg': '0 0 40px rgba(0, 212, 255, 0.4)',
				'cyber-purple': '0 0 20px rgba(168, 85, 247, 0.3)',
				'cyber-green': '0 0 20px rgba(34, 197, 94, 0.3)',
				'cyber-inner': 'inset 0 0 20px rgba(0, 212, 255, 0.1)',
			},
			backgroundImage: {
				'cyber-gradient': 'linear-gradient(135deg, #00d4ff 0%, #a855f7 100%)',
				'cyber-gradient-dark': 'linear-gradient(135deg, #0a0e17 0%, #1a1a2e 50%, #0a0e17 100%)',
				'cyber-mesh': 'radial-gradient(circle at 25% 25%, rgba(0, 212, 255, 0.1) 0%, transparent 50%), radial-gradient(circle at 75% 75%, rgba(168, 85, 247, 0.1) 0%, transparent 50%)',
			},
			keyframes: {
				'accordion-down': {
					from: { height: 0 },
					to: { height: 'var(--radix-accordion-content-height)' },
				},
				'accordion-up': {
					from: { height: 0 },
					to: { height: 'var(--radix-accordion-content-height)' },
				},
				'pulse-glow': {
					'0%, 100%': { boxShadow: '0 0 20px rgba(0, 212, 255, 0.3)' },
					'50%': { boxShadow: '0 0 40px rgba(0, 212, 255, 0.6)' },
				},
				'border-flow': {
					'0%': { backgroundPosition: '0% 50%' },
					'50%': { backgroundPosition: '100% 50%' },
					'100%': { backgroundPosition: '0% 50%' },
				},
				'float': {
					'0%, 100%': { transform: 'translateY(0)' },
					'50%': { transform: 'translateY(-10px)' },
				},
				'typing': {
					'0%': { width: '0' },
					'100%': { width: '100%' },
				},
				'blink': {
					'0%, 50%': { opacity: 1 },
					'51%, 100%': { opacity: 0 },
				},
			},
			animation: {
				'accordion-down': 'accordion-down 0.2s ease-out',
				'accordion-up': 'accordion-up 0.2s ease-out',
				'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
				'border-flow': 'border-flow 3s ease infinite',
				'float': 'float 3s ease-in-out infinite',
				'typing': 'typing 2s steps(40) forwards',
				'blink': 'blink 1s step-end infinite',
			},
		},
	},
	plugins: [require('tailwindcss-animate')],
}

