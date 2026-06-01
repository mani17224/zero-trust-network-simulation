/**
 * pages/AuditLogs.jsx — Filterable, searchable audit log table with CSV export.
 */
import { useState, useMemo } from "react";
import { ScrollText, Download, Search, Filter } from "lucide-react";
import { useAuditLogs } from "../hooks/useLogs";

function DecisionBadge({ decision }) {
  return decision === "allow" ? (
    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400
                     border border-emerald-500/30 font-medium">Allow</span>
  ) : (
    <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400
                     border border-red-500/30 font-medium">Deny</span>
  );
}

function MethodBadge({ method }) {
  const colors = {
    GET:    "bg-blue-900/50 text-blue-300",
    POST:   "bg-yellow-900/50 text-yellow-300",
    PUT:    "bg-orange-900/50 text-orange-300",
    PATCH:  "bg-orange-900/50 text-orange-300",
    DELETE: "bg-red-900/50 text-red-300",
  };
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono font-semibold ${colors[method] ?? "bg-gray-800 text-gray-400"}`}>
      {method}
    </span>
  );
}

function exportToCsv(logs) {
  const headers = ["timestamp","source","destination","method","resource","decision","reason","latency_ms","request_id"];
  const rows = logs.map((l) =>
    [l.timestamp, l.subject, l.target_service, l.method,
     l.resource, l.decision, `"${l.reason}"`, l.latency_ms, l.request_id].join(",")
  );
  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `audit-logs-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AuditLogs() {
  const { data: logs, isLoading } = useAuditLogs();
  const [search, setSearch]     = useState("");
  const [decision, setDecision] = useState("all");
  const [method, setMethod]     = useState("all");

  const filtered = useMemo(() => {
    if (!logs) return [];
    return logs.filter((l) => {
      const matchSearch =
        !search ||
        l.subject.includes(search)       ||
        l.resource.includes(search)      ||
        l.reason.includes(search)        ||
        l.target_service.includes(search);
      const matchDecision = decision === "all" || l.decision === decision;
      const matchMethod   = method   === "all" || l.method   === method;
      return matchSearch && matchDecision && matchMethod;
    });
  }, [logs, search, decision, method]);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Audit Logs</h1>
          <p className="text-gray-500 text-sm mt-1">
            Authorization decisions — {filtered.length} entries
          </p>
        </div>
        <button
          onClick={() => exportToCsv(filtered)}
          disabled={!filtered.length}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-300
                     bg-gray-800 hover:bg-gray-700 border border-gray-700
                     rounded-lg transition-colors disabled:opacity-40"
        >
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search subject, resource, reason…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                       text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm
                     text-white focus:outline-none focus:border-emerald-500"
        >
          <option value="all">All Decisions</option>
          <option value="allow">Allow</option>
          <option value="deny">Deny</option>
        </select>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm
                     text-white focus:outline-none focus:border-emerald-500"
        >
          <option value="all">All Methods</option>
          {["GET","POST","PUT","DELETE","PATCH"].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {["Timestamp","Source","Destination","Method","Resource","Decision","Latency","Reason"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {isLoading
                ? [...Array(8)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(8)].map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-3.5 bg-gray-800 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((log) => (
                    <tr
                      key={log.id}
                      className={`hover:bg-gray-800/40 transition-colors ${
                        log.decision === "deny" ? "bg-red-500/5" : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap font-mono">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-3 text-gray-300 text-xs font-medium whitespace-nowrap">
                        {log.subject}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                        {log.target_service}
                      </td>
                      <td className="px-4 py-3">
                        <MethodBadge method={log.method} />
                      </td>
                      <td className="px-4 py-3 text-gray-300 text-xs font-mono">
                        {log.resource}
                      </td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={log.decision} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                        {log.latency_ms}ms
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                        {log.reason}
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {!isLoading && !filtered.length && (
          <div className="text-center py-12 text-gray-600 text-sm">
            No log entries match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}
