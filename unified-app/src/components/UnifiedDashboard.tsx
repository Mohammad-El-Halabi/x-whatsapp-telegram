import { useCallback, useEffect, useMemo, useState } from 'react';
import QRCode from 'qrcode';
import AccountPanel from './AccountPanel';
import { usePlatformBridge } from '../hooks/usePlatformBridge';
import { useSupabase } from '../hooks/useSupabase';
import type {
  AccountSlotState,
  Assignment,
  Platform,
  PlatformEvent,
  SafeContact,
  SafeMessage,
  User,
} from '../types';

interface Props {
  user: User;
  officeId: string;
  onLogout: () => void;
}

type SlotStore = Record<Platform, AccountSlotState[]>;

function makeSlots(platform: Platform): AccountSlotState[] {
  return [1, 2, 3].map(index => ({
    slotId: `${platform}-${index}`,
    index,
    contacts: [],
    selectedClientId: null,
    messagesByClient: {},
    status: 'unassigned',
    statusMessage: 'Not assigned',
    qrCode: null,
  }));
}

function safeStatusMessage(value: unknown, fallback: string) {
  const text = typeof value === 'string' ? value : fallback;
  return text.replace(/\+?\d[\d\s().-]{6,}\d/g, 'assigned account').slice(0, 120);
}

function normalizeMessage(value: any): SafeMessage | null {
  if (!value?.clientId || !value?.id) return null;
  return {
    id: String(value.id),
    clientId: String(value.clientId),
    clientName: value.clientName ? String(value.clientName) : undefined,
    body: String(value.body || value.caption || ''),
    timestamp: Number(value.timestamp || Math.floor(Date.now() / 1000)),
    fromMe: !!value.fromMe,
    ack: value.ack == null ? undefined : Number(value.ack),
    hasMedia: !!value.hasMedia,
    mediaType: value.mediaType || null,
    mediaData: value.mediaData || null,
    caption: value.caption || null,
  };
}

function appendMessage(messages: SafeMessage[], incoming: SafeMessage) {
  if (messages.some(message => message.id === incoming.id)) return messages;
  if (incoming.fromMe) {
    const optimisticIndex = messages.findIndex(message =>
      message.id.startsWith('pending-') &&
      message.fromMe &&
      message.body === incoming.body &&
      Math.abs(message.timestamp - incoming.timestamp) < 30
    );
    if (optimisticIndex !== -1) {
      const next = messages.slice();
      next[optimisticIndex] = incoming;
      return next;
    }
  }
  return [...messages, incoming].sort((a, b) => a.timestamp - b.timestamp);
}

export default function UnifiedDashboard({ user, officeId, onLogout }: Props) {
  const [activePlatform, setActivePlatform] = useState<Platform>('telegram');
  const [slots, setSlots] = useState<SlotStore>({
    telegram: makeSlots('telegram'),
    whatsapp: makeSlots('whatsapp'),
  });
  const [pageMessage, setPageMessage] = useState('Preparing assigned accounts…');
  const { api: supabase } = useSupabase();

  const updateSlot = useCallback((platform: Platform, slotId: string, updater: (slot: AccountSlotState) => AccountSlotState) => {
    setSlots(current => ({
      ...current,
      [platform]: current[platform].map(slot => slot.slotId === slotId ? updater(slot) : slot),
    }));
  }, []);

  const handlePlatformEvent = useCallback((payload: PlatformEvent) => {
    if (!payload || (payload.platform !== 'telegram' && payload.platform !== 'whatsapp')) return;
    const platform = payload.platform;
    const slotId = payload.slotId;

    if (payload.event === 'qr') {
      const existing = payload.data?.qrData;
      if (existing) {
        updateSlot(platform, slotId, slot => ({ ...slot, qrCode: existing, status: 'pending', statusMessage: 'Scan the QR code' }));
      } else if (payload.data?.qrValue) {
        QRCode.toDataURL(String(payload.data.qrValue), { width: 260, margin: 2 })
          .then(qrCode => updateSlot(platform, slotId, slot => ({ ...slot, qrCode, status: 'pending', statusMessage: 'Scan the QR code' })))
          .catch(() => updateSlot(platform, slotId, slot => ({ ...slot, status: 'error', statusMessage: 'Could not create the QR code' })));
      }
      return;
    }

    if (payload.event === 'ready') {
      updateSlot(platform, slotId, slot => ({
        ...slot,
        qrCode: null,
        passwordRequired: false,
        status: 'connected',
        statusMessage: 'Connected',
      }));
      setSlots(current => {
        const assignment = current[platform].find(slot => slot.slotId === slotId)?.assignment;
        if (assignment?.id) {
          void supabase.updateConnectionStatus(assignment.id, 'connected', { slot: slotId, platform });
        }
        return current;
      });
      if (platform === 'whatsapp') {
        void bridge.getWhatsAppChats(slotId);
      }
      return;
    }

    if (payload.event === 'password-required') {
      updateSlot(platform, slotId, slot => ({
        ...slot,
        qrCode: null,
        passwordRequired: true,
        status: 'pending',
        statusMessage: 'Two-step verification required',
      }));
      return;
    }

    if (payload.event === 'status-change') {
      const status = payload.data?.status === 'connected' ? 'connected' : 'pending';
      updateSlot(platform, slotId, slot => ({
        ...slot,
        status,
        statusMessage: safeStatusMessage(payload.data?.message, status === 'connected' ? 'Connected' : 'Connecting'),
      }));
      return;
    }

    if (payload.event === 'error') {
      updateSlot(platform, slotId, slot => ({
        ...slot,
        qrCode: null,
        status: 'error',
        statusMessage: safeStatusMessage(payload.data?.message, 'Connection error'),
      }));
      return;
    }

    if (payload.event === 'disconnected') {
      updateSlot(platform, slotId, slot => ({ ...slot, qrCode: null, status: 'disconnected', statusMessage: 'Disconnected' }));
      return;
    }

    if (payload.event === 'chats' && Array.isArray(payload.data)) {
      updateSlot(platform, slotId, slot => {
        const chatMap = new Map(payload.data.map((chat: any) => [String(chat.id), chat]));
        return {
          ...slot,
          contacts: slot.contacts.map(contact => {
            const chat: any = chatMap.get(contact.id);
            return chat ? {
              ...contact,
              unreadCount: Number(chat.unreadCount || 0),
              lastMessage: chat.lastMessage?.body || '',
              lastTimestamp: Number(chat.lastMessage?.timestamp || 0),
            } : contact;
          }),
        };
      });
      return;
    }

    if (payload.event === 'messages' && Array.isArray(payload.data)) {
      const normalized = payload.data.map(normalizeMessage).filter(Boolean) as SafeMessage[];
      updateSlot(platform, slotId, slot => {
        const next = { ...slot.messagesByClient };
        for (const message of normalized) {
          next[message.clientId] = appendMessage(next[message.clientId] || [], message);
        }
        return { ...slot, messagesByClient: next };
      });
      return;
    }

    if (payload.event === 'new-message' || payload.event === 'message-sent') {
      const message = normalizeMessage(payload.data);
      if (!message) return;
      updateSlot(platform, slotId, slot => ({
        ...slot,
        messagesByClient: {
          ...slot.messagesByClient,
          [message.clientId]: appendMessage(slot.messagesByClient[message.clientId] || [], message),
        },
        contacts: slot.contacts.map(contact => contact.id === message.clientId ? {
          ...contact,
          lastMessage: message.body || 'Attachment',
          lastTimestamp: message.timestamp,
          unreadCount: message.fromMe || slot.selectedClientId === message.clientId
            ? contact.unreadCount || 0
            : (contact.unreadCount || 0) + 1,
        } : contact),
      }));
      return;
    }

    if (payload.event === 'message-ack') {
      updateSlot(platform, slotId, slot => ({
        ...slot,
        messagesByClient: Object.fromEntries(Object.entries(slot.messagesByClient).map(([clientId, messages]) => [
          clientId,
          messages.map(message => message.id === payload.data?.id ? { ...message, ack: Number(payload.data.ack) } : message),
        ])),
      }));
    }
  }, [supabase, updateSlot]);

  const bridge = usePlatformBridge(handlePlatformEvent);

  useEffect(() => {
    let cancelled = false;
    async function loadPlatform(platform: Platform) {
      const assignments = await supabase.getStaffAssignments(user.id, platform) as Assignment[];
      const assignmentsBySlot = new Map<number, Assignment>();
      const legacyAssignments: Assignment[] = [];
      assignments.forEach(assignment => {
        const slot = Number(assignment.account_slot);
        if (Number.isInteger(slot) && slot >= 1 && slot <= 3 && !assignmentsBySlot.has(slot)) {
          assignmentsBySlot.set(slot, assignment);
        } else {
          legacyAssignments.push(assignment);
        }
      });
      legacyAssignments.forEach(assignment => {
        const openSlot = [1, 2, 3].find(slot => !assignmentsBySlot.has(slot));
        if (openSlot) assignmentsBySlot.set(openSlot, assignment);
      });
      const platformSlots = makeSlots(platform).map(slot => {
        const assignment = assignmentsBySlot.get(slot.index);
        return assignment ? {
          ...slot,
          assignment,
          status: 'disconnected' as const,
          statusMessage: 'Ready to connect',
        } : slot;
      });
      if (cancelled) return;
      setSlots(current => ({ ...current, [platform]: platformSlots }));

      for (const slot of platformSlots) {
        if (!slot.assignment || cancelled) continue;
        try {
          const contacts = await supabase.getAllowedContacts(
            officeId,
            platform,
            slot.slotId,
            slot.assignment.gateway_number || 'default',
          ) as SafeContact[];
          if (cancelled) return;
          updateSlot(platform, slot.slotId, current => ({ ...current, contacts }));
          if (platform === 'whatsapp') {
            await bridge.connectWhatsApp(slot.slotId, slot.assignment.id, slot.assignment.gateway_number || '');
          } else {
            await bridge.connectTelegram(slot.slotId, slot.assignment.id);
          }
        } catch (error) {
          if (cancelled) return;
          updateSlot(platform, slot.slotId, current => ({
            ...current,
            status: 'error',
            statusMessage: safeStatusMessage(error, 'Could not prepare this account'),
          }));
        }
      }
    }

    Promise.all([loadPlatform('telegram'), loadPlatform('whatsapp')])
      .then(() => { if (!cancelled) setPageMessage(''); })
      .catch(error => { if (!cancelled) setPageMessage(safeStatusMessage(error, 'Could not load assignments')); });
    return () => { cancelled = true; };
  }, [officeId, user.id]);

  useEffect(() => {
    const safeTelegramMessages = Object.fromEntries(slots.telegram.map(slot => [slot.slotId, slot.messagesByClient]));
    localStorage.setItem('staff-control-telegram-messages', JSON.stringify(safeTelegramMessages));
  }, [slots.telegram]);

  const selectContact = useCallback((platform: Platform, slotId: string, clientId: string) => {
    updateSlot(platform, slotId, slot => ({
      ...slot,
      selectedClientId: clientId,
      contacts: slot.contacts.map(contact => contact.id === clientId ? { ...contact, unreadCount: 0 } : contact),
    }));
    if (platform === 'whatsapp') {
      void bridge.getWhatsAppMessages(slotId, clientId);
      void bridge.markWhatsAppRead(slotId, clientId);
    } else {
      void bridge.getTelegramMessages(slotId, clientId);
      void bridge.markTelegramRead(slotId, clientId);
    }
  }, [bridge, updateSlot]);

  const connectSlot = useCallback(async (platform: Platform, slot: AccountSlotState) => {
    if (!slot.assignment) return;
    updateSlot(platform, slot.slotId, current => ({ ...current, status: 'pending', statusMessage: 'Connecting', qrCode: null }));
    try {
      if (platform === 'whatsapp') {
        await bridge.connectWhatsApp(slot.slotId, slot.assignment.id, slot.assignment.gateway_number || '');
      } else {
        await bridge.connectTelegram(slot.slotId, slot.assignment.id);
      }
    } catch (error) {
      updateSlot(platform, slot.slotId, current => ({ ...current, status: 'error', statusMessage: safeStatusMessage(error, 'Connection failed') }));
    }
  }, [bridge, updateSlot]);

  const sendMessage = useCallback(async (platform: Platform, slotId: string, clientId: string, body: string) => {
    const pending: SafeMessage = {
      id: `pending-${crypto.randomUUID()}`,
      clientId,
      body,
      timestamp: Math.floor(Date.now() / 1000),
      fromMe: true,
    };
    updateSlot(platform, slotId, slot => ({
      ...slot,
      messagesByClient: {
        ...slot.messagesByClient,
        [clientId]: appendMessage(slot.messagesByClient[clientId] || [], pending),
      },
    }));
    try {
      if (platform === 'whatsapp') {
        await bridge.sendWhatsAppMessage(slotId, clientId, body);
      } else {
        await bridge.sendTelegramMessage(slotId, clientId, body);
      }
    } catch (error) {
      updateSlot(platform, slotId, slot => ({ ...slot, statusMessage: safeStatusMessage(error, 'Message failed') }));
      throw error;
    }
  }, [bridge, updateSlot]);

  const sendFile = useCallback(async (platform: Platform, slotId: string, clientId: string, filePath: string) => {
    if (platform === 'whatsapp') {
      await bridge.sendWhatsAppFile(slotId, clientId, filePath);
    } else {
      await bridge.sendTelegramFile(slotId, clientId, filePath);
    }
  }, [bridge]);

  const logout = async () => {
    await bridge.disconnectAll();
    await supabase.logout();
    localStorage.removeItem('staff-control-session');
    onLogout();
  };

  const activeSlots = useMemo(() => slots[activePlatform], [activePlatform, slots]);

  return (
    <div className="dashboard-shell">
      <div className="dashboard-toolbar">
        <div className="platform-tabs" role="tablist" aria-label="Communication platforms">
          <button className={activePlatform === 'telegram' ? 'active' : ''} onClick={() => setActivePlatform('telegram')}>
            <span className="tab-icon telegram">T</span>Telegram accounts
          </button>
          <button className={activePlatform === 'whatsapp' ? 'active' : ''} onClick={() => setActivePlatform('whatsapp')}>
            <span className="tab-icon whatsapp">W</span>WhatsApp accounts
          </button>
        </div>
        <div className="staff-menu">
          <span>{user.full_name || user.email || 'Staff member'}</span>
          <button onClick={() => void logout()}>Sign out</button>
        </div>
      </div>
      {pageMessage && <div className="page-message">{pageMessage}</div>}
      <div className="account-grid" role="tabpanel">
        {activeSlots.map(slot => (
          <AccountPanel
            key={slot.slotId}
            platform={activePlatform}
            slot={slot}
            onConnect={() => void connectSlot(activePlatform, slot)}
            onSelectContact={clientId => selectContact(activePlatform, slot.slotId, clientId)}
            onSendMessage={(clientId, message) => sendMessage(activePlatform, slot.slotId, clientId, message)}
            onSendFile={(clientId, filePath) => sendFile(activePlatform, slot.slotId, clientId, filePath)}
            onSubmitPassword={async password => { await bridge.submitTelegramPassword(slot.slotId, password); }}
          />
        ))}
      </div>
    </div>
  );
}
