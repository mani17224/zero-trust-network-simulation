/**
 * components/ActivityFeed.jsx — Real-time activity feed showing last 10 requests.
 * @param {{ entries: Array, loading: boolean }} props
 */
import { CheckCircle, XCircle, Clock } from "lucide-react";

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export default function ActivityFeed({ entries = [], loading }) {
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 bg-gray-800 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (!entries.length) {
    return <p className="text-gray-500 text-sm text-center py-8">No recent activity</p>;
  }

  return (
    <div className="space-y-2">
      {entries.slice(0, 10).map((entry) => (
        <div
          key={entry.id}
          className={`
            flex items-center gap-3 p-3 rounded-lg border text-sm
            ${entry.decision === "allow"
              ? "bg-emerald-500/5 border-emerald-500/20"
              : "bg-red-500/5 border-red-500/20"
            }
          `}
        >
          {entry.decision === "allow"
            ? <CheckCircle size={16} className="text-emerald-400 shrink-0" />
            : <XCircle    size={16} className="text-red-400 shrink-0" />
          }
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-gray-300 font-medium truncate">{entry.subject}</span>
              <span className="text-gray-500">→</span>
              <span className="text-gray-400 truncate">{entry.resource}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                entry.method === "DELETE" ? "bg-red-900/50 text-red-300"
                : entry.method === "POST" ? "bg-yellow-900/50 text-yellow-300"
                : "bg-blue-900/50 text-blue-300"
              }`}>{entry.method}</span>
            </div>
            <div className="text-xs text-gray-500 truncate">{entry.reason}</div>
          </div>
          <div className="flex items-center gap-1 text-xs text-gray-600 shrink-0">
            <Clock size={11} />
            {timeAgo(entry.timestamp)}
          </div>
        </div>
      ))}
    </div>
  );
}
