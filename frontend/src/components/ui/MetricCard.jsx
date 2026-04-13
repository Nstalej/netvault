export default function MetricCard({ title, value, subtitle, icon: Icon, color = 'text-teal' }) {
  return (
    <div className="card flex items-start gap-4">
      {Icon ? (
        <div className={`${color} mt-0.5 rounded-lg bg-surface-700 p-2`}>
          <Icon size={18} />
        </div>
      ) : null}

      <div>
        <p className="text-xs uppercase tracking-wide text-gray-500">{title}</p>
        <p className="mt-1 text-2xl font-bold text-white">{value}</p>
        {subtitle ? <p className="mt-1 text-xs text-gray-500">{subtitle}</p> : null}
      </div>
    </div>
  );
}
