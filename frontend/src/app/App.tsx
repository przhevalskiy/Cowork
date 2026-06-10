import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useParams, useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import { ChatArea } from '@/features/chat';
import { useDiscussionStore } from '@/features/discussions';
import { useAuthStore, AuthModal } from '@/features/auth';
import './App.css';

function ChatPage() {
  const { discussionId } = useParams<{ discussionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { setActiveDiscussionId, discussions } = useDiscussionStore();
  const initialMessage = location.state?.initialMessage;

  useEffect(() => {
    if (discussionId) {
      const exists = discussions.length === 0 || discussions.some((d) => d.id === discussionId);
      if (exists) {
        setActiveDiscussionId(discussionId);
      } else {
        navigate('/chat', { replace: true });
      }
    } else {
      setActiveDiscussionId(null);
    }
  }, [discussionId, discussions, setActiveDiscussionId, navigate]);

  return <ChatArea initialMessage={initialMessage} />;
}

function AppLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:discussionId" element={<ChatPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  const { user, isInitializing, initialize } = useAuthStore();
  const [isProcessingAuth, setIsProcessingAuth] = useState(false);

  useEffect(() => {
    const urlHasAuthTokens = window.location.hash.includes('access_token') ||
                            window.location.hash.includes('refresh_token');
    if (urlHasAuthTokens) {
      setIsProcessingAuth(true);
    }
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (user && isProcessingAuth) {
      setIsProcessingAuth(false);
      if (window.location.hash) {
        window.history.replaceState(null, '', window.location.pathname);
      }
    }
  }, [user, isProcessingAuth]);

  if (isInitializing || isProcessingAuth) {
    return (
      <div className="auth-loading">
        <div className="spinner" />
        {isProcessingAuth && (
          <p style={{ marginTop: '16px', color: 'var(--gray-600)' }}>
            Confirming your email...
          </p>
        )}
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<AppLayout />} />
      </Routes>
      <AuthModal isOpen={!user} />
    </BrowserRouter>
  );
}

export default App;
