'use client';

import type { User, Assignment } from '../types';

interface ConnectionScreenProps {
  user: User | null;
  assignments: Assignment[];
  isWhatsAppConnected: boolean;
  connectionStatus: string;
  connectionMessage: string;
  qrCodeUrl: string | null;
  onConnect: (assignment?: Assignment) => void;
  onGoToChat?: () => void;
  isWhatsAppReady?: boolean;
}

export default function ConnectionScreen({
  user,
  assignments,
  isWhatsAppConnected,
  connectionStatus,
  connectionMessage,
  qrCodeUrl,
  onConnect,
  onGoToChat,
  isWhatsAppReady,
}: ConnectionScreenProps) {
  const gateway = assignments.length > 0 ? assignments[0] : null;

  const statusColor = isWhatsAppConnected ? 'bg-success' : connectionStatus === 'pending' ? 'bg-warning animate-pulse-dot' : connectionStatus === 'error' ? 'bg-danger' : 'bg-text-muted';
  const statusText = isWhatsAppConnected ? 'Connected' : connectionStatus === 'pending' ? (connectionMessage || 'Connecting...') : connectionStatus === 'error' ? (connectionMessage || 'Error') : 'Disconnected';

  const initials = user?.email?.charAt(0).toUpperCase() || 'S';

  return (
    <div className="flex flex-col w-full h-[calc(100vh-32px)] bg-bg-primary">
      <div className="flex items-center justify-between px-5 py-3 bg-bg-secondary border-b border-border min-h-14">
        <div className="flex items-center gap-2.5 text-sm font-medium">
          <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center font-semibold text-white text-sm">{initials}</div>
          <span className="text-text-primary">{user?.email || 'Staff'}</span>
        </div>
        <div />
      </div>

      <div className="flex-1 flex flex-col items-center py-10 px-5 overflow-y-auto gap-4 max-w-[480px] mx-auto w-full">
        <div className="w-full bg-bg-secondary border border-border rounded-xl p-5 text-center">
          <div className="mb-3">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" opacity="0.5" className="mx-auto">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </div>
          <h2 className="text-xl mb-1 text-text-primary">WhatsApp Connection</h2>
          <p className="text-text-secondary text-sm">Connect to WhatsApp from your device</p>
        </div>

        <div className="w-full bg-bg-secondary border border-border rounded-xl p-5">
          <div className="flex items-center justify-center gap-2.5 p-3.5 bg-bg-tertiary rounded-lg text-sm font-medium">
            <div className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
            <span className="text-text-primary">{statusText}</span>
          </div>
        </div>

        {isWhatsAppConnected && (
          <div className="w-full bg-bg-secondary border border-border rounded-xl p-5">
            <label className="block text-xs text-text-secondary mb-1.5 text-left">Gateway Number</label>
            <div className="p-2.5 bg-bg-tertiary rounded-lg text-[12px] text-left">
              {gateway?.gateway_number && (
                <div className="flex justify-between py-0.5"><span className="text-text-muted">Phone</span><span className="text-text-primary font-medium">{gateway.gateway_number}</span></div>
              )}
              {gateway?.display_name && (
                <div className="flex justify-between py-0.5"><span className="text-text-muted">Name</span><span className="text-text-primary font-medium">{gateway.display_name}</span></div>
              )}
              <div className="flex justify-between py-0.5"><span className="text-text-muted">Status</span><span className="text-text-primary font-medium">{statusText}</span></div>
            </div>
          </div>
        )}

        <div className="w-full bg-bg-secondary border border-border rounded-xl p-5">
          {isWhatsAppConnected ? (
            <div className="flex gap-3">
              {onGoToChat && (
                <button onClick={onGoToChat} className="w-full p-3.5 bg-accent text-white rounded-lg text-[15px] font-semibold cursor-pointer hover:bg-accent-hover transition-all">
                  Go to Chat
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={() => onConnect(gateway || undefined)}
              disabled={connectionStatus === 'pending'}
              className="w-full p-3.5 bg-accent text-white rounded-lg text-[15px] font-semibold cursor-pointer hover:bg-accent-hover transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {connectionStatus === 'pending' ? 'Connecting...' : 'Connect WhatsApp'}
            </button>
          )}
        </div>

        {qrCodeUrl && (
          <div className="w-full bg-bg-secondary border border-border rounded-xl p-5 text-center">
            <h3 className="text-sm mb-3 text-text-secondary">Scan QR Code</h3>
            <div className="bg-white p-3 rounded-lg mb-3">
              <img src={qrCodeUrl} alt="QR Code" className="w-full rounded-lg" style={{ maxWidth: 256, margin: '0 auto' }} />
            </div>
            <p className="text-[11px] text-text-secondary leading-snug">Open WhatsApp on your phone &gt; Settings &gt; Linked Devices &gt; Link a Device</p>
          </div>
        )}
      </div>
    </div>
  );
}
