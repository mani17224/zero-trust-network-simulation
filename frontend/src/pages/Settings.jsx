/**
 * Settings.jsx — Configure endpoints, test connections, toggle theme.
 * Fixes:
 *   - Shows current VITE_* env var values as defaults
 *   - "Test connection" button for each service
 *   - Real health status (not hardcoded "unreachable")
 *   - Dark/light mode toggle
 */
import { useState } from "react";
import {
  Settings as SettingsIcon, Moon, Sun, CheckCircle, XCircle,
  Loader2, Save, RefreshCw, Terminal, Info,
} from "lucide-react";
import axios from "axios";
import { useHealth } from "../hooks/useMetrics";
import { API_BASE, OPA_BASE } from "../api/client";
import useStore from "../store";

function ServiceRow({ label, url, onTest, status, testing }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
      <div className="min-w-0 flex-1 mr-3">
        <div className="text-sm text-white font-medium">{label}</div>
        <div className="text-xs text-gray-500 font-mono truncate">{url}</div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {status === "idle"     && <span className="text-xs text-gray-600">—</span>}
        {status === "healthy"  && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle size={13} /> OK</span>}
        {status === "error"    && <span className="flex items-center gap-1 text-xs text-red-400"><XCircle size={13} /> Down</span>}
        <button
          onClick={onTest}
          disabled={testing}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700
                     text-gray-300 rounded-lg transition-colors disabled:opacity-50"
        >
          {testing ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
          Test
        </button>
      </div>
    </div>
  );
}

function SettingInput({ label, value, onChange, placeholder, description }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-gray-300">{label}</label>
      {description && <p className="text-xs text-gray-500">{description}</p>}
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm
                   text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500
                   transition-colors font-mono"
      />
    </div>
  );
}

async function testUrl(url, path = "/health") {
  try {
    const r = await axios.get(`${url}${path}`, { timeout: 3000, withCredentials: false });
    return r.status < 400 ? "healthy" : "error";
  } catch {
    return "error";
  }
}

export default function Settings() {
  const {
    theme, toggleTheme,
    opaUrl, setOpaUrl,
    vaultUrl, setVaultUrl,
    gatewayUrl, setGatewayUrl,
    refreshInterval, setRefreshInterval,
  } = useStore();

  const [localGateway, setLocalGateway] = useState(gatewayUrl || API_BASE);
  const [localOpa,     setLocalOpa]     = useState(opaUrl     || OPA_BASE);
  const [localVault,   setLocalVault]   = useState(vaultUrl   || "http://localhost:8200");
  const [saved, setSaved] = useState(false);

  const [statuses, setStatuses] = useState({
    gateway: "idle", opa: "idle", vault: "idle",
    prometheus: "idle", grafana: "idle",
  });
  const [testing, setTesting] = useState({});

  const runTest = async (key, url, path = "/health") => {
    setTesting((t) => ({ ...t, [key]: true }));
    setStatuses((s) => ({ ...s, [key]: "idle" }));
    const result = await testUrl(url, path);
    setStatuses((s) => ({ ...s, [key]: result }));
    setTesting((t) => ({ ...t, [key]: false }));
  };

  const handleSave = () => {
    setGatewayUrl(localGateway);
    setOpaUrl(localOpa);
    setVaultUrl(localVault);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const SERVICES = [
    { key: "gateway",    label: "API Gateway",   url: localGateway,           path: "/health"    },
    { key: "opa",        label: "OPA Engine",    url: localOpa,               path: "/health"    },
    { key: "vault",      label: "Vault PKI",     url: localVault,             path: "/v1/sys/health" },
    { key: "prometheus", label: "Prometheus",    url: "http://localhost:9090", path: "/-/healthy" },
    { key: "grafana",    label: "Grafana",       url: "http://localhost:3001", path: "/api/health"},
  ];

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-white">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">Configure service endpoints and display preferences</p>
      </div>

      {/* Env var info banner */}
      <div className="flex items-start gap-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-xs text-blue-300">
        <Info size={14} className="mt-0.5 shrink-0" />
        <div>
          Default URLs come from <code className="bg-blue-900/40 px-1 rounded">VITE_GATEWAY_URL</code> and{" "}
          <code className="bg-blue-900/40 px-1 rounded">VITE_OPA_URL</code> in your{" "}
          <code className="bg-blue-900/40 px-1 rounded">.env</code> file.
          Current: Gateway = <span className="text-white font-mono">{API_BASE}</span>,
          OPA = <span className="text-white font-mono">{OPA_BASE}</span>
        </div>
      </div>

      {/* Endpoint config */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-5">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          <SettingsIcon size={15} className="text-emerald-400" />
          Endpoint Configuration
        </h2>
        <SettingInput
          label="API Gateway URL"
          value={localGateway}
          onChange={setLocalGateway}
          placeholder={API_BASE}
          description="Base URL for the Zero Trust Gateway (set VITE_GATEWAY_URL in .env)"
        />
        <SettingInput
          label="OPA Policy Engine URL"
          value={localOpa}
          onChange={setLocalOpa}
          placeholder={OPA_BASE}
          description="Used by Policy Tester — direct to OPA (set VITE_OPA_URL in .env)"
        />
        <SettingInput
          label="HashiCorp Vault URL"
          value={localVault}
          onChange={setLocalVault}
          placeholder="http://localhost:8200"
          description="Used by Certificate Manager for renewal operations"
        />
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-gray-300">Refresh Interval</label>
          <p className="text-xs text-gray-500">How often to poll for live metrics</p>
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm
                       text-white focus:outline-none focus:border-emerald-500"
          >
            <option value={2000}>2 seconds</option>
            <option value={5000}>5 seconds (default)</option>
            <option value={10000}>10 seconds</option>
            <option value={30000}>30 seconds</option>
          </select>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500
                     text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Save size={14} />
          {saved ? "Saved ✓" : "Save Settings"}
        </button>
      </div>

      {/* Theme */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-white font-semibold text-sm mb-4">Display</h2>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-300 font-medium">Theme</div>
            <div className="text-xs text-gray-500 mt-0.5">Current: {theme} mode</div>
          </div>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700
                       text-gray-300 text-sm rounded-lg transition-colors border border-gray-700"
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            Switch to {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </div>

      {/* System health */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-white font-semibold text-sm">System Health</h2>
          <button
            onClick={() => SERVICES.forEach((s) => runTest(s.key, s.url, s.path))}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white
                       bg-gray-800 px-2 py-1 rounded-lg transition-colors"
          >
            <RefreshCw size={11} /> Test All
          </button>
        </div>
        {SERVICES.map((s) => (
          <ServiceRow
            key={s.key}
            label={s.label}
            url={s.url}
            status={statuses[s.key]}
            testing={!!testing[s.key]}
            onTest={() => runTest(s.key, s.url, s.path)}
          />
        ))}
      </div>

      {/* Quick reference */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2 mb-3">
          <Terminal size={14} className="text-emerald-400" />
          Quick Test Commands
        </h2>
        <div className="space-y-2 text-xs font-mono">
          {[
            ["Authorized GET", `curl -H "X-Client-Cert-CN: gateway.zerotrust.local" ${localGateway}/records`],
            ["Denied POST",    `curl -X POST -H "X-Client-Cert-CN: service-a.zerotrust.local" ${localGateway}/records`],
            ["No cert (401)",  `curl ${localGateway}/records`],
            ["OPA direct",     `curl -X POST ${localOpa}/v1/data/zerotrust/authz -d '{"input":{"subject":"gateway","service":"service-b","resource":"/records","method":"GET"}}'`],
          ].map(([label, cmd]) => (
            <div key={label}>
              <div className="text-gray-500 mb-0.5"># {label}</div>
              <div className="bg-gray-950 rounded p-2 text-gray-300 overflow-x-auto whitespace-pre">
                {cmd}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
