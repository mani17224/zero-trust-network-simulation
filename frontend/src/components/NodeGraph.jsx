/**
 * components/NodeGraph.jsx — Interactive SVG network topology graph.
 * Shows services as nodes with mTLS connection edges color-coded by status.
 * @param {{ selectedNode: string|null, onSelectNode: function }} props
 */
import { useEffect, useRef, useState } from "react";
import useStore from "../store";

// Node definitions with fixed layout positions
const NODES = [
  { id: "client",           label: "Client",           x: 120, y: 240, role: "external",   color: "#6b7280" },
  { id: "gateway",          label: "Gateway",          x: 300, y: 240, role: "gateway",    color: "#10b981" },
  { id: "service-a",        label: "Auth Service",     x: 500, y: 120, role: "service",    color: "#3b82f6" },
  { id: "service-b",        label: "Data Service",     x: 500, y: 240, role: "service",    color: "#8b5cf6" },
  { id: "service-c",        label: "Admin Service",    x: 500, y: 360, role: "service",    color: "#f59e0b" },
  { id: "opa",              label: "OPA",              x: 300, y: 100, role: "infra",      color: "#ec4899" },
  { id: "vault",            label: "Vault PKI",        x: 300, y: 380, role: "infra",      color: "#f97316" },
  { id: "monitoring",       label: "Prometheus",       x: 680, y: 180, role: "monitoring", color: "#14b8a6" },
];

// Edge definitions: [from, to, status]
const EDGES = [
  ["client",    "gateway",   "active"],
  ["gateway",   "service-a", "active"],
  ["gateway",   "service-b", "active"],
  ["gateway",   "service-c", "active"],
  ["gateway",   "opa",       "active"],
  ["gateway",   "vault",     "active"],
  ["service-a", "monitoring","active"],
  ["service-b", "monitoring","active"],
  ["service-c", "monitoring","active"],
  ["gateway",   "monitoring","active"],
];

const STATUS_COLORS = {
  active:   "#10b981",
  denied:   "#ef4444",
  inactive: "#374151",
};

const NODE_DETAILS = {
  gateway:    { roles: ["writer", "reader"], connections: 5, requests: 142 },
  "service-a":{ roles: ["reader"],           connections: 2, requests: 58 },
  "service-b":{ roles: ["reader","writer"],  connections: 3, requests: 97 },
  "service-c":{ roles: ["admin"],            connections: 2, requests: 23 },
  opa:        { roles: ["policy engine"],    connections: 1, requests: 142 },
  vault:      { roles: ["PKI CA"],           connections: 1, requests: 12 },
  monitoring: { roles: ["monitoring"],       connections: 4, requests: 0 },
  client:     { roles: ["external"],         connections: 1, requests: 45 },
};

export default function NodeGraph({ selectedNode, onSelectNode }) {
  const svgRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));

  return (
    <div className="relative w-full h-full">
      <svg
        ref={svgRef}
        viewBox="0 0 800 480"
        className="w-full h-full"
        style={{ background: "transparent" }}
      >
        {/* Defs: arrowhead marker */}
        <defs>
          <marker id="arrow-active"   markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill={STATUS_COLORS.active} />
          </marker>
          <marker id="arrow-denied"   markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill={STATUS_COLORS.denied} />
          </marker>
          <marker id="arrow-inactive" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill={STATUS_COLORS.inactive} />
          </marker>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Edges */}
        {EDGES.map(([fromId, toId, status], i) => {
          const from = nodeById[fromId];
          const to   = nodeById[toId];
          if (!from || !to) return null;

          const color = STATUS_COLORS[status];
          const isHighlighted =
            selectedNode === fromId || selectedNode === toId;

          // Offset line endpoints to edge of circle (r=28)
          const dx = to.x - from.x;
          const dy = to.y - from.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const ux = dx / dist;
          const uy = dy / dist;
          const r = 28;
          const x1 = from.x + ux * r;
          const y1 = from.y + uy * r;
          const x2 = to.x   - ux * (r + 8);
          const y2 = to.y   - uy * (r + 8);

          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={color}
              strokeWidth={isHighlighted ? 2.5 : 1.5}
              strokeOpacity={isHighlighted ? 1 : 0.5}
              strokeDasharray={status === "inactive" ? "6 4" : undefined}
              markerEnd={`url(#arrow-${status})`}
              style={{ transition: "stroke-opacity 0.2s" }}
            />
          );
        })}

        {/* Nodes */}
        {NODES.map((node) => {
          const isSelected = selectedNode === node.id;
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-pointer"
              onClick={() => onSelectNode(isSelected ? null : node.id)}
              onMouseEnter={() => setTooltip(node.id)}
              onMouseLeave={() => setTooltip(null)}
            >
              {/* Glow ring on selection */}
              {isSelected && (
                <circle r={38} fill="none" stroke={node.color} strokeWidth={2}
                        strokeOpacity={0.4} filter="url(#glow)" />
              )}
              {/* Node circle */}
              <circle
                r={28}
                fill={isSelected ? node.color : "#1f2937"}
                stroke={node.color}
                strokeWidth={isSelected ? 0 : 2}
                style={{ transition: "all 0.2s" }}
              />
              {/* Node label */}
              <text
                textAnchor="middle"
                dy="4"
                fontSize="9"
                fontWeight="600"
                fill={isSelected ? "#fff" : node.color}
                style={{ userSelect: "none" }}
              >
                {node.label.split(" ").map((word, wi) => (
                  <tspan key={wi} x="0" dy={wi === 0 ? (node.label.includes(" ") ? -5 : 0) : 12}>
                    {word}
                  </tspan>
                ))}
              </text>
              {/* Role badge */}
              <text
                textAnchor="middle"
                dy={42}
                fontSize="8"
                fill="#6b7280"
                style={{ userSelect: "none" }}
              >
                {node.role}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Selected node detail panel */}
      {selectedNode && NODE_DETAILS[selectedNode] && (
        <div className="absolute top-4 right-4 bg-gray-900 border border-gray-700
                        rounded-xl p-4 w-52 shadow-xl">
          <h3 className="text-white font-semibold text-sm mb-3">{selectedNode}</h3>
          <dl className="space-y-2 text-xs">
            <div className="flex justify-between">
              <dt className="text-gray-500">Roles</dt>
              <dd className="text-gray-300">{NODE_DETAILS[selectedNode].roles.join(", ")}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Connections</dt>
              <dd className="text-emerald-400">{NODE_DETAILS[selectedNode].connections}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Requests</dt>
              <dd className="text-blue-400">{NODE_DETAILS[selectedNode].requests}</dd>
            </div>
          </dl>
          <button
            onClick={() => onSelectNode(null)}
            className="mt-3 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Deselect
          </button>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 flex items-center gap-4 text-xs text-gray-500">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <span key={status} className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5" style={{ background: color }} />
            {status}
          </span>
        ))}
      </div>
    </div>
  );
}
