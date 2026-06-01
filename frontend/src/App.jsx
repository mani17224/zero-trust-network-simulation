/**
 * App.jsx — Root application component with routing and layout.
 */
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import PolicyManager from "./pages/PolicyManager";
import CertificateManager from "./pages/CertificateManager";
import NetworkTopology from "./pages/NetworkTopology";
import AuditLogs from "./pages/AuditLogs";
import Settings from "./pages/Settings";
import useStore from "./store";

export default function App() {
  const theme = useStore((s) => s.theme);

  return (
    <div className={`${theme === "dark" ? "dark" : ""} flex h-screen overflow-hidden bg-gray-950 text-white`}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/policies"     element={<PolicyManager />} />
          <Route path="/certificates" element={<CertificateManager />} />
          <Route path="/topology"     element={<NetworkTopology />} />
          <Route path="/logs"         element={<AuditLogs />} />
          <Route path="/settings"     element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
