"use client";

import { useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import type { Edge, Node } from "reactflow";
import "reactflow/dist/style.css";

type ValueChainNode = {
  ticker?: string;
  label?: string | null;
};

export type ValueChainData = {
  target: ValueChainNode;
  suppliers?: ValueChainNode[];
  customers?: ValueChainNode[];
  peers?: ValueChainNode[];
};

const ReactFlow = dynamic(() => import("reactflow").then((module) => module.default), {
  ssr: false,
});
const Background = dynamic(() => import("reactflow").then((module) => module.Background), { ssr: false });
const Controls = dynamic(() => import("reactflow").then((module) => module.Controls), { ssr: false });

const NODE_WIDTH = 150;

const nodeStyle = {
  background: "rgba(15,23,42,0.9)",
  color: "#E2E8F0",
  border: "1px solid rgba(99,102,241,0.5)",
  borderRadius: 12,
  padding: 12,
  fontSize: 12,
  width: NODE_WIDTH,
  textAlign: "center" as const,
};

type ValueChainGraphProps = {
  data?: ValueChainData | null;
  onNodeSelect?: (ticker: string) => void;
};

const formatLabel = (node?: ValueChainNode) => node?.label || node?.ticker || "Unknown";

export function ValueChainGraph({ data, onNodeSelect }: ValueChainGraphProps) {
  const { nodes, edges } = useMemo(() => {
    if (!data?.target) {
      return { nodes: [], edges: [] };
    }
    const graphNodes: Node[] = [];
    const graphEdges: Edge[] = [];

    const centerX = 350;
    const centerY = 160;
    graphNodes.push({
      id: "target",
      position: { x: centerX, y: centerY },
      data: { label: formatLabel(data.target), ticker: data.target?.ticker },
      style: {
        ...nodeStyle,
        border: "2px solid rgba(59,130,246,0.8)",
        boxShadow: "0 0 20px rgba(59,130,246,0.3)",
      },
    });

    const addNodes = (
      items: ValueChainNode[] | undefined,
      prefix: string,
      startX: number,
      verticalOffset = 80,
      limit = 4,
    ) => {
      (items || []).slice(0, limit).forEach((item, index) => {
        const id = `${prefix}-${index}`;
        const position = { x: startX, y: centerY + (index - ((items?.length || 0) - 1) / 2) * verticalOffset };
        graphNodes.push({
          id,
          position,
          data: { label: formatLabel(item), ticker: item?.ticker },
          style: nodeStyle,
        });
        if (prefix === "supplier") {
          graphEdges.push({ id: `edge-${id}`, source: id, target: "target", animated: false });
        } else if (prefix === "customer") {
          graphEdges.push({
            id: `edge-${id}`,
            source: "target",
            target: id,
            animated: true,
            style: { stroke: "#34D399" },
          });
        } else if (prefix === "peer") {
          graphEdges.push({
            id: `edge-${id}`,
            source: "target",
            target: id,
            animated: false,
            style: { strokeDasharray: "4 2", stroke: "#A855F7" },
          });
        }
      });
    };

    addNodes(data.suppliers, "supplier", centerX - 220);
    addNodes(data.customers, "customer", centerX + 220);
    addNodes(data.peers, "peer", centerX, 110);

    return { nodes: graphNodes, edges: graphEdges };
  }, [data]);

  const handleNodeClick = useCallback(
    (_event: object, node: Node) => {
      if (!onNodeSelect || node.id === "target") {
        return;
      }
      const tickerValue =
        (typeof node.data?.ticker === "string" && node.data.ticker.trim()) ||
        (typeof node.data?.label === "string" && node.data.label.trim());
      if (tickerValue) {
        onNodeSelect(tickerValue);
      }
    },
    [onNodeSelect],
  );

  if (!data?.target) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-3xl border border-border-subtle bg-surface-1 text-sm text-text-secondary">
        <div className="mb-3 h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-transparent" />
        <p className="text-sm text-slate-300">🤖 AI가 최신 뉴스로 밸류체인을 분석 중입니다...</p>
        <p className="mt-1 text-xs text-slate-500">잠시만 기다리시면 관계도가 생성됩니다.</p>
      </div>
    );
  }

  return (
    <div className="h-[340px] w-full overflow-hidden rounded-3xl border border-border-subtle bg-surface-1">
      {typeof window === "undefined" ? null : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          panOnScroll
          zoomOnScroll
          className="value-chain-flow"
          onNodeClick={handleNodeClick}
        >
          <Background color="#1E293B" gap={16} />
          <Controls />
        </ReactFlow>
      )}
    </div>
  );
}

export default ValueChainGraph;
