import { useNavigate } from 'react-router-dom';
import { useAppState } from '../context/AppContext';
import LoginScreen from '../components/LoginScreen';

export default function LoginPage() {
  const { handleLogin, loginLoading, loginError, user, assignments } = useAppState();
  const navigate = useNavigate();

  if (user) {
    navigate(assignments.length > 0 ? '/chat' : '/connect', { replace: true });
    return null;
  }

  const onLogin = async (email: string, password: string) => {
    await handleLogin(email, password);
  };

  return <LoginScreen onLogin={onLogin} loading={loginLoading} error={loginError} />;
}
