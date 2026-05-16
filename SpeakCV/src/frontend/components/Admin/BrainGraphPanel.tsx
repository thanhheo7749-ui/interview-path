"use client";

import dynamic from "next/dynamic";
import { useMemo, useRef, useState } from "react";

type Candidate = {
  id: number;
  kind: "node" | "edge";
  payload?: any;
  confidence?: number;
};

type GraphNode = {
  id: string;
  type: string;
  labelShort: string;
  labelFull: string;
  confidence: number;
  degree: number;
  importanceScore: number;
  color: string;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationType: string;
  confidence: number;
};

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const typeColor = (type: string) => {
  if (type === "principle") return "#8b5cf6";
  if (type === "rubric") return "#06b6d4";
  if (type === "red_flag") return "#ef4444";
  if (type === "follow_up_strategy") return "#22c55e";
  if (type === "question_pattern") return "#f59e0b";
  return "#64748b";
};

export function BrainGraphPanel({ candidates }: { candidates: Candidate[] }) {
  const fgRef = useRef<any>(null);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);

  const adapted = useMemo(() => {
    const nodeCandidates = candidates.filter((c) => c.kind === "node");
    const edgeCandidates = candidates.filter((c) => c.kind === "edge");

    const nodes: GraphNode[] = nodeCandidates.map((c) => {
      const label = c.payload?.label || c.payload?.type || "node";
      return {
        id: c.payload?.id || `n_${c.id}`,
        type: c.payload?.type || "domain_knowledge",
        labelShort: label.length > 16 ? `${label.slice(0, 16)}...` : label,
        labelFull: label,
        confidence: Number(c.confidence || 0),
        degree: 0,
        importanceScore: Number(c.confidence || 0),
        color: typeColor(c.payload?.type || "domain_knowledge"),
      };
    });

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const edges: GraphEdge[] = edgeCandidates
      .map((c) => ({
        id: c.payload?.id || `e_${c.id}`,
        source: String(c.payload?.source || ""),
        target: String(c.payload?.target || ""),
        relationType: c.payload?.type || "supports",
        confidence: Number(c.confidence || 0),
      }))
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target));

    edges.forEach((e) => {
      const s = nodeMap.get(e.source);
      const t = nodeMap.get(e.target);
      if (s) s.degree += 1;
      if (t) t.degree += 1;
    });

    nodes.forEach((n) => {
      n.importanceScore = n.degree * 0.7 + n.confidence * 0.3;
    });

    const topLabelNodeIds = new Set(
      [...nodes]
        .sort((a, b) => b.importanceScore - a.importanceScore)
        .slice(0, 12)
        .map((n) => n.id)
    );

    return { nodes, edges, topLabelNodeIds };
  }, [candidates]);

  const visibleNodes = useMemo(() => {
    if (selectedType === "all") return adapted.nodes;
    return adapted.nodes.filter((n) => n.type === selectedType);
  }, [adapted.nodes, selectedType]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  const visibleEdges = useMemo(
    () => adapted.edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)),
    [adapted.edges, visibleNodeIds]
  );

  const focusedNeighborhood = useMemo(() => {
    if (!focusedNodeId) return null;
    const set = new Set<string>([focusedNodeId]);
    visibleEdges.forEach((e) => {
      if (e.source === focusedNodeId) set.add(e.target);
      if (e.target === focusedNodeId) set.add(e.source);
    });
    return set;
  }, [focusedNodeId, visibleEdges]);

  const types = useMemo(() => ["all", ...Array.from(new Set(adapted.nodes.map((n) => n.type)))], [adapted.nodes]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedType(t)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${selectedType === t ? "bg-purple-600 text-white border-purple-500" : "bg-slate-800 text-slate-300 border-slate-700"}`}
          >
            {t}
          </button>
        ))}
        <button
          onClick={() => {
            setSelectedType("all");
            setFocusedNodeId(null);
            fgRef.current?.zoomToFit?.(500, 30);
          }}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-700 text-white"
        >
          Reset view
        </button>
      </div>

      <div className="rounded-lg border border-slate-700 bg-slate-900/60 h-[420px] overflow-hidden">
        {visibleNodes.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">
            No graph data yet. Upload a file, run parsing, then refresh job.
          </div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            graphData={{
              nodes: visibleNodes as any,
              links: visibleEdges.map((e) => ({ ...e, source: e.source as any, target: e.target as any })) as any,
            }}
            nodeRelSize={5}
            cooldownTicks={120}
            linkWidth={(link: any) => (focusedNeighborhood && !(focusedNeighborhood.has(link.source.id) && focusedNeighborhood.has(link.target.id)) ? 0.4 : 1)}
            linkColor={(link: any) => (focusedNeighborhood && !(focusedNeighborhood.has(link.source.id) && focusedNeighborhood.has(link.target.id)) ? "rgba(100,116,139,0.18)" : "rgba(148,163,184,0.35)")}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const inFocus = !focusedNeighborhood || focusedNeighborhood.has(node.id);
              const radius = 4 + Math.min(node.degree, 12) * 0.7;
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
              ctx.fillStyle = inFocus ? node.color : "rgba(100,116,139,0.35)";
              ctx.fill();

              if (adapted.topLabelNodeIds.has(node.id)) {
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px sans-serif`;
                ctx.fillStyle = inFocus ? "#e2e8f0" : "rgba(148,163,184,0.5)";
                ctx.fillText(node.labelShort, node.x + radius + 2, node.y + 3);
              }
            }}
            onNodeClick={(node: any) => setFocusedNodeId(node.id)}
            onNodeHover={(node: any) => {
              if (!node) return;
            }}
            nodeLabel={(node: any) => `${node.labelFull}\nType: ${node.type}\nConfidence: ${node.confidence.toFixed(2)}\nDegree: ${node.degree}`}
          />
        )}
      </div>
    </div>
  );
}
