import { invoke } from '@tauri-apps/api/core';
import { useMemo } from 'react';

export function useSupabase() {
  const api = useMemo(() => ({
    login: (email: string, password: string) =>
      invoke<{ user: any; session: any; error?: string; token?: string }>('supabase_login', { email, password }),
    restoreSession: (token: string) =>
      invoke('supabase_restore_session', { token }),
    logout: () => invoke('supabase_logout'),
    getStaffAssignments: (userId: string) =>
      invoke<any[]>('supabase_get_staff_assignments', { userId }),
    getUser: (userId: string) =>
      invoke<any[]>('supabase_get_user', { userId }),
    getClients: (officeId: string) =>
      invoke<any[]>('supabase_get_clients', { officeId }),
    updateConnectionStatus: (assignmentId: string, status: string, data?: any) =>
      invoke('supabase_update_connection_status', { assignmentId, status, connectionData: data }),
  }), []);

  return { api };
}
