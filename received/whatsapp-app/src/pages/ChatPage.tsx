import { useAppState } from '../context/AppContext';
import ChatScreen from '../components/ChatScreen';

export default function ChatPage() {
  const { user, isWhatsAppConnected, connectionStatus, connectionMessage, filteredChats, clients, whatsapp, addListener, clearUnread } = useAppState();

  if (!isWhatsAppConnected) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-32px)] bg-bg-primary gap-4">
        <div className="w-10 h-10 border-2 border-accent/30 border-t-accent rounded-full animate-spin-slow" />
        <div className="text-center">
          <p className="text-text-primary text-[15px] font-medium mb-1">
            {connectionStatus === 'pending' ? (connectionMessage || 'Connecting to WhatsApp...') : 'Waiting for WhatsApp...'}
          </p>
          <p className="text-text-secondary text-[13px]">Please wait while we finish setting up</p>
        </div>
      </div>
    );
  }

  return (
    <ChatScreen
      user={user}
      isWhatsAppConnected={isWhatsAppConnected}
      connectionStatus={connectionStatus}
      connectionMessage={connectionMessage}
      chats={filteredChats}
      clients={clients}
      whatsapp={whatsapp}
      addListener={addListener}
      clearUnread={clearUnread}
    />
  );
}
