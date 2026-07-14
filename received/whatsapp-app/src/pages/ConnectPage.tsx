import { useNavigate } from 'react-router-dom';
import { useAppState } from '../context/AppContext';
import ConnectionScreen from '../components/ConnectionScreen';

export default function ConnectPage() {
  const { user, assignments, isWhatsAppConnected, connectionStatus, connectionMessage, qrCodeUrl, handleConnect } = useAppState();
  const navigate = useNavigate();

  if (isWhatsAppConnected) {
    navigate('/chat', { replace: true });
    return null;
  }

  const onGoToChat = () => navigate('/chat');

  return (
    <ConnectionScreen
      user={user}
      assignments={assignments}
      isWhatsAppConnected={isWhatsAppConnected}
      connectionStatus={connectionStatus}
      connectionMessage={connectionMessage}
      qrCodeUrl={qrCodeUrl}
      onConnect={handleConnect}
      onGoToChat={onGoToChat}
      isWhatsAppReady={connectionStatus === 'connected'}
    />
  );
}
