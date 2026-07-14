import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import TitleBar from './components/TitleBar';
import LoginPage from './pages/LoginPage';
import ConnectPage from './pages/ConnectPage';
import ChatPage from './pages/ChatPage';
import { AppProvider, useAppState } from './context/AppContext';

function ToastDisplay() {
  const { toast } = useAppState();
  if (!toast) return null;
  return (
    <div className="fixed bottom-10 right-5 z-[1000] animate-slide-in">
      <div className={`bg-bg-secondary border border-border rounded-lg px-4 py-3 flex items-center gap-3 shadow-[0_4px_12px_rgba(0,0,0,0.3)] ${
        toast.type === 'success' ? 'border-l-[3px] border-l-success' :
        toast.type === 'error' ? 'border-l-[3px] border-l-danger' :
        'border-l-[3px] border-l-info'
      }`}>
        <span>{toast.message}</span>
      </div>
    </div>
  );
}

function AppContent() {
  const { user, isWhatsAppConnected, loading } = useAppState();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-32px)] bg-bg-primary">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin-slow" />
      </div>
    );
  }

  return (
    <>
      <Routes>
        <Route path="/login" element={user ? <Navigate to={isWhatsAppConnected ? '/chat' : '/connect'} replace /> : <LoginPage />} />
        <Route path="/connect" element={!user ? <Navigate to="/login" replace /> : isWhatsAppConnected ? <Navigate to="/chat" replace /> : <ConnectPage />} />
        <Route path="/chat" element={!user ? <Navigate to="/login" replace /> : <ChatPage />} />
        <Route path="*" element={<Navigate to={user ? (isWhatsAppConnected ? '/chat' : '/connect') : '/login'} replace />} />
      </Routes>
      <ToastDisplay />
    </>
  );
}

export default function App() {
  return (
    <AppProvider>
      <div className="flex flex-col h-screen bg-bg-primary">
        <TitleBar />
        <HashRouter>
          <AppContent />
        </HashRouter>
      </div>
    </AppProvider>
  );
}
