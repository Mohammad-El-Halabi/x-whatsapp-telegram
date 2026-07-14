import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo, type ReactNode } from 'react';
import { useWhatsApp } from '../hooks/useWhatsApp';
import { useSupabase } from '../hooks/useSupabase';
import { isPermissionGranted, requestPermission, sendNotification } from '@tauri-apps/plugin-notification';
import type { User, Assignment, Chat, Client, Toast } from '../types';

const normalizeId = (id: string | null | undefined) =>
  (id || '').split('@')[0].split(':')[0].replace(/\D/g, '');

interface AppState {
  user: User | null;
  officeId: string | null;
  assignments: Assignment[];
  chats: Chat[];
  clients: Client[];
  filteredChats: Chat[];
  qrCodeUrl: string | null;
  connectionStatus: string;
  connectionMessage: string;
  loginLoading: boolean;
  loginError: string;
  toast: Toast | null;
  isWhatsAppConnected: boolean;
  whatsapp: ReturnType<typeof useWhatsApp>['api'];
  addListener: ReturnType<typeof useWhatsApp>['addListener'];
  handleLogin: (email: string, password: string) => Promise<void>;
  handleConnect: (assignment?: Assignment) => void;
  showToast: (message: string, type?: Toast['type']) => void;
  clearUnread: (chatId: string) => void;
  loading: boolean;
}

const AppContext = createContext<AppState | null>(null);

export function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within AppProvider');
  return ctx;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [officeId, setOfficeId] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [connectionMessage, setConnectionMessage] = useState('Disconnected');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [toast, setToast] = useState<Toast | null>(null);
  const [loading, setLoading] = useState(true);

  const { api: whatsapp, isConnected, addListener } = useWhatsApp();
  const { api: supabase } = useSupabase();

  const clientsRef = useRef<Client[]>([]);
  const assignmentsRef = useRef<Assignment[]>([]);
  const officeIdRef = useRef<string | null>(null);
  const connectionStatusRef = useRef(connectionStatus);
  const autoConnectRef = useRef(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { clientsRef.current = clients; }, [clients]);
  useEffect(() => { assignmentsRef.current = assignments; }, [assignments]);
  useEffect(() => { officeIdRef.current = officeId; }, [officeId]);
  useEffect(() => { connectionStatusRef.current = connectionStatus; }, [connectionStatus]);

  const showToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message, type });
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
    isPermissionGranted().then(granted => {
      if (granted) {
        sendNotification({ title: 'X-WhatsApp', body: message });
      } else if (granted !== null) {
        requestPermission().then(perm => {
          if (perm === 'granted') sendNotification({ title: 'X-WhatsApp', body: message });
        }).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  const handleConnect = useCallback((assignment?: Assignment) => {
    setConnectionStatus('pending');
    setConnectionMessage('Initializing...');
    const id = assignment?.id || 'default';
    const gw = assignment?.gateway_number || '';
    if (assignment?.id) {
      supabase.updateConnectionStatus(assignment.id, 'pending').catch(() => {});
    }
    localStorage.setItem('xwhatsapp_last_assignment', id);
    whatsapp.connect({ assignmentId: id, gatewayNumber: gw }).catch(() => {});
  }, [whatsapp, supabase]);

  const handleLogin = useCallback(async (email: string, password: string) => {
    setLoginLoading(true);
    setLoginError('');
    try {
      const result = await supabase.login(email, password);
      if (result.error) {
        setLoginError(result.error);
        return;
      }
      const u = result.user;
      setUser(u);
      setLoginError('');
      let oid: string | null = null;
      try {
        const profileArr = await supabase.getUser(u.id);
        const profile = Array.isArray(profileArr) && profileArr.length > 0 ? profileArr[0] : null;
        oid = profile?.office_id || null;
      } catch {}
      setOfficeId(oid);
      officeIdRef.current = oid;
      localStorage.setItem('xwhatsapp_session', JSON.stringify({
        user: u,
        token: result.token,
        officeId: oid,
        expiresAt: Date.now() / 1000 + 86400
      }));
      let assignmentsList: Assignment[] = [];
      try {
        const data = await supabase.getStaffAssignments(u.id);
        assignmentsList = Array.isArray(data) ? data : [];
      } catch {}
      setAssignments(assignmentsList);
      assignmentsRef.current = assignmentsList;
      if (assignmentsList.length > 0) {
        const first = assignmentsList[0];
        localStorage.setItem('xwhatsapp_last_assignment', first.id);
        handleConnect(first);
      } else {
        handleConnect();
      }
      if (oid) {
        supabase.getClients(oid).then((d) => {
          const c = Array.isArray(d) ? d : [];
          setClients(c);
          clientsRef.current = c;
        }).catch(() => {});
      }
    } catch (err: any) {
      setLoginError(err.message || 'Login failed');
    } finally {
      setLoginLoading(false);
    }
  }, [supabase, handleConnect]);

  // WhatsApp listeners
  useEffect(() => {
    const cleanups = [
      addListener('qr', (data: any) => {
        const url = data.qrData || data;
        setQrCodeUrl(url);
        setConnectionStatus('pending');
        setConnectionMessage('Scan QR code with WhatsApp');
      }),
      addListener('authenticated', () => {
        showToast('WhatsApp authenticated', 'success');
      }),
      addListener('ready', (data: any) => {
        setQrCodeUrl(null);
        setConnectionStatus('connected');
        setConnectionMessage(`Connected as ${data.name}`);
        showToast(`Connected as ${data.name}`, 'success');
        const currentAssignments = assignmentsRef.current;
        if (currentAssignments.length > 0) {
          const a = currentAssignments[0];
          if (a.id && a.id !== 'default') {
            supabase.updateConnectionStatus(a.id, 'connected', { name: data.name, number: data.number }).catch(() => {});
          } else {
            const deviceAssignment: Assignment = { id: 'default', gateway_number: data.number || '', display_name: data.name || '', connection_status: 'connected' };
            setAssignments([deviceAssignment]);
            assignmentsRef.current = [deviceAssignment];
          }
          const oid = officeIdRef.current;
          if (oid) {
            supabase.getClients(oid).then((d) => {
              const c = Array.isArray(d) ? d : [];
              setClients(c);
              clientsRef.current = c;
            }).catch(() => {});
          }
        }
        whatsapp.getChats().catch(() => {});
      }),
      addListener('disconnected', () => {
        setQrCodeUrl(null);
        setConnectionStatus('disconnected');
        setConnectionMessage('Disconnected');
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
        const savedAssignmentId = localStorage.getItem('xwhatsapp_last_assignment');
        const currentAssignments = assignmentsRef.current;
        const target = savedAssignmentId
          ? currentAssignments.find((a: Assignment) => a.id === savedAssignmentId) || currentAssignments[0]
          : currentAssignments[0];
        if (target) {
          reconnectTimerRef.current = setTimeout(() => {
            handleConnect(target);
          }, 3000);
        }
      }),
      addListener('error', (data: any) => {
        const msg = data?.message || 'Unknown error';
        if (connectionStatusRef.current !== 'connected' && connectionStatusRef.current !== 'error') {
          console.error('[WhatsApp error during init]:', msg);
          return;
        }
        showToast('WhatsApp error: ' + msg, 'error');
        setConnectionStatus('error');
        setConnectionMessage(msg);
      }),
      addListener('status-change', (status: any) => {
        setConnectionStatus(status.status);
        setConnectionMessage(status.message);
      }),
      addListener('chats', (chatList: Chat[]) => {
        setChats(chatList);
      }),
      addListener('new-message', (msg: any) => {
        const body = msg.body || (msg.mediaType === 'image' ? '📷 Photo' : msg.mediaType === 'video' ? '🎬 Video' : msg.mediaType === 'audio' ? '🎤 Voice message' : msg.mediaType === 'document' ? '📄 Document' : '');
        const msgType = msg.mediaType || msg.type || undefined;
        const currentClients = clientsRef.current;
        if (!msg.fromMe && body) {
          const chatName = msg.fromName || msg.from || 'Unknown';
          const matched = currentClients.find((c: any) => {
            const cPhone = (c.platform_identifiers?.whatsapp || '').replace(/\D/g, '');
            const chatNumber = (msg.from || '').split('@')[0].replace(/\D/g, '');
            return cPhone === chatNumber || cPhone.endsWith(chatNumber) || chatNumber.endsWith(cPhone);
          });
          showToast(`${matched?.masked_identity || chatName}: ${body.substring(0, 60)}`, 'info');
        }
        setChats(prev => {
          const chatId = msg.fromMe ? msg.to : msg.from;
          const chatNumber = normalizeId(chatId);
          const idx = prev.findIndex(c => normalizeId(c.id) === chatNumber);
          if (idx !== -1) {
            const updated = {
              ...prev[idx],
              unreadCount: msg.fromMe ? prev[idx].unreadCount : (prev[idx].unreadCount || 0) + 1,
              lastMessage: { body, timestamp: msg.timestamp, fromMe: msg.fromMe, type: msgType },
            };
            const rest = prev.slice();
            rest.splice(idx, 1);
            return [updated, ...rest];
          }
          const matchedClient = currentClients.find((c: any) => {
            const cPhone = (c.platform_identifiers?.whatsapp || '').replace(/\D/g, '');
            return cPhone === chatNumber || cPhone.endsWith(chatNumber) || chatNumber.endsWith(cPhone);
          });
          return [{ id: chatId, name: matchedClient?.masked_identity || matchedClient?.full_name || undefined, isGroup: chatId.includes('@g.us'), unreadCount: msg.fromMe ? 0 : 1, lastMessage: { body, timestamp: msg.timestamp, fromMe: msg.fromMe, type: msgType } }, ...prev];
        });
      }),
      addListener('message-sent', (msg: any) => {
        const body = msg.body || (msg.mediaType === 'image' ? '📷 Photo' : msg.mediaType === 'video' ? '🎬 Video' : msg.mediaType === 'audio' ? '🎤 Voice message' : msg.mediaType === 'document' ? '📄 Document' : '');
        const msgType = msg.mediaType || msg.type || undefined;
        setChats(prev => {
          const chatId = msg.to;
          const chatNumber = normalizeId(chatId);
          const idx = prev.findIndex(c => normalizeId(c.id) === chatNumber);
          if (idx === -1) {
            return [{ id: chatId, name: undefined, isGroup: chatId.includes('@g.us'), unreadCount: 0, lastMessage: { body, timestamp: msg.timestamp, fromMe: true, type: msgType } }, ...prev];
          }
          const updated = { ...prev[idx], lastMessage: { body, timestamp: msg.timestamp, fromMe: true, type: msgType } };
          const rest = prev.slice();
          rest.splice(idx, 1);
          return [updated, ...rest];
        });
      }),
    ];
    return () => {
      cleanups.forEach(c => { if (typeof c === 'function') c(); });
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, []);

  // Fetch chats once connected
  useEffect(() => {
    if (connectionStatus !== 'connected') return;
    whatsapp.getChats().catch(() => {});
  }, [connectionStatus, whatsapp]);

  // Restore session on mount
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      try {
        const saved = localStorage.getItem('xwhatsapp_session');
        if (!saved) { setLoading(false); return; }
        const session = JSON.parse(saved);
        if (!session?.user?.id || !session.token || !session.expiresAt || session.expiresAt <= Date.now() / 1000) {
          localStorage.removeItem('xwhatsapp_session');
          setLoading(false);
          return;
        }
        await supabase.restoreSession(session.token);
        if (cancelled) return;
        setUser(session.user);
        setOfficeId(session.officeId || null);
        officeIdRef.current = session.officeId || null;
        const data = await supabase.getStaffAssignments(session.user.id);
        if (cancelled) return;
        const assignmentsList = Array.isArray(data) ? data : [];
        setAssignments(assignmentsList);
        assignmentsRef.current = assignmentsList;
        const savedAssignmentId = localStorage.getItem('xwhatsapp_last_assignment');
        const target = savedAssignmentId
          ? assignmentsList.find((a: Assignment) => a.id === savedAssignmentId) || assignmentsList[0]
          : assignmentsList[0];
        if (!autoConnectRef.current) {
          autoConnectRef.current = true;
          handleConnect(target);
          if (session.officeId) {
            supabase.getClients(session.officeId).then((d) => {
              if (cancelled) return;
              const c = Array.isArray(d) ? d : [];
              setClients(c);
              clientsRef.current = c;
            }).catch(() => {});
          }
        }
      } catch {
        localStorage.removeItem('xwhatsapp_session');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    restore();
    return () => { cancelled = true; };
  }, []);

  const clearUnread = useCallback((chatId: string) => {
    setChats(prev => prev.map(c =>
      normalizeId(c.id) === normalizeId(chatId) ? { ...c, unreadCount: 0 } : c
    ));
  }, []);

  const filteredChats = useMemo(() => {
    if (clients.length === 0) return chats.filter(c => c.id !== 'status@broadcast');
    return chats.filter(c => c.id !== 'status@broadcast').map(chat => {
      const chatNumber = normalizeId(chat.id);
      let matched = clients.find((c: any) => {
        const cPhone = (c.platform_identifiers?.whatsapp || '').replace(/\D/g, '');
        return cPhone === chatNumber || cPhone.endsWith(chatNumber) || chatNumber.endsWith(cPhone);
      });
      if (!matched && chat.name) {
        matched = clients.find((c: any) => {
          const clientName = (c.masked_identity || c.full_name || '').toLowerCase().trim();
          const chatName = (chat.name || '').toLowerCase().trim();
          return clientName && chatName && (clientName === chatName || clientName.includes(chatName) || chatName.includes(clientName));
        });
      }
      if (matched) return { ...chat, name: matched.masked_identity || matched.full_name || chat.name };
      return chat;
    }) as Chat[];
  }, [chats, clients]);

  const value: AppState = {
    user, officeId, assignments, chats, clients, filteredChats,
    qrCodeUrl, connectionStatus, connectionMessage,
    loginLoading, loginError, toast,
    isWhatsAppConnected: isConnected,
    whatsapp, addListener,
    handleLogin, handleConnect, showToast, clearUnread, loading,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
