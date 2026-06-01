/**
 * pages/CertificateManager.jsx — mTLS certificate table with expiry indicators and renewal.
 */
import { useState } from "react";
import { KeyRound, RefreshCw, Eye, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { useCertificates, useRenewCertificate } from "../hooks/useCertificates";
import CertModal from "../components/CertModal";
import useStore from "../store";

function ExpiryBadge({ status, days }) {
  if (status === "expired") return (
    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                     bg-red-500/20 text-red-400 border border-red-500/30 font-medium">
      <XCircle size={11} /> Expired
    </span>
  );
  if (status === "critical") return (
    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                     bg-orange-500/20 text-orange-400 border border-orange-500/30 font-medium">
      <AlertTriangle size={11} /> {days}h left
    </span>
  );
  if (status === "warning") return (
    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                     bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 font-medium">
      <AlertTriangle size={11} /> {days}d left
    </span>
  );
  return (
    <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                     bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">
      <CheckCircle size={11} /> {days}d
    </span>
  );
}

export default function CertificateManager() {
  const { data: certs, isLoading } = useCertificates();
  const { mutate: renewCert, isPending, variables: renewingId } = useRenewCertificate();
  const [selectedCert, setSelectedCert] = useState(null);
  const addNotification = useStore((s) => s.addNotification);

  const handleRenew = (cert) => {
    renewCert(cert.id, {
      onSuccess: () => addNotification("success", `Certificate renewed: ${cert.cn}`),
      onError:   () => addNotification("error",   `Failed to renew: ${cert.cn}`),
    });
  };

  const summary = certs
    ? {
        total:   certs.length,
        ok:      certs.filter((c) => c.status === "ok").length,
        warning: certs.filter((c) => c.status === "warning" || c.status === "critical").length,
        expired: certs.filter((c) => c.status === "expired").length,
      }
    : { total: 0, ok: 0, warning: 0, expired: 0 };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Certificate Manager</h1>
        <p className="text-gray-500 text-sm mt-1">Monitor and renew mTLS service certificates</p>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total",    value: summary.total,   color: "text-gray-300" },
          { label: "Valid",    value: summary.ok,      color: "text-emerald-400" },
          { label: "Expiring", value: summary.warning, color: "text-yellow-400" },
          { label: "Expired",  value: summary.expired, color: "text-red-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Certificates table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center gap-2">
          <KeyRound size={16} className="text-emerald-400" />
          <h2 className="text-white font-semibold text-sm">Service Certificates</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {["Service","Common Name","Issuer","Expiry","Status","Actions"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading
                ? [...Array(5)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(6)].map((_, j) => (
                        <td key={j} className="px-5 py-4">
                          <div className="h-4 bg-gray-800 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                : (certs ?? []).map((cert) => {
                    const isRenewing = isPending && renewingId === cert.id;
                    const displayDays = cert.daysUntilExpiry < 1
                      ? `${Math.round(cert.daysUntilExpiry * 24)}h`
                      : `${cert.daysUntilExpiry}d`;

                    return (
                      <tr
                        key={cert.id}
                        className={`hover:bg-gray-800/40 transition-colors ${
                          cert.status === "expired"  ? "bg-red-500/5"    :
                          cert.status === "critical" ? "bg-orange-500/5" :
                          cert.status === "warning"  ? "bg-yellow-500/5" : ""
                        }`}
                      >
                        <td className="px-5 py-4 font-medium text-white">{cert.service}</td>
                        <td className="px-5 py-4 font-mono text-xs text-gray-300">{cert.cn}</td>
                        <td className="px-5 py-4 text-gray-400 text-xs">{cert.issuer}</td>
                        <td className="px-5 py-4 text-xs text-gray-400">
                          {new Date(cert.validTo).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-4">
                          <ExpiryBadge status={cert.status} days={cert.daysUntilExpiry} />
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setSelectedCert(cert)}
                              className="p-1.5 text-gray-500 hover:text-white hover:bg-gray-700
                                         rounded-lg transition-colors"
                              title="View details"
                            >
                              <Eye size={14} />
                            </button>
                            <button
                              onClick={() => handleRenew(cert)}
                              disabled={isRenewing}
                              className="flex items-center gap-1.5 px-2.5 py-1 text-xs
                                         bg-emerald-600/20 hover:bg-emerald-600/40
                                         text-emerald-400 border border-emerald-500/30
                                         rounded-lg transition-colors disabled:opacity-50"
                              title="Renew certificate"
                            >
                              <RefreshCw size={12} className={isRenewing ? "animate-spin" : ""} />
                              Renew
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
              }
            </tbody>
          </table>
        </div>
      </div>

      <CertModal cert={selectedCert} onClose={() => setSelectedCert(null)} />
    </div>
  );
}
