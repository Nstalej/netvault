import { useTranslation } from 'react-i18next';

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation('common');

  const setLanguage = (value) => {
    i18n.changeLanguage(value);
  };

  return (
    <div className="inline-flex rounded-lg border border-surface-600 bg-surface-700 p-0.5">
      <button
        type="button"
        onClick={() => setLanguage('en')}
        className={`rounded-md px-2 py-1 text-xs font-semibold transition-colors ${
          i18n.language.startsWith('en') ? 'bg-teal text-white' : 'text-gray-400 hover:text-gray-100'
        }`}
        aria-label={t('language.en')}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLanguage('es')}
        className={`rounded-md px-2 py-1 text-xs font-semibold transition-colors ${
          i18n.language.startsWith('es') ? 'bg-teal text-white' : 'text-gray-400 hover:text-gray-100'
        }`}
        aria-label={t('language.es')}
      >
        ES
      </button>
    </div>
  );
}
