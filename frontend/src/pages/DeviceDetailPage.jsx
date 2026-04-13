import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import StatusBadge from '../components/ui/StatusBadge';

export default function DeviceDetailPage() {
  const { id } = useParams();
  const { t } = useTranslation('common');

  const { data: device, isLoading, isError } = useQuery({
    queryKey: ['device', id],
    queryFn: () => api.get(`/devices/${id}`),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return <LoadingSpinner text={t('status.loadingDevice')} />;
  }

  if (isError || !device) {
    return <div className="card text-sm text-red-300">{t('devices.detailLoadError')}</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">{t('devices.detailTitle', { name: device.name })}</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="card">
          <p className="text-sm text-gray-500">{t('devices.columns.ip')}</p>
          <p className="mt-1 font-mono text-sm text-gray-200">{device.ip_address}</p>
        </div>

        <div className="card">
          <p className="text-sm text-gray-500">{t('devices.columns.status')}</p>
          <div className="mt-2">
            <StatusBadge status={device.status} />
          </div>
        </div>
      </div>

      <div className="card text-sm text-gray-300">{t('devices.detailPlaceholder')}</div>
    </div>
  );
}
