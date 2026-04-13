import { useTranslation } from 'react-i18next';

const STATUS_CONFIG = {
  online: 'border-green-800 bg-green-900/30 text-green-400',
  offline: 'border-red-800 bg-red-900/30 text-red-400',
  warning: 'border-yellow-800 bg-yellow-900/30 text-yellow-400',
  unknown: 'border-gray-700 bg-gray-800 text-gray-400',
};

export default function StatusBadge({ status }) {
  const { t } = useTranslation('common');
  const safeStatus = ['online', 'offline', 'warning', 'unknown'].includes(status) ? status : 'unknown';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${STATUS_CONFIG[safeStatus]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {t(`status.${safeStatus}`)}
    </span>
  );
}
