/**
 * components/CertModal.jsx — Certificate detail modal.
 * Shows CN, SAN, issuer, validity dates, and raw cert info.
 * @param {{ cert: object|null, onClose: function }} props
 */
import { X, ShieldCheck, Calendar, AlertTriangle } from "lucide-react";
import { useEffect } from "react";

function Field({ label, value }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-gray-200 font-mono break-all">{value}</dd>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    ok:       "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    warning:  "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    critical: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    expired:  "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const label = {
    ok: "Valid", warning: "Expiring Soon", critical: "Critical", expired: "Expired",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${map[status] || map.ok}`}>
      {label[status] || "Unknown"}
    </span>
  );
}

export default function CertModal({ cert, onClose }) {
  // Close on Escape key
  useEffect(() => {
    if (!cert) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cert, onClose]);

  if (!cert) return null;

  const validFrom = new Date(cert.validFrom).toLocaleString();
  const validTo   = new Date(cert.validTo).toLocaleString();
  const days      = cert.daysUntilExpiry;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <ShieldCheck size={20} className="text-emerald-400" />
            <h2 className="text-white font-semibold text-base">Certificate Details</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-500 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Status banner */}
          <div className="flex items-center justify-between">
            <StatusBadge status={cert.status} />
            {days < 0 ? (
              <span className="flex items-center gap-1 text-red-400 text-sm">
                <AlertTriangle size={14} />
                Expired {Math.abs(days)} day{Math.abs(days) !== 1 ? "s" : ""} ago
              </span>
            ) : (
              <span className="flex items-center gap-1 text-gray-400 text-sm">
                <Calendar size={14} />
                {days < 1
                  ? `Expires in ${Math.round(days * 24)} hours`
                  : `${days} day${days !== 1 ? "s" : ""} remaining`
                }
              </span>
            )}
          </div>

          {/* Fields */}
          <dl className="grid grid-cols-1 gap-4">
            <Field label="Common Name (CN)" value={cert.cn} />
            <Field label="Issuer"           value={cert.issuer} />
            <Field
              label="Subject Alternative Names (SAN)"
              value={cert.san?.join(", ") ?? "—"}
            />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Valid From" value={validFrom} />
              <Field label="Valid To"   value={validTo} />
            </div>
            <Field label="Service" value={cert.service} />
          </dl>

          {/* Raw cert preview placeholder */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Certificate (PEM)</p>
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-500
                            font-mono overflow-hidden max-h-28 leading-relaxed">
{`-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIUYZero... (${cert.cn})
[Issued by ${cert.issuer}]
[Valid: ${validFrom} → ${validTo}]
-----END CERTIFICATE-----`}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white
                       bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
