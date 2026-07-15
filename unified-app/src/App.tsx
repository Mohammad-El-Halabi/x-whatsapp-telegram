import { useEffect, useState } from 'react';
import TitleBar from './components/TitleBar';
import LoginScreen from './components/LoginScreen';
import UnifiedDashboard from './components/UnifiedDashboard';
import DemoWorkspace from './components/DemoWorkspace';
import { useSupabase } from './hooks/useSupabase';
import type { User } from './types';

interface SavedSession {
  user: User;
  token: string;
  officeId: string;
  expiresAt: number;
}

export default function App() {
  const demoMode = import.meta.env.VITE_DEMO_MODE === '1'
    || (['127.0.0.1', 'localhost'].includes(window.location.hostname)
      && new URLSearchParams(window.location.search).get('demo') === '1');
  const [session, setSession] = useState<SavedSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const { api: supabase } = useSupabase();

  useEffect(() => {
    if (demoMode) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    async function restore() {
      try {
        const raw = localStorage.getItem('staff-control-session');
        if (!raw) return;
        const saved = JSON.parse(raw) as SavedSession;
        if (!saved?.token || !saved?.user?.id || !saved.officeId || saved.expiresAt <= Date.now()) {
          localStorage.removeItem('staff-control-session');
          return;
        }
        await supabase.restoreSession(saved.token);
        const profiles = await supabase.getUser(saved.user.id) as User[];
        const profile = Array.isArray(profiles) ? profiles[0] : null;
        if (!profile || profile.is_active === false || !profile.office_id) {
          localStorage.removeItem('staff-control-session');
          return;
        }
        if (!cancelled) {
          const verified = { ...saved, user: { ...saved.user, ...profile }, officeId: profile.office_id };
          setSession(verified);
        }
      } catch {
        localStorage.removeItem('staff-control-session');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void restore();
    return () => { cancelled = true; };
  }, [demoMode]);

  const login = async (email: string, password: string) => {
    setLoginLoading(true);
    setLoginError('');
    try {
      const result = await supabase.login(email, password);
      if (result.error || !result.user || !result.token) {
        setLoginError(result.error || 'Login failed');
        return;
      }
      const profiles = await supabase.getUser(result.user.id) as User[];
      const profile = Array.isArray(profiles) ? profiles[0] : null;
      if (!profile || profile.is_active === false) {
        setLoginError('This staff account is not active.');
        return;
      }
      if (!profile.office_id) {
        setLoginError('This staff account is not assigned to an office.');
        return;
      }
      const saved: SavedSession = {
        user: { ...result.user, ...profile },
        token: result.token,
        officeId: profile.office_id,
        expiresAt: Date.now() + 23 * 60 * 60 * 1000,
      };
      localStorage.setItem('staff-control-session', JSON.stringify(saved));
      setSession(saved);
    } catch (error: any) {
      setLoginError(error?.message || String(error) || 'Login failed');
    } finally {
      setLoginLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <TitleBar />
      {demoMode ? (
        <DemoWorkspace />
      ) : loading ? (
        <div className="loading-screen"><div className="spinner" /><span>Loading secure workspace…</span></div>
      ) : session ? (
        <UnifiedDashboard
          user={session.user}
          officeId={session.officeId}
          onLogout={() => setSession(null)}
        />
      ) : (
        <LoginScreen onLogin={login} loading={loginLoading} error={loginError} />
      )}
    </div>
  );
}
