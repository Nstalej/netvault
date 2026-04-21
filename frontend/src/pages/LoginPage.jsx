import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { t } = useTranslation('auth');
  const { token, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('admin@netvault.local');
  const [password, setPassword] = useState('NetVault2025!');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const from = location.state?.from || '/dashboard';

  if (token) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch {
      setError(t('login.error'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-surface-900 px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(20,168,173,0.25),_transparent_45%)]" />

      <div className="relative w-full max-w-md rounded-2xl border border-surface-600 bg-surface-800/90 p-6 backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-lg bg-teal/20 p-2 text-teal">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">{t('login.title')}</h1>
            <p className="text-sm text-gray-400">{t('login.subtitle')}</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-gray-300" htmlFor="email">
              {t('login.email')}
            </label>
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder={t('login.emailPlaceholder')}
              autoComplete="username"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-300" htmlFor="password">
              {t('login.password')}
            </label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={t('login.passwordPlaceholder')}
              autoComplete="current-password"
            />
          </div>

          {error ? <p className="text-sm text-red-400">{error}</p> : null}

          <button type="submit" className="btn-primary w-full" disabled={submitting}>
            {submitting ? t('login.loading') : t('login.submit')}
          </button>
        </form>
      </div>
    </div>
  );
}
