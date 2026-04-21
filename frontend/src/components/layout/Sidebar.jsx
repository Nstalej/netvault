import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Monitor, Network, Settings, Shield } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const NAV_ITEMS = [
  { to: '/dashboard', key: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/devices', key: 'nav.devices', icon: Monitor },
  { to: '/audit', key: 'nav.audit', icon: Shield },
  { to: '/topology', key: 'nav.topology', icon: Network },
  { to: '/settings', key: 'nav.settings', icon: Settings },
];

export default function Sidebar() {
  const { t } = useTranslation('common');

  return (
    <aside className="hidden w-60 flex-col border-r border-surface-600 bg-surface-800 md:flex">
      <div className="border-b border-surface-600 px-4 py-5">
        <span className="text-xl font-bold text-teal">Net</span>
        <span className="text-xl font-bold text-white">Vault</span>
        <span className="ml-2 rounded bg-surface-700 px-1.5 py-0.5 font-mono text-[10px] text-gray-400">v0.5</span>
      </div>

      <nav className="flex-1 space-y-1 px-2 py-4">
        {NAV_ITEMS.map(({ to, key, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-teal text-white'
                  : 'text-gray-400 hover:bg-surface-700 hover:text-gray-100'
              }`
            }
          >
            <Icon size={16} />
            {t(key)}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-surface-600 px-4 py-3 text-xs text-gray-500">{t('app.version')}</div>
    </aside>
  );
}
