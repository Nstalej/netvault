import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Clock3, Router } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import MetricCard from '../components/ui/MetricCard';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import StatusBadge from '../components/ui/StatusBadge';

function formatUptime(seconds) {
  const safe = Number(seconds || 0);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

export default function DashboardPage() {
  const { t } = useTranslation('common');

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health'),
    refetchInterval: 30000,
  });

  const { data: devices = [], isLoading, isError } = useQuery({
    queryKey: ['devices'],
    queryFn: () => api.get('/devices'),
    refetchInterval: 60000,
  });

  const metrics = useMemo(() => {
    const total = devices.length;
    const online = devices.filter((d) => d.status === 'online').length;
    const offline = devices.filter((d) => d.status === 'offline').length;
    return { total, online, offline };
  }, [devices]);

  if (isLoading) {
    return <LoadingSpinner text={t('status.loadingDashboard')} />;
  }

  if (isError) {
    return <div className="card text-sm text-red-300">{t('status.dashboardLoadError')}</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">{t('nav.dashboard')}</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard title={t('dashboard.metrics.totalDevices')} value={metrics.total} icon={Router} color="text-gray-300" />
        <MetricCard title={t('dashboard.metrics.online')} value={metrics.online} icon={CheckCircle2} color="text-green-400" />
        <MetricCard title={t('dashboard.metrics.offline')} value={metrics.offline} icon={AlertTriangle} color="text-red-400" />
        <MetricCard
          title={t('dashboard.metrics.uptime')}
          value={formatUptime(health?.uptime_seconds)}
          icon={Clock3}
          color="text-teal"
        />
      </div>

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">{t('dashboard.recentDevices')}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-600 text-left text-gray-500">
                <th className="pb-2 font-medium">{t('devices.columns.name')}</th>
                <th className="pb-2 font-medium">{t('devices.columns.ip')}</th>
                <th className="pb-2 font-medium">{t('devices.columns.type')}</th>
                <th className="pb-2 font-medium">{t('devices.columns.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-600">
              {devices.slice(0, 8).map((device) => (
                <tr key={device.id} className="transition-colors hover:bg-surface-700/60">
                  <td className="py-2.5 font-medium text-white">{device.name}</td>
                  <td className="py-2.5 font-mono text-xs text-gray-400">{device.ip_address}</td>
                  <td className="py-2.5 text-gray-300">{device.device_type || '-'}</td>
                  <td className="py-2.5">
                    <StatusBadge status={device.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
