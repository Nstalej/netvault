import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PlusCircle, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import StatusBadge from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';

export default function DevicesPage() {
  const { t } = useTranslation('common');
  const { isEditor } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: devices = [], isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: () => api.get('/devices'),
    refetchInterval: 60000,
  });

  const testDeviceMutation = useMutation({
    mutationFn: (deviceId) => api.post(`/devices/${deviceId}/test`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">{t('nav.devices')}</h1>
        {isEditor() ? (
          <button type="button" className="btn-primary inline-flex items-center gap-2" disabled>
            <PlusCircle size={16} />
            {t('actions.addDevice')}
          </button>
        ) : null}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-600 text-left text-gray-500">
              <th className="pb-2 font-medium">{t('devices.columns.name')}</th>
              <th className="pb-2 font-medium">{t('devices.columns.ip')}</th>
              <th className="pb-2 font-medium">{t('devices.columns.type')}</th>
              <th className="pb-2 font-medium">{t('devices.columns.status')}</th>
              <th className="pb-2 font-medium">{t('devices.columns.actions')}</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-surface-600">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-500">
                  {t('status.loadingDevices')}
                </td>
              </tr>
            ) : null}

            {!isLoading && devices.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-500">
                  {t('devices.empty')}
                </td>
              </tr>
            ) : null}

            {!isLoading
              ? devices.map((device) => (
                  <tr
                    key={device.id}
                    className="cursor-pointer transition-colors hover:bg-surface-700/50"
                    onClick={() => navigate(`/devices/${device.id}`)}
                  >
                    <td className="py-2.5 font-medium text-white">{device.name}</td>
                    <td className="py-2.5 font-mono text-xs text-gray-400">{device.ip_address}</td>
                    <td className="py-2.5 text-gray-300">{device.device_type || '-'}</td>
                    <td className="py-2.5">
                      <StatusBadge status={device.status} />
                    </td>
                    <td className="py-2.5" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        className="btn-secondary inline-flex items-center gap-2"
                        onClick={() => testDeviceMutation.mutate(device.id)}
                        disabled={testDeviceMutation.isPending}
                      >
                        <RefreshCw size={14} className={testDeviceMutation.isPending ? 'animate-spin' : ''} />
                        {t('actions.test')}
                      </button>
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
