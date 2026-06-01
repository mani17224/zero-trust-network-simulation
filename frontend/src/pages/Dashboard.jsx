/**
 * Dashboard.jsx — Live stats, real-time chart, activity feed.
 * Fixes:
 *   - Proper loading skeletons on all data fetches
 *   - Error state with retry button
 *   - Chart only renders when data is available
 *   - Stats fall back to liveStats store when API unavailable
 */
import { useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  Activity, CheckCircle, XCircle, Wifi,
  AlertTriangle, RefreshCw,
} from "lucide-react";
import { useMetrics } from "../hooks/useMetrics";
import { useAuditLogs } from "../hooks/useLogs";
import { StatsCard } from "../components/StatsCard";
import ActivityFeed from "../components/ActivityFeed";
import useStore from "../store";

function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex items-center justify-between p-3 bg-red-500/10 border border-red-500/20
                    rounded-xl text-sm text-red-400">
      <div className="flex items-center gap-2">
        <AlertTriangle size={15} />
        {message}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 px-2 py-1 bg-red-500/20 hover:bg-red-500/30
                     rounded-lg text-xs transition-colors"
        >
          <RefreshCw size={11} /> Retry
        </button>
      )}
    </div>
  );
}

export default function Dashboard() {
  const {
    data: metricsData,
    isLoading: metricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
  } = useMetrics();

  const {
    data: logs,
    isLoading: logsLoading,
    error: logsError,
    refetch: refetchLogs,
  } = useAuditLogs();

  const { timeSeries, pushTimeSeriesPoint, liveStats, setLiveStats } = useStore();

  // Feed live stats into store + time series
  useEffect(() => {
    if (!metricsData?.stats) return;
    setLiveStats(metricsData.stats);
    pushTimeSeriesPoint({
      ts:      new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      allowed: metricsData.stats.allowed,
      denied:  metricsData.stats.denied,
    });
  }, [metricsData]);

  const stats = metricsData?.stats ?? liveStats;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Real-time Zero Trust network overview</p>
      </div>

      {/* Gateway error banner */}
      {metricsError && (
        <ErrorBanner
          message={`Gateway unreachable: ${metricsError.message}`}
          onRetry={refetchMetrics}
        />
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Total Requests" value={stats.total}       icon={Activity}     color="bg-blue-600"   subtitle="All time"                             loading={metricsLoading} />
        <StatsCard title="Allowed"        value={stats.allowed}     icon={CheckCircle}  color="bg-emerald-600"subtitle={stats.total ? `${((stats.allowed/stats.total)*100).toFixed(1)}%` : ""}   loading={metricsLoading} />
        <StatsCard title="Denied"         value={stats.denied}      icon={XCircle}      color="bg-red-600"    subtitle={stats.total ? `${((stats.denied/stats.total)*100).toFixed(1)}%` : ""}    loading={metricsLoading} />
        <StatsCard title="Active Peers"   value={stats.activePeers} icon={Wifi}         color="bg-violet-600" subtitle="Live connections"                      loading={metricsLoading} />
      </div>

      {/* Real-time chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold text-sm">Requests — Live</h2>
          <span className="text-xs text-gray-600">
            {timeSeries.length} data points · updates every 5s
          </span>
        </div>

        {metricsLoading && timeSeries.length === 0 ? (
          <div className="h-48 flex items-center justify-center">
            <div className="flex items-center gap-2 text-gray-600 text-sm">
              <RefreshCw size={14} className="animate-spin" /> Loading metrics…
            </div>
          </div>
        ) : timeSeries.length < 2 ? (
          <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
            Waiting for data… (auto-refreshes every 5 seconds)
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={timeSeries} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="ts" tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
              <Line type="monotone" dataKey="allowed" stroke="#10b981" strokeWidth={2} dot={false} name="Allowed" />
              <Line type="monotone" dataKey="denied"  stroke="#ef4444" strokeWidth={2} dot={false} name="Denied"  />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Activity feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold text-sm">Recent Activity</h2>
          {logsError && (
            <button onClick={refetchLogs}
              className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300">
              <RefreshCw size={11} /> Retry
            </button>
          )}
        </div>
        {logsError ? (
          <p className="text-sm text-yellow-500 flex items-center gap-2">
            <AlertTriangle size={14} />
            Showing mock data — {logsError.message}
          </p>
        ) : null}
        <ActivityFeed entries={logs ?? []} loading={logsLoading} />
      </div>
    </div>
  );
}
