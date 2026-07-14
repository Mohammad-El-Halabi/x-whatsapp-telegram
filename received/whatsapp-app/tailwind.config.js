/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-dock': '#F0F2F5',
        'bg-primary': '#EFEAE2',
        'bg-secondary': '#FFFFFF',
        'bg-tertiary': '#F0F2F5',
        'bg-hover': '#EAEAEA',
        'bg-chat': '#EFEAE2',
        'text-primary': '#111B21',
        'text-secondary': '#667781',
        'text-muted': '#8696A0',
        'accent': '#00A884',
        'accent-hover': '#06967B',
        'accent-green': '#25D366',
        'danger': '#EF5350',
        'danger-hover': '#E53935',
        'border': '#E9EDEF',
        'border-dark': '#D1D7DB',
        'success': '#25D366',
        'warning': '#FFC107',
        'info': '#53BDEB',
        'msg-out': '#D9FDD3',
        'msg-in': '#FFFFFF',
        'status-blue': '#53BDEB',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Oxygen',
          'Ubuntu',
          'sans-serif',
        ],
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s infinite',
        'spin-slow': 'spin 0.8s linear infinite',
        'slide-in': 'slideIn 0.3s ease',
        'pulse-dot': 'pulse-dot 1.5s infinite',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(1.3)', opacity: '0' },
        },
        slideIn: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
};
