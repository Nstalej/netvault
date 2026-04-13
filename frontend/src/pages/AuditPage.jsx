import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';

const PAGE_SIZE = 20;

export default function AuditPage() {
  const { t } = useTranslation('common');
  const [filters, setFilters] = useState({
    device_id: '',
    audit_type: '',
    status: '',
    date_from: '',
    date_to: '',
  });
  const [page, setPage] = useState(0);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.device_id) params.set('device_id', filters.device_id);
    if (filters.audit_type) params.set('audit_type', filters.audit_type);
    if (filters.status) params.set('status', filters.status);
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String(page * PAGE_SIZE));
    return params.toString();
  }, [filters, page]);

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['audit', queryString],
    queryFn: () => api.get(`/audit/results?${queryString}`),
  });

  const updateFilter = (key, value) => {
    setPage(0);
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">{t('nav.audit')}</h1>

      <div className="card grid grid-cols-1 gap-3 md:grid-cols-5">
        <input
          className="input"
          placeholder={t('audit.filters.deviceId')}
          value={filters.device_id}
          onChange={(event) => updateFilter('device_id', event.target.value)}
        />
        <input
          className="input"
          placeholder={t('audit.filters.auditType')}
          value={filters.audit_type}
          onChange={(event) => updateFilter('audit_type', event.target.value)}
        />
        <input
          className="input"
          placeholder={t('audit.filters.status')}
          value={filters.status}
          onChange={(event) => updateFilter('status', event.target.value)}
        />
        <input
          className="input"
          type="date"
          value={filters.date_from}
          onChange={(event) => updateFilter('date_from', event.target.value)}
          aria-label={t('audit.filters.dateFrom')}
        />
        <input
          className="input"
          type="date"
          value={filters.date_to}
          onChange={(event) => updateFilter('date_to', event.target.value)}
          aria-label={t('audit.filters.dateTo')}
        />
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-600 text-left text-gray-500">
              <th className="pb-2 font-medium">{t('audit.columns.id')}</th>
              <th className="pb-2 font-medium">{t('audit.columns.deviceId')}</th>
              <th className="pb-2 font-medium">{t('audit.columns.type')}</th>
              <th className="pb-2 font-medium">{t('audit.columns.status')}</th>
              <th className="pb-2 font-medium">{t('audit.columns.timestamp')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-600">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-500">
                  {t('status.loadingAudit')}
                </td>
              </tr>
            ) : null}

            {!isLoading && rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-500">
                  {t('audit.empty')}
                </td>
              </tr>
            ) : null}

            {!isLoading
              ? rows.map((row) => (
                  <tr key={row.id}>
                    <td className="py-2.5 text-gray-200">{row.id}</td>
                    <td className="py-2.5 text-gray-300">{row.device_id}</td>
                    <td className="py-2.5 text-gray-300">{row.audit_type}</td>
                    <td className="py-2.5 text-gray-300">{row.status}</td>
                    <td className="py-2.5 text-gray-400">{row.created_at || '-'}</td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-end gap-2">
        <button type="button" className="btn-secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
          {t('actions.previous')}
        </button>
        <button type="button" className="btn-secondary" disabled={rows.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
          {t('actions.next')}
        </button>
      </div>
    </div>
  );
}
