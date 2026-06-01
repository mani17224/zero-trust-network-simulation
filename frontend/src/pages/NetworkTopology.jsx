/**
 * pages/NetworkTopology.jsx — Interactive network topology visualization.
 */
import { Network } from "lucide-react";
import NodeGraph from "../components/NodeGraph";
import useStore from "../store";

export default function NetworkTopology() {
  const { selectedNode, setSelectedNode } = useStore();

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-xl font-bold text-white">Network Topology</h1>
        <p className="text-gray-500 text-sm mt-1">
          Interactive view of service connections and mTLS tunnel status. Click a node to inspect.
        </p>
      </div>

      {/* Legend + stats strip */}
      <div className="flex items-center gap-6 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
          mTLS Active
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500 inline-block" />
          Denied
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-gray-600 inline-block" />
          Inactive
        </span>
        <span className="ml-auto text-gray-600">
          Click any node to see details
        </span>
      </div>

      {/* Main topology graph */}
      <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden min-h-[420px]">
        <NodeGraph
          selectedNode={selectedNode}
          onSelectNode={setSelectedNode}
        />
      </div>

      {/* Service info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { name: "Gateway",      ip: "172.20.0.10", port: 8000, status: "active" },
          { name: "Auth Service", ip: "172.20.0.11", port: 8001, status: "active" },
          { name: "Data Service", ip: "172.20.0.12", port: 8002, status: "active" },
          { name: "Admin Service",ip: "172.20.0.13", port: 8003, status: "active" },
        ].map((svc) => (
          <div key={svc.name}
               className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-white font-medium text-sm">{svc.name}</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            </div>
            <div className="text-gray-500">{svc.ip}:{svc.port}</div>
            <div className="text-emerald-400">mTLS enforced</div>
          </div>
        ))}
      </div>
    </div>
  );
}
