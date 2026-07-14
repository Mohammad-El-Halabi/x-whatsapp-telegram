import { useCallback, useEffect, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { PlatformEvent } from '../types';

export function usePlatformBridge(onEvent: (event: PlatformEvent) => void) {
  const handlerRef = useRef(onEvent);
  useEffect(() => { handlerRef.current = onEvent; }, [onEvent]);

  useEffect(() => {
    const subscription = listen<PlatformEvent>('platform:event', event => {
      handlerRef.current(event.payload);
    });
    return () => { subscription.then(unlisten => unlisten()); };
  }, []);

  return {
    connectWhatsApp: useCallback((slotId: string, assignmentId: string, gatewayNumber: string) =>
      invoke('whatsapp_connect', { slotId, assignmentId, gatewayNumber }), []),
    disconnectWhatsApp: useCallback((slotId: string) =>
      invoke('whatsapp_disconnect', { slotId }), []),
    getWhatsAppChats: useCallback((slotId: string) =>
      invoke('whatsapp_get_chats', { slotId }), []),
    getWhatsAppMessages: useCallback((slotId: string, clientId: string) =>
      invoke('whatsapp_get_messages', { slotId, clientId }), []),
    sendWhatsAppMessage: useCallback((slotId: string, clientId: string, message: string) =>
      invoke('whatsapp_send_message', { slotId, clientId, message }), []),
    sendWhatsAppFile: useCallback((slotId: string, clientId: string, filePath: string, caption?: string) =>
      invoke('whatsapp_send_file', { slotId, clientId, filePath, caption: caption || null }), []),
    markWhatsAppRead: useCallback((slotId: string, clientId: string) =>
      invoke('whatsapp_mark_read', { slotId, clientId }), []),
    connectTelegram: useCallback((slotId: string, assignmentId: string) =>
      invoke('telegram_connect', { slotId, assignmentId }), []),
    submitTelegramPassword: useCallback((slotId: string, password: string) =>
      invoke('telegram_submit_password', { slotId, password }), []),
    disconnectTelegram: useCallback((slotId: string) =>
      invoke('telegram_disconnect', { slotId }), []),
    getTelegramMessages: useCallback((slotId: string, clientId: string) =>
      invoke('telegram_get_messages', { slotId, clientId }), []),
    markTelegramRead: useCallback((slotId: string, clientId: string) =>
      invoke('telegram_mark_read', { slotId, clientId }), []),
    sendTelegramMessage: useCallback((slotId: string, clientId: string, message: string) =>
      invoke('telegram_send_message', { slotId, clientId, message }), []),
    sendTelegramFile: useCallback((slotId: string, clientId: string, filePath: string, caption?: string) =>
      invoke('telegram_send_file', { slotId, clientId, filePath, caption: caption || null }), []),
    disconnectAll: useCallback(async () => {
      await Promise.allSettled([
        invoke('whatsapp_disconnect_all'),
        invoke('telegram_disconnect_all'),
      ]);
    }, []),
  };
}
