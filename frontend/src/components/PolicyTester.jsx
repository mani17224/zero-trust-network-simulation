/**
 * PolicyTester.jsx — OPA policy tester with loading states and real error messages.
 * Fixes:
 *   - Shows spinner while testing (not frozen button)
 *   - Displays the real OPA error (not "Network error")
 *   - Explains how to fix common errors
 *   - Resource field is editable (type custom paths)
 */
import { useState } from "react";
import { CheckCircle, XCircle, Loader2, Play, AlertTriangle, Info } from "lucide-react";
import { useTestPolicy } from "../hooks/usePolicies";

const SUBJECTS  = ["gateway","service-a","service-b","service-c","monitoring-agent","admin-service","unknown-attacker"];
const SERVICES  = ["service-a","service-b","service-c","gateway"];
const RESOURCES = ["/health","/metrics","/login","/verify","/records","/records/123","/users","/audit-logs"];
const METHODS   = ["GET","POST","PUT","DELETE","PATCH"];

const cls = `w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
  text-sm text-white focus:outline-none focus:border-emerald-500 transition-colors`;

export default function PolicyTester() {
  const [form, setForm] = useState({
    subject: "gateway", service: "service-b", resource: "/records", method: "GET",
  });
  const [customResource, setCustomResource] = useState(false);
  const { mutate, data, isPending, error, reset } = useTestPolicy();

  const set = (field) => (e) => { setForm((f) => ({ ...f, [field]: e.target.value })); reset(); };
  const run = () => mutate(form);

  return (
    <div className="space-y-4">
      {/* Input grid */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Subject (Caller CN)</label>
          <select className={cls} value={form.subject} onChange={set("subject")}>
            {SUBJECTS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Target Service</label>
          <select className={cls} value={form.service} onChange={set("service")}>
            {SERVICES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-gray-400">Resource Path</label>
            <button
              onClick={() => setCustomResource((v) => !v)}
              className="text-xs text-emerald-400 hover:text-emerald-300"
            >
              {customResource ? "Use preset" : "Type custom"}
            </button>
          </div>
          {customResource ? (
            <input
              type="text"
              className={cls}
              value={form.resource}
              onChange={set("resource")}
              placeholder="/your/custom/path"
            />
          ) : (
            <select className={cls} value={form.resource} onChange={set("resource")}>
              {RESOURCES.map((r) => <option key={r}>{r}</option>)}
            </select>
          )}
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">HTTP Method</label>
          <select className={cls} value={form.method} onChange={set("method")}>
            {METHODS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
      </div>

      {/* Input preview */}
      <div className="bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs font-mono text-gray-500">
        <span className="text-gray-600">OPA input: </span>
        {`{ subject: "${form.subject}", service: "${form.service}", resource: "${form.resource}", method: "${form.method}" }`}
      </div>

      {/* Test button */}
      <button
        onClick={run}
        disabled={isPending}
        className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500
                   disabled:opacity-60 text-white text-sm font-medium rounded-lg transition-colors"
      >
        {isPending
          ? <><Loader2 size={15} className="animate-spin" /> Testing…</>
          : <><Play size={15} /> Test Policy</>
        }
      </button>

      {/* Error state — show real error + fix hint */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg space-y-2">
          <div className="flex items-start gap-2 text-red-400 text-sm font-medium">
            <XCircle size={15} className="mt-0.5 shrink-0" />
            {error.message}
          </div>
          {error.message?.includes("Cannot reach OPA") && (
            <div className="flex items-start gap-2 text-yellow-400 text-xs">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              Fix: Run <code className="bg-gray-800 px-1 rounded">docker compose up opa -d</code> then
              check <span className="text-yellow-300">Settings → OPA URL</span> matches your OPA address.
            </div>
          )}
          {error.message?.includes("CORS") && (
            <div className="flex items-start gap-2 text-yellow-400 text-xs">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              CORS error: OPA must have <code className="bg-gray-800 px-1 rounded">--cors-allowed-origins</code> set,
              or use the gateway proxy route instead.
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {data && (
        <div className={`p-4 rounded-lg border text-sm space-y-3 ${
          data.allow
            ? "bg-emerald-500/10 border-emerald-500/30"
            : "bg-red-500/10 border-red-500/30"
        }`}>
          <div className="flex items-center gap-2 font-semibold text-base">
            {data.allow
              ? <><CheckCircle size={18} className="text-emerald-400" /><span className="text-emerald-400">ALLOWED</span></>
              : <><XCircle    size={18} className="text-red-400" />    <span className="text-red-400">DENIED</span></>
            }
          </div>

          <div className="text-gray-300 text-xs">
            <span className="text-gray-500">Reason:</span>{" "}
            {data.reason || "(no reason returned)"}
          </div>

          {data.audit?.roles?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-gray-500 text-xs">Roles:</span>
              {data.audit.roles.map((r) => (
                <span key={r} className="text-xs px-1.5 py-0.5 bg-gray-800 text-gray-300 rounded">
                  {r}
                </span>
              ))}
            </div>
          )}

          {/* Raw audit object for transparency */}
          {data.audit && Object.keys(data.audit).length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-gray-500 hover:text-gray-300">
                Raw OPA audit object
              </summary>
              <pre className="mt-2 bg-gray-950 rounded p-2 text-gray-400 overflow-x-auto text-xs leading-relaxed">
                {JSON.stringify(data.audit, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Info box — how it works */}
      {!data && !error && !isPending && (
        <div className="flex items-start gap-2 text-xs text-gray-600 p-3 bg-gray-900/50 rounded-lg border border-gray-800">
          <Info size={13} className="mt-0.5 shrink-0 text-gray-600" />
          Select a subject, service, resource, and method above, then click Test Policy.
          The query goes directly to OPA — no mTLS required from the browser.
        </div>
      )}
    </div>
  );
}
