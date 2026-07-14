export type Platform = 'telegram' | 'whatsapp';

export interface User {
  id: string;
  email?: string;
  full_name?: string;
  office_id?: string | null;
  is_active?: boolean;
  [key: string]: unknown;
}

export interface Assignment {
  id: string;
  gateway_number?: string;
  display_name?: string;
  connection_status?: string;
  platform?: Platform | string;
  user_id?: string;
  staff_id?: string;
  [key: string]: unknown;
}

export interface SafeContact {
  id: string;
  name: string;
  unreadCount?: number;
  lastMessage?: string;
  lastTimestamp?: number;
}

export interface SafeMessage {
  id: string;
  clientId: string;
  clientName?: string;
  body: string;
  timestamp: number;
  fromMe: boolean;
  ack?: number;
  hasMedia?: boolean;
  mediaType?: 'image' | 'video' | 'audio' | 'document' | null;
  mediaData?: string | null;
  caption?: string | null;
}

export interface PlatformEvent {
  platform: Platform;
  slotId: string;
  event: string;
  data: any;
}

export interface AccountSlotState {
  slotId: string;
  index: number;
  assignment?: Assignment;
  contacts: SafeContact[];
  selectedClientId: string | null;
  messagesByClient: Record<string, SafeMessage[]>;
  status: 'unassigned' | 'disconnected' | 'pending' | 'connected' | 'error' | 'needs-link';
  statusMessage: string;
  qrCode: string | null;
  passwordRequired?: boolean;
}
