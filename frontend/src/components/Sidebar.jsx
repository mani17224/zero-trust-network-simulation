/**
 * components/Sidebar.jsx — Collapsible sidebar navigation for the Zero Trust Dashboard.
 * @param {{ collapsed: boolean, onToggle: function }} props
 */
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Shield, KeyRound, Network,
  ScrollText, Settings, ChevronLeft, ChevronRight,
  ShieldCheck,
} from "lucide-react";
import useStore from "../store";

const NAV_ITEMS = [
  { path: "/",             label: "Dashboard",         icon: LayoutDashboard },
  { path: "/policies",     label: "Policy Manager",    icon: Shield },
  { path: "/certificates", label: "Certificates",      icon: KeyRound },
  { path: "/topology",     label: "Network Topology",  icon: Network },
  { path: "/logs",         label: "Audit Logs",        icon: ScrollText },
  { path: "/settings",     label: "Settings",          icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, toggleSidebar } = useStore();

  return (
    <aside
      className={`
        flex flex-col bg-gray-900 border-r border-gray-800 transition-all duration-300
        ${sidebarCollapsed ? "w-16" : "w-56"}
      `}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-800">
        <ShieldCheck className="text-emerald-400 shrink-0" size={22} />
        {!sidebarCollapsed && (
          <span className="font-semibold text-white text-sm leading-tight">
            Zero Trust<br />
            <span className="text-gray-400 font-normal text-xs">Network Sim</span>
          </span>
        )}
      </div>

      {/* Nav links */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path;
          return (
            <Link
              key={path}
              to={path}
              title={sidebarCollapsed ? label : undefined}
              className={`
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium
                transition-colors duration-150
                ${active
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
                }
              `}
            >
              <Icon size={18} className="shrink-0" />
              {!sidebarCollapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center py-4 border-t border-gray-800
                   text-gray-500 hover:text-white transition-colors"
        aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </aside>
  );
}
