import { useTranslation } from 'react-i18next';

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation('common');

  const toggleLanguage = () => {
    const nextLanguage = i18n.language.startsWith('es') ? 'en' : 'es';
    i18n.changeLanguage(nextLanguage);
  };

  return (
    <button
      type="button"
      onClick={toggleLanguage}
      className="rounded-lg border border-surface-600 bg-surface-700 px-3 py-1 text-xs font-semibold text-gray-200 transition-colors hover:bg-surface-600"
      title={t('language.current')}
      aria-label={t('language.current')}
    >
      {t('language.switch')}
    </button>
  );
}
