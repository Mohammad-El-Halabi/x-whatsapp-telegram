const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');
const os = require('os');

let client = null;
let isReady = false;
let gatewayNumber = null;
let currentAssignmentId = null;
let reconnecting = false;
let reconnectTimer = null;
let lidToPhone = {};
let phoneToName = {};

function send(event, data) {
  const msg = JSON.stringify({ event, data });
  process.stdout.write(msg + '\n');
  console.error(`[SIDECAR EVENT] ${event}`);
}

function findChrome() {
  const platform = os.platform();
  const candidates = [];

  if (platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA || '';
    const programFiles = process.env['PROGRAMFILES'] || 'C:\\Program Files';
    const programFilesX86 = process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)';

    candidates.push(
      path.join(programFiles, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(programFilesX86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(localAppData, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(os.homedir(), 'AppData', 'Local', 'Google', 'Chrome', 'Application', 'chrome.exe'),
      // Edge as fallback
      path.join(programFiles, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      path.join(programFilesX86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    );
  } else if (platform === 'darwin') {
    candidates.push(
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    );
  } else {
    candidates.push(
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/snap/bin/chromium',
    );
  }

  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) {
        console.error(`[SIDECAR] Found browser at: ${p}`);
        return p;
      }
    } catch {}
  }

  console.error('[SIDECAR] No browser found, letting Puppeteer use its bundled Chromium');
  return undefined;
}

function parseInput(line) {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

async function handleAction(action, data) {
  switch (action) {
    case 'connect':
      await initializeClient(data.assignmentId, data.gatewayNumber);
      break;
    case 'disconnect':
      reconnecting = false;
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      await destroyClient();
      break;
    case 'send-message':
      await sendMessage(data.number, data.message);
      break;
    case 'send-file':
      await sendFile(data.number, data.filePath, data.caption);
      break;
    case 'send-audio':
      await sendAudio(data.number, data.base64, data.mimeType);
      break;
    case 'get-chats':
      await getChats();
      break;
    case 'get-messages':
      await getMessages(data.chatId);
      break;
    case 'get-status':
      await getStatus(data.number);
      break;
    case 'mark-read':
      await markAsRead(data.chatId);
      break;
    case 'archive-chat':
      await archiveChat(data.chatId);
      break;
    case 'delete-chat':
      await deleteChat(data.chatId);
      break;
    case 'pin-chat':
      await pinChat(data.chatId);
      break;
    case 'mute-chat':
      await muteChat(data.chatId);
      break;
    default:
      send('error', { message: `Unknown action: ${action}` });
  }
}

async function initializeClient(assignmentId, gwNumber) {
  if (client) {
    await destroyClient();
  }

  gatewayNumber = gwNumber;
  currentAssignmentId = assignmentId;
  reconnecting = true;
  const userDataDir = path.join(os.homedir(), '.x-whatsapp-tauri', assignmentId || 'default');

  let loadTimeout = null;
  try {
    const chromePath = findChrome();
    const puppeteerConfig = {
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-extensions',
        '--no-first-run',
        '--no-zygote',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-breakpad',
        '--disable-client-side-phishing-detection',
        '--disable-default-apps',
        '--disable-domain-reliability',
        '--disable-hang-monitor',
        '--disable-ipc-flooding-protection',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--metrics-recording-only',
        '--no-default-browser-check',
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--enable-features=WebRtcHideLocalIpsWithMdns',
        '--autoplay-policy=no-user-gesture-required',
      ],
    };
    if (chromePath) {
      puppeteerConfig.executablePath = chromePath;
    }

    client = new Client({
      authStrategy: new LocalAuth({ dataPath: userDataDir }),
      webVersionCache: { type: 'local' },
      puppeteer: puppeteerConfig,
    });

    client.on('qr', async (qr) => {
      try {
        const dataUrl = await QRCode.toDataURL(qr, { width: 256, margin: 2 });
        send('qr', { qrData: dataUrl });
      } catch {
        send('qr', { qrData: qr });
      }
      send('status-change', { status: 'pending', message: 'Scan QR code with WhatsApp' });
    });

    client.on('authenticated', () => {
      send('authenticated', {});
    });

    client.on('auth_failure', (msg) => {
      send('error', { message: 'Auth failure: ' + msg });
    });

    client.on('ready', () => {
      isReady = true;
      const info = client.info;
      send('ready', { name: info.pushname, number: info.wid.user });
    });

    client.on('message', async (msg) => {
      if (msg.fromMe) return;
      let fromId = resolveLid(normalizeChatId(msg.from));
      let toId = resolveLid(normalizeChatId(msg.to));
      const fromPhone = fromId.split('@')[0].split(':')[0].replace(/\D/g, '');
      const fromName = phoneToName[fromPhone] || '';
      console.error(`[SIDECAR] message event received, fromMe=${msg.fromMe}`);
      const item = {
        id: msg.id._serialized,
        from: fromId,
        to: toId,
        fromName,
        body: msg.body,
        timestamp: msg.timestamp,
        fromMe: msg.fromMe,
        hasMedia: msg.hasMedia,
        type: msg.type,
        mediaType: null,
        mediaData: null,
        caption: null,
      };
      if (msg.hasMedia) {
        try {
          const media = await msg.downloadMedia();
          if (media && media.mimetype) {
            item.mediaType = media.mimetype.startsWith('image/') ? 'image'
              : media.mimetype.startsWith('video/') ? 'video'
              : media.mimetype.startsWith('audio/') ? 'audio'
              : 'document';
            if (media.data) {
              item.mediaData = `data:${media.mimetype};base64,${media.data}`;
            }
            if (msg.body) item.caption = msg.body;
          }
        } catch (e) {
        console.error('[SIDECAR] Media download failed for a new message');
          item.mediaType = msg.type;
        }
      }
      console.error(`[SIDECAR] forwarding approved message, fromMe=${item.fromMe}`);
      send('new-message', item);
    });

    client.on('message_create', async (msg) => {
      if (msg.fromMe) {
        let fromId = resolveLid(normalizeChatId(msg.from));
        let toId = resolveLid(normalizeChatId(msg.to));
        console.error('[SIDECAR] outgoing message event received');
        const item = {
          id: msg.id._serialized,
          from: fromId,
          to: toId,
          body: msg.body,
          timestamp: msg.timestamp,
          fromMe: true,
          hasMedia: msg.hasMedia,
          type: msg.type,
          mediaType: null,
          mediaData: null,
          caption: null,
        };
        if (msg.hasMedia) {
          try {
            const media = await msg.downloadMedia();
            if (media && media.mimetype) {
              item.mediaType = media.mimetype.startsWith('image/') ? 'image'
                : media.mimetype.startsWith('video/') ? 'video'
                : media.mimetype.startsWith('audio/') ? 'audio'
                : 'document';
              if (media.data) {
                item.mediaData = `data:${media.mimetype};base64,${media.data}`;
              }
              if (msg.body) item.caption = msg.body;
            }
          } catch (e) {
            console.error('[SIDECAR] Media download failed for a sent message');
            item.mediaType = msg.type;
          }
        }
        console.error('[SIDECAR] forwarding approved sent message');
        send('message-sent', item);
      }
    });

    client.on('message_ack', (msg, ack) => {
      send('message-ack', { id: msg.id._serialized, ack });
    });

    client.on('disconnected', (reason) => {
      isReady = false;
      send('disconnected', { reason });
      autoReconnect();
    });

    client.on('loading_screen', (percent, message) => {
      send('status-change', { status: 'pending', message: `Loading: ${percent}%` });
    });

    send('status-change', { status: 'pending', message: 'Initializing WhatsApp...' });
    
    loadTimeout = setTimeout(() => {
      if (!isReady) {
        send('error', { message: 'WhatsApp Web took too long to respond. Check that Chrome/Edge is installed.' });
      }
    }, 60000);

    await client.initialize();
    
    if (loadTimeout) clearTimeout(loadTimeout);
  } catch (err) {
    if (loadTimeout) clearTimeout(loadTimeout);
    send('error', { message: 'Failed to initialize: ' + err.message });
    autoReconnect();
  }
}

function autoReconnect() {
  if (!reconnecting) return;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  send('status-change', { status: 'pending', message: 'Reconnecting in 5s...' });
  reconnectTimer = setTimeout(async () => {
    reconnectTimer = null;
    if (!reconnecting) return;
    await destroyClient();
    await initializeClient(currentAssignmentId, gatewayNumber);
  }, 5000);
}

async function destroyClient() {
  if (client) {
    try {
      await client.destroy();
    } catch {}
    client = null;
    isReady = false;
  }
}

async function sendMessage(number, message) {
  number = normalizeChatId(number);
  console.error(`[SIDECAR] sendMessage called, isReady=${isReady}`);
  if (!isReady) return send('error', { message: 'WhatsApp not ready' });
  const chatId = number.includes('@c.us') ? number : `${number}@c.us`;
  try {
    console.error('[SIDECAR] routing approved outgoing message');
    await client.sendMessage(chatId, message);
    console.error(`[SIDECAR] sendMessage success`);
  } catch (err) {
    console.error('[SIDECAR] sendMessage failed');
    send('error', { message: err.message });
  }
}

async function sendFile(number, filePath, caption) {
  number = normalizeChatId(number);
  if (!isReady) return send('error', { message: 'WhatsApp not ready' });
  const chatId = number.includes('@c.us') ? number : `${number}@c.us`;
  try {
    const media = await MessageMedia.fromFilePath(filePath);
    const opts = caption ? { caption } : {};
    await client.sendMessage(chatId, media, opts);
  } catch (err) {
    send('error', { message: err.message });
  }
}

async function sendAudio(number, base64Data, mimeType) {
  number = normalizeChatId(number);
  if (!isReady) return send('error', { message: 'WhatsApp not ready' });
  const chatId = number.includes('@c.us') ? number : `${number}@c.us`;
  try {
    const media = new MessageMedia(mimeType || 'audio/ogg; codecs=opus', base64Data, 'voice-message.ogg');
    await client.sendMessage(chatId, media, { sendAudioAsVoice: true });
  } catch (err) {
    send('error', { message: err.message });
  }
}

function normalizeChatId(id) {
  if (!id) return id;
  if (id.endsWith('@s.whatsapp.net@c.us')) {
    return id.replace('@s.whatsapp.net@c.us', '@c.us');
  }
  if (id.endsWith('@s.whatsapp.net@g.us')) {
    return id.replace('@s.whatsapp.net@g.us', '@g.us');
  }
  if (!id.includes('@')) {
    const digits = String(id).replace(/\D/g, '');
    return digits ? `${digits}@c.us` : id;
  }
  return id;
}

function resolveLid(id) {
  if (id && id.endsWith('@lid') && lidToPhone[id]) {
    return lidToPhone[id] + '@c.us';
  }
  return id;
}

async function getChats() {
  console.error(`[SIDECAR] getChats called, isReady=${isReady}`);
  if (!isReady) return send('chats', []);
  try {
    const chats = await client.getChats();
    console.error(`[SIDECAR] getChats found ${chats.length} chats`);

    const nameToPhone = {};
    const localLidToPhone = {};
    try {
      const contacts = await client.getContacts();
      console.error(`[SIDECAR] getChats total contacts: ${contacts.length}`);
      for (const c of contacts) {
        const rawId = c.id ? c.id._serialized : '';
        const phone = c.number || '';
        const name = (c.name || c.pushname || '').toLowerCase().trim();
        if (rawId.endsWith('@c.us') && phone && name) {
          nameToPhone[name] = phone;
        }
        if (phone) {
          phoneToName[phone] = c.name || c.pushname || '';
        }
        if (rawId.endsWith('@lid') && phone) {
          localLidToPhone[rawId] = phone;
        }
      }
      lidToPhone = localLidToPhone;
      console.error(`[SIDECAR] getChats built nameToPhone=${Object.keys(nameToPhone).length}, lidToPhone=${Object.keys(lidToPhone).length}`);
      console.error('[SIDECAR] private contact map initialized');
    } catch (e) { console.error('[SIDECAR] private contact mapping failed'); }

    const results = [];
    for (const chat of chats) {
      let chatId = normalizeChatId(chat.id._serialized);
      if (chatId.endsWith('@lid') && !chat.isGroup) {
        if (lidToPhone[chatId]) {
          chatId = lidToPhone[chatId] + '@c.us';
          console.error('[SIDECAR] resolved a private chat identifier');
        } else {
          const chatName = (chat.name || '').toLowerCase().trim();
          if (chatName && nameToPhone[chatName]) {
            chatId = nameToPhone[chatName] + '@c.us';
            lidToPhone[oldId] = nameToPhone[chatName];
            console.error('[SIDECAR] resolved a private chat by approved display name');
          }
        }
      }
      results.push({
        id: chatId,
        name: chat.name,
        isGroup: chat.isGroup,
        unreadCount: chat.unreadCount,
        lastMessage: chat.lastMessage
          ? { body: chat.lastMessage.body, timestamp: chat.lastMessage.timestamp, fromMe: chat.lastMessage.fromMe, type: chat.lastMessage.type }
          : null,
        pinned: chat.pinned,
        archived: chat.archived,
        isMuted: chat.isMuted,
        timestamp: chat.timestamp,
      });
    }
    send('chats', results);
  } catch (err) {
    console.error('[SIDECAR] getChats failed');
    send('chats', []);
  }
}

async function getMessages(chatId, limit = 50) {
  const originalChatId = chatId;
  chatId = normalizeChatId(chatId);
  console.error(`[SIDECAR] getMessages called, isReady=${isReady}`);
  if (!isReady) return send('messages', []);
  try {
    let chat;
    try {
      chat = await client.getChatById(chatId);
      console.error('[SIDECAR] approved chat lookup succeeded');
    } catch (e) {
      console.error('[SIDECAR] approved chat lookup failed');
      console.error(`[SIDECAR] getMessages trying to find chat by iterating all chats...`);
      const allChats = await client.getChats();
      for (const c of allChats) {
        const cid = c.id ? c.id._serialized : '';
        const cDigits = cid.split('@')[0].split(':')[0].replace(/\D/g, '');
        if (cDigits === chatId.split('@')[0].split(':')[0].replace(/\D/g, '')) {
          chat = c;
          console.error('[SIDECAR] approved chat fallback matched');
          break;
        }
      }
      if (!chat) {
        console.error('[SIDECAR] approved chat was not found; trying safe fallback');
      }
    }
    if (!chat) {
      console.error(`[SIDECAR] getMessages sending empty messages - chat not found`);
      return send('messages', []);
    }
    const messages = await chat.fetchMessages({ limit });
    console.error(`[SIDECAR] getMessages found ${messages.length} messages`);
    if (messages.length > 0) {
      const m = messages[0];
      console.error(`[SIDECAR] getMessages first msg keys: ${Object.keys(m).join(', ')}`);
      console.error(`[SIDECAR] validating first message, fromMe=${m.fromMe}`);
      if (m.from === undefined) {
        console.error('[SIDECAR] message sender field is unavailable');
      }
    }

    const results = [];
    for (const msg of messages) {
      let fromId = '';
      let toId = '';
      if (msg.from && msg.from._serialized) {
        fromId = msg.from._serialized;
      } else if (msg._from) {
        fromId = typeof msg._from === 'string' ? msg._from : (msg._from._serialized || msg._from.toString());
      } else if (msg.author) {
        fromId = typeof msg.author === 'string' ? msg.author : (msg.author._serialized || '');
      } else if (msg.sender) {
        fromId = typeof msg.sender === 'string' ? msg.sender : (msg.sender._serialized || '');
      }
      if (msg.to && msg.to._serialized) {
        toId = msg.to._serialized;
      } else if (msg._to) {
        toId = typeof msg._to === 'string' ? msg._to : (msg._to._serialized || msg._to.toString());
      }
      if (!fromId && msg.id && msg.id.remote) {
        fromId = msg.fromMe ? chat.id._serialized : (typeof msg.id.remote === 'string' ? msg.id.remote : msg.id.remote._serialized || '');
      }
      if (!toId && msg.id && msg.id.remote) {
        toId = msg.fromMe ? (typeof msg.id.remote === 'string' ? msg.id.remote : msg.id.remote._serialized || '') : chat.id._serialized;
      }
      console.error(`[SIDECAR] processing approved message, fromMe=${msg.fromMe}`);
      const item = {
        id: msg.id._serialized,
        body: msg.body,
        timestamp: msg.timestamp,
        from: fromId,
        to: toId,
        fromMe: msg.fromMe,
        type: msg.type,
        hasMedia: msg.hasMedia,
        ack: msg.ack,
        mediaType: null,
        mediaData: null,
        caption: null,
      };

      if (msg.hasMedia) {
        try {
          const media = await msg.downloadMedia();
          if (media && media.mimetype) {
            item.mediaType = media.mimetype.startsWith('image/') ? 'image'
              : media.mimetype.startsWith('video/') ? 'video'
              : media.mimetype.startsWith('audio/') ? 'audio'
              : 'document';
            if (media.data) {
              item.mediaData = `data:${media.mimetype};base64,${media.data}`;
            }
            if (msg.body) item.caption = msg.body;
          }
        } catch (e) {
          console.error('[SIDECAR] Media download failed');
          item.mediaType = msg.type;
        }
      }

      results.push(item);
    }

    send('messages', results);
  } catch (err) {
    console.error('[SIDECAR] getMessages failed');
    send('messages', []);
  }
}

async function getStatus(number) {
  if (!isReady) return send('status', null);
  try {
    const contact = await client.getNumberId(number);
    if (!contact) return send('status', null);
    const chat = await client.getChatById(contact._serialized);
    send('status', {
      isOnline: chat.isOnline,
      lastSeen: chat.lastSeen,
      isTyping: chat.isTyping,
    });
  } catch {
    send('status', null);
  }
}

async function markAsRead(chatId) {
  chatId = normalizeChatId(chatId);
  if (!isReady) return;
  try {
    const chat = await client.getChatById(chatId);
    await chat.sendSeen();
  } catch {}
}

async function archiveChat(chatId) {
  chatId = normalizeChatId(chatId);
  if (!isReady) return;
  try {
    const chat = await client.getChatById(chatId);
    await chat.archive();
  } catch {}
}

async function deleteChat(chatId) {
  chatId = normalizeChatId(chatId);
  if (!isReady) return;
  try {
    const chat = await client.getChatById(chatId);
    await chat.delete();
  } catch {}
}

async function pinChat(chatId) {
  chatId = normalizeChatId(chatId);
  if (!isReady) return;
  try {
    const chat = await client.getChatById(chatId);
    await chat.pin();
  } catch {}
}

async function muteChat(chatId) {
  chatId = normalizeChatId(chatId);
  if (!isReady) return;
  try {
    const chat = await client.getChatById(chatId);
    await chat.mute();
  } catch {}
}

process.stdin.setEncoding('utf-8');
let buffer = '';

process.stdin.on('data', (chunk) => {
  buffer += chunk;
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
  const msg = parseInput(trimmed);
  if (msg && msg.action) {
      console.error(`[SIDECAR] action=${msg.action}`);
      handleAction(msg.action, msg.data || {});
    } else {
      console.error('[SIDECAR] invalid command received');
    }
  }
});

process.stdin.on('end', () => {
  reconnecting = false;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  destroyClient().then(() => process.exit(0));
});

process.on('SIGINT', () => {
  reconnecting = false;
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  destroyClient().then(() => process.exit(0));
});

process.on('uncaughtException', (err) => {
  send('error', { message: 'Uncaught: ' + err.message });
  console.error('[SIDECAR] Uncaught runtime exception');
});

process.on('unhandledRejection', (reason) => {
  const msg = reason instanceof Error ? reason.message : String(reason);
  send('error', { message: 'Unhandled rejection: ' + msg });
  console.error('[SIDECAR] Unhandled runtime rejection');
});

const args = process.argv.slice(2);
if (args.length >= 1) {
  const action = args[0];
  if (action === 'connect' && args.length >= 3) {
    handleAction('connect', { assignmentId: args[1], gatewayNumber: args[2] });
  }
}
