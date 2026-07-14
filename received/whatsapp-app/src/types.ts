export interface User {
  id: string;
  email?: string;
  [key: string]: any;
}

export interface Assignment {
  id: string;
  gateway_number?: string;
  phone_number?: string;
  display_name?: string;
  connection_status?: string;
  platform?: string;
  user_id?: string;
  staff_id?: string;
  [key: string]: any;
}

export interface Chat {
  id: string;
  name?: string;
  isGroup?: boolean;
  unreadCount?: number;
  lastMessage?: { body: string; timestamp: number; fromMe?: boolean; type?: string };
  pinned?: boolean;
  archived?: boolean;
  isMuted?: boolean;
  isClientOnly?: boolean;
}

export interface Message {
  id: string;
  body: string;
  timestamp: number;
  from: string;
  to: string;
  fromMe: boolean;
  type?: string;
  hasMedia?: boolean;
  mediaType?: 'image' | 'video' | 'audio' | 'document' | null;
  mediaData?: string | null;
  caption?: string | null;
  ack?: number;
  quotedMsg?: { body: string; from: string } | null;
}

export interface Client {
  id: string;
  masked_identity?: string;
  full_name?: string;
  real_identifier?: string;
  platform_identifiers?: { whatsapp?: string };
  [key: string]: any;
}

export interface ContactStatus {
  isOnline: boolean;
  lastSeen: number | null;
  isTyping?: boolean;
}

export interface Toast {
  message: string;
  type: 'success' | 'error' | 'info';
}
