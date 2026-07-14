'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import type { Chat, Client, User } from '../types';
import Dock from './Dock';

function VoicePlayer({ src, fromMe }: { src: string; fromMe: boolean }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loadError, setLoadError] = useState(false);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !src) return;
    if (playing) { audio.pause(); } else { audio.play().catch(() => setLoadError(true)); }
  }, [playing, src]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => { setProgress(audio.currentTime); };
    const onLoaded = () => { setDuration(audio.duration || 0); };
    const onEnd = () => { setPlaying(false); setProgress(0); };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onError = () => setLoadError(true);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onLoaded);
    audio.addEventListener('ended', onEnd);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('error', onError);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onLoaded);
      audio.removeEventListener('ended', onEnd);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('error', onError);
    };
  }, []);

  const formatDur = (s: number) => {
    if (!s || !isFinite(s)) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const pct = duration > 0 ? (progress / duration) * 100 : 0;
  const barHeights = [4, 8, 12, 6, 14, 10, 5, 13, 7, 11, 4, 9, 15, 8, 6, 12, 10, 5, 14, 7, 11, 4, 8, 13, 6, 10, 15, 9, 5, 12, 7, 11, 4, 8, 14, 6];

  if (!src || loadError) {
    return (
      <div className="flex items-center gap-2.5 min-w-[200px]">
        <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0" style={{ background: fromMe ? '#009688' : '#00A884' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><polygon points="6,3 20,12 6,21"/></svg>
        </div>
        <span className="text-xs text-text-secondary">{loadError ? 'Audio unavailable' : 'Voice message'}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5 min-w-[200px]">
      <audio ref={audioRef} src={src} preload="metadata" />
      <button onClick={togglePlay} className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 border-none cursor-pointer" style={{ background: fromMe ? '#009688' : '#00A884' }}>
        {playing ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><polygon points="6,3 20,12 6,21"/></svg>
        )}
      </button>
      <div className="flex-1 flex flex-col gap-1.5 min-w-0">
        <div className="flex items-end gap-[2px] h-5">
          {barHeights.map((h, i) => {
            const barPct = (i / barHeights.length) * 100;
            const isActive = barPct <= pct;
            return (
              <div
                key={i}
                className="w-[3px] rounded-full transition-colors duration-150"
                style={{
                  height: `${h}px`,
                  opacity: isActive ? 1 : 0.35,
                  background: isActive ? (fromMe ? '#009688' : '#00A884') : '#8696A0',
                }}
              />
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={progress}
            onChange={(e) => { const a = audioRef.current; if (a) a.currentTime = Number(e.target.value); }}
            className="flex-1 h-1 rounded-full appearance-none cursor-pointer"
            style={{ background: `linear-gradient(to right, ${fromMe ? '#009688' : '#00A884'} ${pct}%, #d1d7db ${pct}%)` }}
          />
          <span className="text-[10px] tabular-nums shrink-0 text-text-secondary">{formatDur(progress)}</span>
        </div>
      </div>
    </div>
  );
}

interface ChatScreenProps {
  user: User | null;
  isWhatsAppConnected: boolean;
  connectionStatus: string;
  connectionMessage: string;
  chats: Chat[];
  clients: Client[];
  whatsapp: any;
  addListener: (type: any, callback: Function) => () => void;
  onStartCall?: (number: string, name: string, isVideo: boolean) => void;
  clearUnread: (chatId: string) => void;
}

export default function ChatScreen({
  user,
  isWhatsAppConnected,
  connectionStatus,
  connectionMessage,
  chats,
  clients,
  whatsapp,
  addListener,
  clearUnread,
}: ChatScreenProps) {
  const [currentChat, setCurrentChat] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [messageInput, setMessageInput] = useState('');
  const [showChatMenu, setShowChatMenu] = useState(false);
  const [contactStatus, setContactStatus] = useState({ isOnline: false, lastSeen: null as number | null, isTyping: false });
  const [messages, setMessages] = useState<any[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentChatRef = useRef<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);

  useEffect(() => { currentChatRef.current = currentChat; }, [currentChat]);

  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const normalizeId = (id: string | null | undefined) =>
    (id || '').split('@')[0].split(':')[0].replace(/\D/g, '');

  useEffect(() => {
    const cleanups = [
      addListener('messages', (msgs: any[]) => {
        const chatId = currentChatRef.current;
        if (chatId) {
          setMessages(msgs);
          setLoadingMessages(false);
        }
      }),
      addListener('new-message', (msg: any) => {
        const chatId = msg.fromMe ? msg.to : msg.from;
        const normalizedChat = normalizeId(chatId);
        const normalizedCurrent = normalizeId(currentChatRef.current);
        if (normalizedChat === normalizedCurrent) {
          setMessages(prev => {
            if (prev.some(m => m.id === msg.id)) return prev;
            return [...prev, msg];
          });
        }
      }),
      addListener('message-sent', (msg: any) => {
        if (normalizeId(msg.to) === normalizeId(currentChatRef.current)) {
          setMessages(prev => {
            if (prev.some(m => m.id === msg.id)) return prev;
            return [...prev, { ...msg, fromMe: true }];
          });
        }
      }),
      addListener('message-ack', (data: any) => {
        setMessages(prev => prev.map(m => m.id === data.id ? { ...m, ack: data.ack } : m));
      }),
      addListener('presence', (data: any) => {
        if (data && (normalizeId(data.number) === normalizeId(currentChatRef.current) || data.id === currentChatRef.current)) {
          setContactStatus({ isOnline: !!data.isOnline, lastSeen: data.lastSeen ?? null, isTyping: !!data.isTyping });
        }
      }),
    ];
    return () => cleanups.forEach(c => { if (typeof c === 'function') c(); });
  }, []);

  // Close chat menu on outside click
  useEffect(() => {
    if (!showChatMenu) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-chat-menu]')) {
        setShowChatMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showChatMenu]);

  const allItems = [...chats.filter(c => c.id !== 'status@broadcast')];
  const clientsWithoutChat = clients.filter(c => {
    const phone = (c.platform_identifiers?.whatsapp || '').replace(/\D/g, '');
    return phone && !chats.some(chat => {
      const chatNum = normalizeId(chat.id);
      return chatNum === phone || chatNum.endsWith(phone) || phone.endsWith(chatNum);
    });
  });
  for (const c of clientsWithoutChat) {
    const phone = (c.platform_identifiers?.whatsapp || '').replace(/\D/g, '');
    const displayName = c.masked_identity || c.full_name || 'Unknown';
    allItems.push({
      id: `${phone}@c.us`,
      name: displayName,
      isGroup: false,
      unreadCount: 0,
      lastMessage: { body: 'No messages', timestamp: 0, fromMe: false },
      pinned: false,
      archived: false,
      isMuted: false,
      isClientOnly: true,
    });
  }

  const currentChatData = allItems.find(c => c.id === currentChat);
  const currentChatMessages = currentChat ? messages : [];

  const sortedChats = [...allItems].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return (b.lastMessage?.timestamp || 0) - (a.lastMessage?.timestamp || 0);
  });

  const filteredChats = sortedChats.filter(chat => {
    if (searchQuery && chat.name && !chat.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const initials = user?.email?.charAt(0).toUpperCase() || 'S';
  const unreadCount = chats.filter(c => c.unreadCount && c.unreadCount > 0).length;

  const selectChat = useCallback((chatId: string) => {
    setCurrentChat(chatId);
    setMessages([]);
    setLoadingMessages(true);
    setShowChatMenu(false);
    setContactStatus({ isOnline: false, lastSeen: null, isTyping: false });
    const chat = allItems.find(c => c.id === chatId);
    if (chat && !(chat as any).isClientOnly) {
      whatsapp.getMessages(chatId);
      const number = normalizeId(chatId);
      if (number) whatsapp.getStatus(number);
      if (chat.unreadCount) {
        whatsapp.markAsRead(chatId);
        clearUnread(chatId);
      }
    } else {
      setLoadingMessages(false);
    }
  }, [allItems, whatsapp, clearUnread]);

  const sendMessage = () => {
    if (!messageInput.trim() || !currentChat) return;
    whatsapp.sendMessage(currentChat, messageInput.trim());
    setMessageInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (ts: number) => {
    if (!ts) return '';
    const date = new Date(ts * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000) return date.toLocaleDateString([], { weekday: 'short' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const formatTimestamp = (ts: number) => {
    if (!ts) return '';
    const date = new Date(ts * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff < 172800000) return 'Yesterday';
    if (diff < 604800000) return date.toLocaleDateString([], { weekday: 'short' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const getStatusIcon = (ack?: number) => {
    if (ack === undefined || ack === null || ack === 0 || ack === 1) {
      return <svg viewBox="0 0 16 11" className="w-4 h-4"><path d="M11.071.653a.457.457 0 00-.304-.102.493.493 0 00-.381.178l-6.19 7.636-2.011-2.175a.463.463 0 00-.647-.012.461.461 0 00-.012.647l2.37 2.562a.457.457 0 00.332.147h.015a.456.456 0 00.342-.194l6.54-8.071a.447.447 0 00-.055-.615z" fill="currentColor"/></svg>;
    }
    if (ack === 2) {
      return <svg viewBox="0 0 16 11" className="w-4 h-4"><path d="M11.071.653a.457.457 0 00-.304-.102.493.493 0 00-.381.178l-6.19 7.636-2.011-2.175a.463.463 0 00-.647-.012.461.461 0 00-.012.647l2.37 2.562a.457.457 0 00.332.147h.015a.456.456 0 00.342-.194l6.54-8.071a.447.447 0 00-.055-.615z" fill="currentColor"/><path d="M15.071.653a.457.457 0 00-.304-.102.493.493 0 00-.381.178l-6.19 7.636-1.19-1.288-.468.577 1.19 1.288a.457.457 0 00.332.147h.015a.456.456 0 00.342-.194l6.54-8.071a.447.447 0 00-.055-.615z" fill="currentColor"/></svg>;
    }
    return <svg viewBox="0 0 16 11" className="w-4 h-4 text-status-blue"><path d="M11.071.653a.457.457 0 00-.304-.102.493.493 0 00-.381.178l-6.19 7.636-2.011-2.175a.463.463 0 00-.647-.012.461.461 0 00-.012.647l2.37 2.562a.457.457 0 00.332.147h.015a.456.456 0 00.342-.194l6.54-8.071a.447.447 0 00-.055-.615z" fill="currentColor"/><path d="M15.071.653a.457.457 0 00-.304-.102.493.493 0 00-.381.178l-6.19 7.636-1.19-1.288-.468.577 1.19 1.288a.457.457 0 00.332.147h.015a.456.456 0 00.342-.194l6.54-8.071a.447.447 0 00-.055-.615z" fill="currentColor"/></svg>;
  };

  const handleAttach = async () => {
    if (!currentChat) return;
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'All Files', extensions: ['*'] }],
      });
      if (selected) {
        const filePath = String(selected);
        if (filePath) {
          await whatsapp.sendFile(currentChat, String(filePath));
        }
      }
    } catch (err) {
      console.error('File select error:', err);
    }
  };

  const startRecording = async () => {
    if (!currentChat) return;
    const targetChat = currentChat;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = mediaRecorder;
      recordingChunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordingChunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        if (recordingChunksRef.current.length === 0) return;
        const blob = new Blob(recordingChunksRef.current, { type: 'audio/webm' });
        recordingChunksRef.current = [];
        try {
          const arrayBuffer = await blob.arrayBuffer();
          const uint8 = new Uint8Array(arrayBuffer);
          let binary = '';
          for (let i = 0; i < uint8.length; i++) {
            binary += String.fromCharCode(uint8[i]);
          }
          const base64 = btoa(binary);
          await whatsapp.sendAudio(targetChat, base64, blob.type || 'audio/webm');
        } catch (err) {
          console.error('Voice send error:', err);
        }
      };
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      recordingTimerRef.current = setInterval(() => setRecordingTime(t => t + 1), 1000);
    } catch (err) {
      console.error('Microphone error:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setRecordingTime(0);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentChatMessages]);

  const connStatusColor = isWhatsAppConnected ? 'bg-success' : connectionStatus === 'pending' ? 'bg-warning' : 'bg-text-muted';

  return (
    <div className="flex h-[calc(100vh-32px)]">
      <Dock unreadCount={unreadCount} currentUserInitial={initials} />

      {/* Chats Sidebar */}
      <div className="flex flex-col w-[30%] min-w-[300px] max-w-[420px] bg-bg-secondary border-r border-border">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between px-4 h-[59px] border-b border-border">
          <h1 className="text-[16px] font-semibold text-text-primary">Chats</h1>
          <div className="flex items-center gap-1">
            <button className="w-10 h-10 border-none bg-transparent text-text-secondary cursor-pointer rounded-full flex items-center justify-center hover:bg-bg-hover transition-all">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </button>
            <div className="relative">
              <button className="w-10 h-10 border-none bg-transparent text-text-secondary cursor-pointer rounded-full flex items-center justify-center hover:bg-bg-hover transition-all">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
              </button>
            </div>
          </div>
        </div>

        {/* Search Bar */}
        <div className="px-3 py-2">
          <div className="relative">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search or start new chat"
              className="w-full pl-10 pr-4 py-[7px] bg-bg-tertiary border-none rounded-lg text-[14px] text-text-primary focus:outline-none placeholder:text-text-muted"
            />
          </div>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto">
          {filteredChats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-text-muted text-sm">
              <p>No chats found</p>
            </div>
          ) : (
            filteredChats.map(chat => {
              const isActive = currentChat === chat.id;
              const hasUnread = !!chat.unreadCount;
              const chatNumber = normalizeId(chat.id);
              const isTyping = contactStatus.isTyping && chat.id === currentChat;
              const lastMsgBody = chat.lastMessage?.body || '';
              const shouldShowLastMsg = !(chatNumber && lastMsgBody.includes(chatNumber));
              return (
                <div
                  key={chat.id}
                  onClick={() => selectChat(chat.id)}
                  className={`flex items-center gap-3 px-4 py-[9px] cursor-pointer transition-all border-l-[3px] ${
                    isActive ? 'bg-bg-hover border-l-accent' : 'bg-bg-secondary border-l-transparent hover:bg-bg-hover'
                  }`}
                >
                  <div className="relative w-[49px] h-[49px] shrink-0">
                    <div className="w-[49px] h-[49px] rounded-full bg-bg-tertiary flex items-center justify-center text-lg text-text-secondary">
                      {chat.isGroup ? (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" opacity="0.5"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
                      ) : (chat.name ? chat.name.charAt(0).toUpperCase() : '?')}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[16px] font-normal text-text-primary truncate">{chat.name || 'Unknown'}</span>
                      {(chat as any).isClientOnly && <span className="text-[10px] bg-accent/20 text-accent px-1.5 py-0.5 rounded-full shrink-0">Client</span>}
                    </div>
                    <div className="flex items-center gap-1 text-sm">
                      {contactStatus.isTyping && chat.id === currentChat ? (
                        <span className="text-accent">typing...</span>
                      ) : (
                        <>
                          {chat.lastMessage?.fromMe && <span className="text-text-muted shrink-0">You: </span>}
                          <span className={`truncate ${hasUnread && !isActive ? 'text-text-primary font-medium' : 'text-text-secondary'}`}>
                            {shouldShowLastMsg ? lastMsgBody || (chat.lastMessage?.type === 'image' ? 'Photo' : chat.lastMessage?.type === 'video' ? 'Video' : chat.lastMessage?.type === 'audio' ? 'Voice message' : chat.lastMessage?.type === 'document' ? 'Document' : '') : ''}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className="text-[12px] text-text-muted">{formatTimestamp(chat.lastMessage?.timestamp || 0)}</span>
                    <div className="flex items-center gap-1">
                      {chat.pinned && (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-text-muted"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2z"/></svg>
                      )}
                      {hasUnread && (
                        <span className="bg-accent-green text-white text-[11px] font-bold px-[5px] py-[1px] rounded-full min-w-[20px] text-center leading-[18px]">{chat.unreadCount}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative overflow-hidden chat-wallpaper">
        {currentChat ? (
          <>
            {/* Chat Header */}
            <div className="flex items-center justify-between px-4 h-[59px] bg-bg-secondary border-b border-border">
              <div className="flex items-center gap-3">
                <div className="relative w-10 h-10">
                  <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center text-base text-text-secondary">
                    {currentChatData?.name?.charAt(0).toUpperCase() || '?'}
                  </div>
                  {contactStatus.isOnline && (
                    <div className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-bg-secondary bg-accent-green" />
                  )}
                </div>
                <div className="flex flex-col">
                  <span className="text-[16px] font-medium text-text-primary">{currentChatData?.name || 'Unknown'}</span>
                  <span className={`text-[13px] ${contactStatus.isOnline ? 'text-accent' : 'text-text-secondary'}`}>
                    {contactStatus.isTyping ? 'typing...' : contactStatus.isOnline ? 'online' : currentChatData && !(currentChatData as any).isClientOnly ? 'offline' : ''}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <div className="relative" data-chat-menu>
                  <button onClick={() => setShowChatMenu(!showChatMenu)} className="w-10 h-10 border-none bg-transparent text-text-secondary cursor-pointer rounded-full flex items-center justify-center hover:bg-bg-hover transition-all">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
                  </button>
                  {showChatMenu && (
                    <div className="absolute right-0 top-full bg-bg-secondary border border-border rounded-lg p-1 min-w-[200px] z-[100] shadow-[0_4px_12px_rgba(0,0,0,0.15)]">
                      <button onClick={() => { whatsapp.markAsRead(currentChat); setShowChatMenu(false); }} className="w-full px-4 py-2.5 border-none bg-transparent text-text-primary text-[14px] text-left cursor-pointer rounded hover:bg-bg-hover transition-all flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Mark as Read
                      </button>
                      <button onClick={() => { whatsapp.pinChat(currentChat); setShowChatMenu(false); }} className="w-full px-4 py-2.5 border-none bg-transparent text-text-primary text-[14px] text-left cursor-pointer rounded hover:bg-bg-hover transition-all flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2z"/></svg> Pin Chat
                      </button>
                      <button onClick={() => { whatsapp.muteChat(currentChat); setShowChatMenu(false); }} className="w-full px-4 py-2.5 border-none bg-transparent text-text-primary text-[14px] text-left cursor-pointer rounded hover:bg-bg-hover transition-all flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12"/><path d="M8 8v3a4 4 0 008 0V8"/><path d="M4 10v1a8 8 0 0016 0v-1"/><path d="M2 21h20"/></svg> Mute Notifications
                      </button>
                      <button onClick={() => { whatsapp.archiveChat(currentChat); setShowChatMenu(false); }} className="w-full px-4 py-2.5 border-none bg-transparent text-text-primary text-[14px] text-left cursor-pointer rounded hover:bg-bg-hover transition-all flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg> Archive
                      </button>
                      <div className="h-px bg-border my-1" />
                      <button onClick={() => { whatsapp.deleteChat(currentChat); setShowChatMenu(false); setCurrentChat(null); }} className="w-full px-4 py-2.5 border-none bg-transparent text-danger text-[14px] text-left cursor-pointer rounded hover:bg-bg-hover transition-all flex items-center gap-3">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg> Delete Chat
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-14 py-4 flex flex-col">
              <div className="flex-1" />
              {loadingMessages && currentChatMessages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="animate-spin-slow mb-4">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" fill="#00A884" opacity="0.5"/>
                    <path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.37 0-4.567-.82-6.293-2.192l-.44-.36-2.893.967.967-2.893-.36-.44A9.935 9.935 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z" fill="#00A884" opacity="0.3"/>
                  </svg>
                  <p className="text-text-muted text-sm">Loading messages...</p>
                </div>
              ) : currentChatMessages.length === 0 ? (
                <div className="text-center text-text-muted text-sm py-8">No messages yet. Send a message to start the conversation.</div>
              ) : (
                currentChatMessages.map((msg, i) => {
                  const msgDate = new Date(msg.timestamp * 1000).toLocaleDateString();
                  const prevMsg = i > 0 ? currentChatMessages[i - 1] : null;
                  const prevDate = prevMsg ? new Date(prevMsg.timestamp * 1000).toLocaleDateString() : '';
                  const showDate = msgDate !== prevDate;
                  return (
                    <div key={msg.id}>
                      {showDate && (
                        <div className="flex justify-center py-2">
                          <span className="bg-bg-tertiary shadow-sm text-text-secondary text-[12px] px-3 py-1 rounded-lg">
                            {new Date(msg.timestamp * 1000).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                          </span>
                        </div>
                      )}
                      <div className={`flex ${msg.fromMe ? 'justify-end' : 'justify-start'} mb-[2px]`}>
                        <div className={`relative flex flex-col max-w-[65%] min-w-[100px] px-[9px] py-[5px] rounded-lg ${
                          msg.fromMe ? 'bg-msg-out rounded-br-sm' : 'bg-msg-in rounded-bl-sm'
                        } shadow-sm`}>
                          {/* Document attachment block */}
                          {msg.mediaType === 'document' && (
                            <div className="flex items-center gap-3 px-1 py-1.5 rounded-lg min-w-[240px]">
                              <div className="w-10 h-10 rounded flex items-center justify-center shrink-0" style={{ background: msg.fromMe ? '#D9FDD3' : '#E9EDEF' }}>
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={msg.fromMe ? '#009688' : '#667781'} strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-[14px] font-medium text-primary truncate">{msg.body || 'Document'}</div>
                                <div className="text-[12px] text-text-muted">{msg.fileSize || 'File'}</div>
                              </div>
                              <button className="w-8 h-8 border-none bg-transparent cursor-pointer rounded-full flex items-center justify-center hover:bg-black/5 transition-all">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={msg.fromMe ? '#009688' : '#00A884'} strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                              </button>
                            </div>
                          )}
                          {/* Image */}
                          {msg.mediaType === 'image' && msg.mediaData && (
                            <div className="mb-0.5">
                              <img src={msg.mediaData} alt="image" className="max-w-[320px] max-h-[400px] rounded-lg cursor-pointer object-cover" />
                            </div>
                          )}
                          {msg.mediaType === 'image' && !msg.mediaData && (
                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg mb-0.5" style={{ background: msg.fromMe ? '#D9FDD3' : '#E9EDEF' }}>
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                              <span className="text-sm">Photo</span>
                            </div>
                          )}
                          {/* Video */}
                          {msg.mediaType === 'video' && (
                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg mb-0.5" style={{ background: msg.fromMe ? '#D9FDD3' : '#E9EDEF' }}>
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                              <span className="text-sm">Video</span>
                            </div>
                          )}
                          {/* Audio */}
                          {msg.mediaType === 'audio' && msg.mediaData && (
                            <div className="mb-0.5">
                              <VoicePlayer src={msg.mediaData} fromMe={msg.fromMe} />
                            </div>
                          )}
                          {msg.mediaType === 'audio' && !msg.mediaData && (
                            <div className="flex items-center gap-2 mb-0.5">
                              <VoicePlayer src="" fromMe={msg.fromMe} />
                            </div>
                          )}
                          {/* Text body */}
                          {msg.caption && msg.mediaType !== 'image' && (
                            <div className="text-[14px] leading-[19px] whitespace-pre-wrap break-words text-text-primary px-0.5">{msg.caption}</div>
                          )}
                          {!msg.mediaType && (
                            <div className="text-[14px] leading-[19px] whitespace-pre-wrap break-words text-text-primary px-0.5">{msg.body}</div>
                          )}
                          {msg.mediaType === 'image' && msg.caption && (
                            <div className="text-[14px] leading-[19px] whitespace-pre-wrap break-words text-text-primary px-0.5 mt-0.5">{msg.caption}</div>
                          )}
                          {/* Timestamp + status */}
                          <div className="flex items-center justify-end gap-1 mt-0.5">
                            <span className="text-[11px]" style={{ color: msg.fromMe ? 'rgba(0,0,0,0.45)' : '#667781' }}>{formatTime(msg.timestamp)}</span>
                            {msg.fromMe && (
                              <span className="flex" style={{ color: (msg.ack && msg.ack >= 3) ? '#53BDEB' : 'rgba(0,0,0,0.45)' }}>
                                {getStatusIcon(msg.ack)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Message Input */}
            <div className="flex items-end gap-2 px-4 py-[10px] bg-bg-tertiary">
              <button onClick={handleAttach} className="w-11 h-11 border-none bg-transparent text-text-secondary cursor-pointer rounded-full flex items-center justify-center hover:bg-bg-hover transition-all shrink-0">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
              </button>
              {isRecording ? (
                <div className="flex-1 flex items-center gap-3 bg-bg-secondary rounded-lg px-3 py-[5px]">
                  <div className="w-3 h-3 rounded-full bg-danger animate-pulse" />
                  <span className="text-sm text-text-primary">{Math.floor(recordingTime / 60).toString().padStart(2, '0')}:{(recordingTime % 60).toString().padStart(2, '0')}</span>
                  <div className="flex-1" />
                  <button onClick={stopRecording} className="px-3 py-1 bg-accent text-white text-sm rounded-lg cursor-pointer border-none hover:bg-accent-hover transition-all">Send</button>
                </div>
              ) : (
                <div className="flex-1 bg-bg-secondary rounded-lg px-3 py-[5px]">
                  <textarea
                    value={messageInput}
                    onChange={e => setMessageInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message"
                    rows={1}
                    className="w-full bg-transparent border-none text-[15px] text-text-primary resize-none max-h-[120px] leading-[20px] focus:outline-none placeholder:text-text-muted"
                  />
                </div>
              )}
              {isRecording ? (
                <button onClick={stopRecording} className="w-11 h-11 border-none bg-danger cursor-pointer rounded-full flex items-center justify-center hover:bg-danger-hover transition-all shrink-0">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="white"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                </button>
              ) : messageInput.trim() ? (
                <button
                  onClick={sendMessage}
                  className="w-11 h-11 border-none bg-transparent cursor-pointer rounded-full flex items-center justify-center transition-all shrink-0"
                >
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="#00A884"><path d="M1.101 21.757L23.8 12.028 1.101 2.3l.011 7.912 13.623 1.816-13.623 1.817-.011 7.912z"/></svg>
                </button>
              ) : (
                <button
                  onClick={startRecording}
                  className="w-11 h-11 border-none bg-transparent text-text-secondary cursor-pointer rounded-full flex items-center justify-center hover:bg-bg-hover transition-all shrink-0"
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8"/></svg>
                </button>
              )}
            </div>
          </>
        ) : (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full bg-bg-secondary">
            <svg width="80" height="80" viewBox="0 0 24 24" fill="none" className="mb-6">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" fill="#00A884" opacity="0.3"/>
              <path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.37 0-4.567-.82-6.293-2.192l-.44-.36-2.893.967.967-2.893-.36-.44A9.935 9.935 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z" fill="#00A884" opacity="0.3"/>
            </svg>
            <h2 className="text-[28px] font-light text-text-primary mb-2">X-WhatsApp</h2>
            <p className="text-[14px] text-text-secondary text-center max-w-xs leading-relaxed">Send and receive messages from your staff WhatsApp</p>
            <p className="text-[13px] text-text-muted mt-4">Select a chat to start messaging</p>
          </div>
        )}
      </div>
    </div>
  );
}
