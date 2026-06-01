/**
 * components/StatsCard.jsx — Metric stat card with icon and trend indicator.
 * @param {{ title: string, value: number|string, icon: React.Component,
 *           color: string, subtitle?: string, loading?: boolean }} props
 */
export function StatsCard({ title, value, icon: Icon, color, subtitle, loading }) {
  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-24 mb-3" />
        <div className="h-8 bg-gray-700 rounded w-16" />
      </div>
    );
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <span className="text-gray-400 text-sm font-medium">{title}</span>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
      <div className="text-2xl font-bold text-white mb-1">
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {subtitle && <div className="text-xs text-gray-500">{subtitle}</div>}
    </div>
  );
}
