import { useTranslation } from 'react-i18next';

export default function TopologyPage() {
  const { t } = useTranslation('common');
  return (
    <div className="card py-12 text-center text-gray-400">
      {t('topology.placeholder')}
    </div>
  );
}
