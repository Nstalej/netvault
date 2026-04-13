import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export default function SettingsPage() {
  const { t } = useTranslation('common');
  const [tab, setTab] = useState('credentials');

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">{t('nav.settings')}</h1>

      <div className="inline-flex rounded-lg border border-surface-600 bg-surface-800 p-1">
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === 'credentials' ? 'bg-teal text-white' : 'text-gray-400'}`}
          onClick={() => setTab('credentials')}
        >
          {t('settings.tabs.credentials')}
        </button>
        <button
          type="button"
          className={`rounded-md px-3 py-1.5 text-sm ${tab === 'general' ? 'bg-teal text-white' : 'text-gray-400'}`}
          onClick={() => setTab('general')}
        >
          {t('settings.tabs.general')}
        </button>
      </div>

      <div className="card text-sm text-gray-300">
        {tab === 'credentials' ? t('settings.placeholderCredentials') : t('settings.placeholderGeneral')}
      </div>
    </div>
  );
}
