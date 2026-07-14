import { useMemo, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import type { AccountSlotState, Platform, SafeMessage } from '../types';

interface Props {
  platform: Platform;
  slot: AccountSlotState;
  onConnect: () => void;
  onSelectContact: (clientId: string) => void;
  onSendMessage: (clientId: string, message: string) => Promise<void>;
  onSendFile: (clientId: string, filePath: string) => Promise<void>;
  onSubmitPassword: (password: string) => Promise<void>;
}

function messageText(message: SafeMessage) {
  if (message.body) return message.body;
  if (message.mediaType === 'image') return 'Photo';
  if (message.mediaType === 'video') return 'Video';
  if (message.mediaType === 'audio') return 'Voice message';
  if (message.mediaType === 'document' || message.hasMedia) return 'Attachment';
  return 'Message';
}

function formatTime(timestamp: number) {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function AccountPanel({
  platform,
  slot,
  onConnect,
  onSelectContact,
  onSendMessage,
  onSendFile,
  onSubmitPassword,
}: Props) {
  const [draft, setDraft] = useState('');
  const [search, setSearch] = useState('');
  const [sending, setSending] = useState(false);
  const [accountPassword, setAccountPassword] = useState('');
  const selected = slot.contacts.find(contact => contact.id === slot.selectedClientId) || null;
  const messages = selected ? slot.messagesByClient[selected.id] || [] : [];
  const visibleContacts = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    if (!term) return slot.contacts;
    return slot.contacts.filter(contact => contact.name.toLocaleLowerCase().includes(term));
  }, [slot.contacts, search]);

  const submit = async () => {
    const text = draft.trim();
    if (!selected || !text || sending) return;
    setSending(true);
    setDraft('');
    try {
      await onSendMessage(selected.id, text);
    } finally {
      setSending(false);
    }
  };

  const attach = async () => {
    if (!selected) return;
    const selectedPath = await open({ multiple: false, directory: false });
    if (typeof selectedPath === 'string') {
      await onSendFile(selected.id, selectedPath);
    }
  };

  const accountName = slot.assignment?.display_name?.trim() || `${platform === 'telegram' ? 'Telegram' : 'WhatsApp'} ${slot.index}`;
  const connected = slot.status === 'connected';

  return (
    <section className="account-panel">
      <header className="account-header">
        <div className="account-title-wrap">
          <span className={`platform-mark ${platform}`} aria-hidden="true">
            {platform === 'telegram' ? 'T' : 'W'}
          </span>
          <div className="min-w-0">
            <h2 title={accountName}>{accountName}</h2>
            <p><span className={`status-dot ${slot.status}`} />{slot.statusMessage}</p>
          </div>
        </div>
        {slot.assignment && !connected && (
          <button className="small-action" onClick={onConnect} disabled={slot.status === 'pending'}>
            Connect
          </button>
        )}
      </header>

      {!slot.assignment ? (
        <div className="account-empty">
          <strong>Account {slot.index} is not assigned</strong>
          <span>Add a {platform} assignment in the admin panel.</span>
        </div>
      ) : slot.passwordRequired ? (
        <div className="qr-stage">
          <strong>Telegram two-step verification</strong>
          <span>Enter the account password to finish linking. It is sent only to the local Telegram runtime.</span>
          <input
            className="account-password"
            type="password"
            value={accountPassword}
            onChange={event => setAccountPassword(event.target.value)}
            placeholder="Two-step verification password"
            aria-label="Telegram two-step verification password"
          />
          <button className="small-action" disabled={!accountPassword} onClick={() => void onSubmitPassword(accountPassword).then(() => setAccountPassword(''))}>
            Continue
          </button>
        </div>
      ) : slot.qrCode ? (
        <div className="qr-stage">
          <div className="qr-card"><img src={slot.qrCode} alt={`Scan to link ${accountName}`} /></div>
          <strong>Scan with {platform === 'telegram' ? 'Telegram' : 'WhatsApp'}</strong>
          <span>The account number remains hidden from staff.</span>
        </div>
      ) : (
        <div className="account-body">
          <aside className="contact-column">
            <div className="contact-search">
              <input
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Search approved names"
                aria-label="Search approved contacts"
              />
            </div>
            <div className="contact-list">
              {visibleContacts.map(contact => (
                <button
                  key={contact.id}
                  className={`contact-row ${selected?.id === contact.id ? 'active' : ''}`}
                  onClick={() => onSelectContact(contact.id)}
                >
                  <span className="contact-avatar">{contact.name.charAt(0).toUpperCase() || '?'}</span>
                  <span className="contact-copy">
                    <strong>{contact.name}</strong>
                    <small>{contact.lastMessage || 'Approved contact'}</small>
                  </span>
                  {!!contact.unreadCount && <span className="unread-badge">{contact.unreadCount}</span>}
                </button>
              ))}
              {visibleContacts.length === 0 && (
                <div className="no-contacts">No approved contacts for this account.</div>
              )}
            </div>
          </aside>

          <main className="chat-column">
            {selected ? (
              <>
                <div className="chat-header">
                  <span className="contact-avatar large">{selected.name.charAt(0).toUpperCase() || '?'}</span>
                  <div><strong>{selected.name}</strong><small>Number protected</small></div>
                </div>
                <div className="message-list">
                  {messages.map(message => (
                    <div key={message.id} className={`message-row ${message.fromMe ? 'sent' : 'received'}`}>
                      <div className="message-bubble">
                        {message.mediaType === 'image' && message.mediaData && (
                          <img className="message-image" src={message.mediaData} alt="Received attachment" />
                        )}
                        {message.mediaType === 'audio' && message.mediaData && (
                          <audio controls src={message.mediaData} />
                        )}
                        <span>{messageText(message)}</span>
                        <time>{formatTime(message.timestamp)}</time>
                      </div>
                    </div>
                  ))}
                  {messages.length === 0 && <div className="empty-chat">No messages loaded yet.</div>}
                </div>
                <div className="composer">
                  <button className="icon-action" onClick={attach} title="Attach file" aria-label="Attach file">＋</button>
                  <textarea
                    value={draft}
                    onChange={event => setDraft(event.target.value)}
                    onKeyDown={event => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        void submit();
                      }
                    }}
                    placeholder="Type a message"
                    rows={1}
                  />
                  <button className="send-action" onClick={() => void submit()} disabled={!draft.trim() || sending}>Send</button>
                </div>
              </>
            ) : (
              <div className="select-chat"><strong>Select an approved contact</strong><span>Client numbers are never displayed.</span></div>
            )}
          </main>
        </div>
      )}
    </section>
  );
}
