import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('netvault_token'));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('netvault_user');
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      if (!token) {
        if (active) {
          setLoading(false);
        }
        return;
      }

      try {
        const me = await api.get('/auth/me');
        if (active) {
          setUser(me);
          localStorage.setItem('netvault_user', JSON.stringify(me));
        }
      } catch {
        localStorage.removeItem('netvault_token');
        localStorage.removeItem('netvault_user');
        if (active) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      active = false;
    };
  }, [token]);

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    const nextToken = response?.access_token || response?.token;
    const nextUser = response?.user;

    if (!nextToken || !nextUser) {
      throw new Error('Invalid login response');
    }

    localStorage.setItem('netvault_token', nextToken);
    localStorage.setItem('netvault_user', JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
    return true;
  };

  const logout = () => {
    localStorage.removeItem('netvault_token');
    localStorage.removeItem('netvault_user');
    setToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      login,
      logout,
      isAdmin: () => user?.role === 'admin',
      isEditor: () => ['admin', 'editor'].includes(user?.role),
    }),
    [loading, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
