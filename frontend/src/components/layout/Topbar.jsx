import { LogOut, Menu, User } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import LanguageSwitcher from '../LanguageSwitcher';

export default function Topbar() {
  const { t } = useTranslation('common');
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b border-surface-600 bg-surface-800 px-4 md:px-6">
      <div className="flex items-center gap-2 text-gray-400 md:hidden">
        <Menu size={16} />
        <span className="text-xs uppercase tracking-widest">{t('app.short')}</span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <LanguageSwitcher />
        <div className="hidden items-center gap-2 text-sm text-gray-400 sm:flex">
          <User size={14} />
          <span>{user?.email || t('auth.userFallback')}</span>
          <span className="rounded bg-surface-700 px-1.5 py-0.5 font-mono text-xs text-teal">
            {user?.role || t('auth.roleUnknown')}
          </span>
        </div>
        <button
          type="button"
          onClick={logout}
          className="inline-flex items-center gap-1 text-sm text-gray-400 transition-colors hover:text-red-400"
          title={t('actions.logout')}
          aria-label={t('actions.logout')}
        >
          <LogOut size={14} />
          <span className="hidden sm:inline">{t('actions.logout')}</span>
        </button>
      </div>
    </header>
  );
}
