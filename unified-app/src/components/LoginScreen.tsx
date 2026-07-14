'use client';

import { useState } from 'react';

interface LoginScreenProps {
  onLogin: (email: string, password: string) => void;
  loading: boolean;
  error: string;
}

export default function LoginScreen({ onLogin, loading, error }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    onLogin(email, password);
  };

  return (
    <div className="flex items-center justify-center w-full bg-bg-primary p-5 h-[calc(100vh-32px)] chat-wallpaper">
      <div className="bg-bg-secondary rounded-xl p-10 w-full max-w-[420px] shadow-[0_4px_12px_rgba(0,0,0,0.08)]">
        <div className="text-center mb-8">
          <div className="relative w-[70px] h-[70px] mx-auto mb-4 flex items-center justify-center">
            <span className="brand-cluster large" aria-hidden="true"><i>T</i><i>W</i></span>
          </div>
          <h1 className="text-2xl mb-1 text-text-primary">Staff Communications Control</h1>
          <p className="text-text-secondary text-sm">Protected Telegram and WhatsApp workspace</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-[13px] text-text-secondary mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="staff@example.com"
              required
              className="w-full p-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent transition-colors"
            />
          </div>
          <div className="mb-4">
            <label className="block text-[13px] text-text-secondary mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter password"
              required
              className="w-full p-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 p-2.5 bg-accent text-white rounded-lg text-sm font-medium cursor-pointer hover:bg-accent-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span>{loading ? 'Signing in...' : 'Sign In'}</span>
            {loading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin-slow" />}
          </button>
        </form>
        {error && (
          <div className="mt-4 bg-danger/10 border border-danger text-danger p-2.5 rounded-lg text-[13px]">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
