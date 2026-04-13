import { useTranslation } from 'react-i18next';

const SIZES = {
  sm: 'h-4 w-4',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
};

export default function LoadingSpinner({ size = 'md', text }) {
  const { t } = useTranslation('common');

  return (
    <div className="flex min-h-[30vh] flex-col items-center justify-center gap-3">
      <div className={`${SIZES[size] || SIZES.md} animate-spin rounded-full border-2 border-surface-600 border-t-teal`} />
      <p className="text-sm text-gray-500">{text || t('status.loading')}</p>
    </div>
  );
}
