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
          <div className="relative w-[70px] h-[70px] mx-auto mb-4">
            <svg width="70" height="70" viewBox="0 0 24 24" fill="none">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" fill="#25D366"/>
              <path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.37 0-4.567-.82-6.293-2.192l-.44-.36-2.893.967.967-2.893-.36-.44A9.935 9.935 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z" fill="#25D366"/>
            </svg>
          </div>
          <h1 className="text-2xl mb-1 text-text-primary">X-WhatsApp</h1>
          <p className="text-text-secondary text-sm">Staff Management Desktop App</p>
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
