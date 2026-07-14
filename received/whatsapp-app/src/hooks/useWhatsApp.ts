import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

type WhatsAppEventType =
  | 'qr'
  | 'authenticated'
  | 'ready'
  | 'disconnected'
  | 'error'
  | 'new-message'
  | 'message-sent'
  | 'message-ack'
  | 'status-change'
  | 'loading'
  | 'chats'
  | 'messages'
  | 'status'
  | 'presence'
  | 'debug';

interface WhatsAppEventData {
  event: string;
  data: any;
}

export function useWhatsApp() {
  const listenersRef = useRef<Map<string, Set<Function>>>(new Map());
  const [isConnected, setIsConnected] = useState(false);

  const addListener = useCallback((type: string, callback: Function) => {
    if (!listenersRef.current.has(type)) {
      listenersRef.current.set(type, new Set());
    }
    listenersRef.current.get(type)!.add(callback);
    return () => {
      listenersRef.current.get(type)?.delete(callback);
    };
  }, []);

  const emit = useCallback((type: string, ...args: any[]) => {
    listenersRef.current.get(type)?.forEach((cb) => {
      try { cb(...args); } catch (e) { console.error('[WhatsApp] listener error:', e); }
    });
  }, []);

  useEffect(() => {
    const unlisten = listen<WhatsAppEventData>('whatsapp:event', (event) => {
      const { event: eventType, data } = event.payload;
      if (eventType === 'ready') {
        setIsConnected(true);
      } else if (eventType === 'disconnected') {
        setIsConnected(false);
      }
      emit(eventType, data);
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, [emit]);

  const api = useMemo(() => ({
    connect: (config: { assignmentId: string; gatewayNumber: string }) => {
      return invoke('whatsapp_connect', {
        assignmentId: config.assignmentId,
        gatewayNumber: config.gatewayNumber,
      });
    },
    disconnect: () => {
      return invoke('whatsapp_disconnect');
    },
    sendMessage: (number: string, message: string) => {
      return invoke('whatsapp_send_message', { number, message });
    },
    sendFile: (number: string, filePath: string, caption?: string) => {
      return invoke('whatsapp_send_file', { number, filePath, caption: caption || null });
    },
    sendAudio: (number: string, base64: string, mimeType?: string) => {
      return invoke('whatsapp_send_audio', { number, base64, mimeType: mimeType || null });
    },
    getChats: () => {
      return invoke('whatsapp_get_chats');
    },
    getMessages: (chatId: string) => {
      return invoke('whatsapp_get_messages', { chatId });
    },
    getStatus: (number: string) => invoke('whatsapp_get_status', { number }),
    markAsRead: (chatId: string) => invoke('whatsapp_mark_read', { chatId }),
    archiveChat: (chatId: string) => invoke('whatsapp_archive_chat', { chatId }),
    deleteChat: (chatId: string) => invoke('whatsapp_delete_chat', { chatId }),
    pinChat: (chatId: string) => invoke('whatsapp_pin_chat', { chatId }),
    muteChat: (chatId: string) => invoke('whatsapp_mute_chat', { chatId }),
  }), []);

  return { api, isConnected, addListener };
}
