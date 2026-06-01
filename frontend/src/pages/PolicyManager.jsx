/**
 * pages/PolicyManager.jsx — OPA policy viewer with enable/disable toggle and policy tester.
 */
import { useState } from "react";
import { Shield, Eye, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from "lucide-react";
import { usePolicies } from "../hooks/usePolicies";
import PolicyTester from "../components/PolicyTester";

function RoleBadge({ role }) {
  const colors = {
    any:            "bg-gray-700 text-gray-300",
    any_registered: "bg-blue-900/60 text-blue-300",
    monitoring:     "bg-teal-900/60 text-teal-300",
    gateway:        "bg-emerald-900/60 text-emerald-300",
    reader:         "bg-violet-900/60 text-violet-300",
    writer:         "bg-yellow-900/60 text-yellow-300",
    admin:          "bg-red-900/60 text-red-300",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[role] ?? colors.any}`}>
      {role}
    </span>
  );
}

function RegoViewer({ rego }) {
  // Very basic Rego syntax highlighting
  const highlighted = rego
    .replace(/(allow|default|if|in|not)/g, '<span class="text-purple-400 font-semibold">$1</span>')
    .replace(/(input\.\w+)/g, '<span class="text-emerald-400">$1</span>')
    .replace(/(roles_for_subject|subject_is_registered)/g, '<span class="text-blue-400">$1</span>')
    .replace(/(".*?")/g, '<span class="text-yellow-300">$1</span>')
    .replace(/(#.*)/g, '<span class="text-gray-500 italic">$1</span>');

  return (
    <pre
      className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs font-mono
                 text-gray-300 overflow-x-auto leading-relaxed whitespace-pre-wrap"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

export default function PolicyManager() {
  const { data: policies, isLoading } = usePolicies();
  const [enabled, setEnabled] = useState({});
  const [expanded, setExpanded] = useState(null);

  const togglePolicy = (id) =>
    setEnabled((e) => ({ ...e, [id]: !(e[id] ?? true) }));

  const isEnabled = (id) => enabled[id] ?? true;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Policy Manager</h1>
        <p className="text-gray-500 text-sm mt-1">View and test OPA authorization policies</p>
      </div>

      {/* Policy table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center gap-2">
          <Shield size={16} className="text-emerald-400" />
          <h2 className="text-white font-semibold text-sm">Active Policies</h2>
          <span className="ml-auto text-xs text-gray-500">{policies?.length ?? 0} rules</span>
        </div>

        {isLoading ? (
          <div className="space-y-2 p-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-800 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {(policies ?? []).map((policy) => (
              <div key={policy.id}>
                {/* Row */}
                <div className="flex items-center gap-4 px-5 py-3 hover:bg-gray-800/50 transition-colors">
                  <button
                    onClick={() => togglePolicy(policy.id)}
                    className={`shrink-0 transition-colors ${isEnabled(policy.id) ? "text-emerald-400" : "text-gray-600"}`}
                    title={isEnabled(policy.id) ? "Disable policy" : "Enable policy"}
                  >
                    {isEnabled(policy.id)
                      ? <ToggleRight size={22} />
                      : <ToggleLeft  size={22} />}
                  </button>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${isEnabled(policy.id) ? "text-white" : "text-gray-500 line-through"}`}>
                        {policy.name}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 font-mono mt-0.5">{policy.resource}</div>
                  </div>

                  <RoleBadge role={policy.role} />

                  <button
                    onClick={() => setExpanded(expanded === policy.id ? null : policy.id)}
                    className="p-1.5 text-gray-500 hover:text-gray-300 hover:bg-gray-800
                               rounded-lg transition-colors"
                    title="View Rego"
                  >
                    {expanded === policy.id
                      ? <ChevronUp size={15} />
                      : <Eye size={15} />
                    }
                  </button>
                </div>

                {/* Rego viewer */}
                {expanded === policy.id && (
                  <div className="px-5 pb-4 bg-gray-950/50">
                    <RegoViewer rego={policy.rego} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Policy tester panel */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-white font-semibold text-sm mb-4">Test Policy</h2>
        <p className="text-gray-500 text-xs mb-4">
          Select a subject, service, resource, and method to test the OPA authorization decision.
        </p>
        <PolicyTester />
      </div>
    </div>
  );
}
