import { useMemo, useState } from 'react';
import AccountPanel from './AccountPanel';
import type { AccountSlotState, Platform, SafeMessage } from '../types';

const names = [
  ['Maya Haddad', 'Omar Nasser', 'Lina Khoury'],
  ['Rami Saleh', 'Nour Mansour', 'Tala Saad'],
  ['Karim Farah', 'Dana Hamdan', 'Sami Habib'],
];

function demoSlots(platform: Platform): AccountSlotState[] {
  return names.map((group, index) => {
    const contacts = group.map((name, contactIndex) => ({
      id: `${platform}-${index + 1}-contact-${contactIndex + 1}`,
      name,
      lastMessage: contactIndex === 0 ? 'Thanks, I will send it today.' : 'Approved contact',
      unreadCount: contactIndex === 0 ? index + 1 : 0,
    }));
    const first = contacts[0];
    return {
      slotId: `${platform}-${index + 1}`,
      index: index + 1,
      assignment: {
        id: `demo-${platform}-${index + 1}`,
        user_id: 'demo-user',
        office_id: 'demo-office',
        platform,
        account_slot: index + 1,
        display_name: `HR Account ${index + 1}`,
        gateway_number: `hr-account-${index + 1}`,
        is_active: true,
        created_at: new Date(2026, 0, index + 1).toISOString(),
      },
      contacts,
      selectedClientId: first.id,
      messagesByClient: {
        [first.id]: [
          { id: `received-${index}`, clientId: first.id, body: 'Hello, is the interview time confirmed?', timestamp: 1784015700, fromMe: false },
          { id: `sent-${index}`, clientId: first.id, body: 'Yes, your appointment is confirmed.', timestamp: 1784016000, fromMe: true },
        ],
      },
      status: 'connected',
      statusMessage: 'Connected',
      qrCode: null,
    };
  });
}

export default function DemoWorkspace() {
  const [activePlatform, setActivePlatform] = useState<Platform>('telegram');
  const [slots, setSlots] = useState<Record<Platform, AccountSlotState[]>>({
    telegram: demoSlots('telegram'),
    whatsapp: demoSlots('whatsapp'),
  });
  const activeSlots = useMemo(() => slots[activePlatform], [activePlatform, slots]);

  const selectContact = (slotId: string, clientId: string) => {
    setSlots(current => ({
      ...current,
      [activePlatform]: current[activePlatform].map(slot => slot.slotId === slotId ? { ...slot, selectedClientId: clientId } : slot),
    }));
  };

  const sendMessage = async (slotId: string, clientId: string, body: string) => {
    const message: SafeMessage = {
      id: `demo-${crypto.randomUUID()}`,
      clientId,
      body,
      timestamp: Math.floor(Date.now() / 1000),
      fromMe: true,
    };
    setSlots(current => ({
      ...current,
      [activePlatform]: current[activePlatform].map(slot => slot.slotId === slotId ? {
        ...slot,
        messagesByClient: {
          ...slot.messagesByClient,
          [clientId]: [...(slot.messagesByClient[clientId] || []), message],
        },
      } : slot),
    }));
  };

  return (
    <div className="dashboard-shell">
      <div style={{ background: '#fff4cc', color: '#5f4300', padding: '8px 16px', textAlign: 'center', fontWeight: 700 }}>
        Visual review only — sample contacts and messages. Live accounts, QR linking, and delivery run in the Windows application.
      </div>
      <div className="dashboard-toolbar">
        <div className="platform-tabs" role="tablist" aria-label="Communication platforms">
          <button className={activePlatform === 'telegram' ? 'active' : ''} onClick={() => setActivePlatform('telegram')}>
            <span className="tab-icon telegram">T</span>Telegram accounts
          </button>
          <button className={activePlatform === 'whatsapp' ? 'active' : ''} onClick={() => setActivePlatform('whatsapp')}>
            <span className="tab-icon whatsapp">W</span>WhatsApp accounts
          </button>
        </div>
        <div className="staff-menu"><span>Visual QA preview</span><button type="button">Sign out</button></div>
      </div>
      <div className="account-grid" role="tabpanel">
        {activeSlots.map(slot => (
          <AccountPanel
            key={slot.slotId}
            platform={activePlatform}
            slot={slot}
            onConnect={() => undefined}
            onSelectContact={clientId => selectContact(slot.slotId, clientId)}
            onSendMessage={(clientId, message) => sendMessage(slot.slotId, clientId, message)}
            onSendFile={async () => undefined}
            onSubmitPassword={async () => undefined}
          />
        ))}
      </div>
    </div>
  );
}
