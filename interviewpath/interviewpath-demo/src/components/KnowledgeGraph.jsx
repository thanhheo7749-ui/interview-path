import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useTranslation } from 'react-i18next';
import { LAYER_COLORS } from '../lib/layers.js';

const FALLBACK_COLOR = '#64748b';
const NODE_SIZE = 10;
const TWO_PI = Math.PI * 2;

const colorOf = (node) => LAYER_COLORS[node.layer] || FALLBACK_COLOR;

// graph: { nodes: [{ id, title, type, layer }], links: [{ source, target, relation }] }
function KnowledgeGraph({ graph, selectedNode, onSelectNode }) {
  const { t } = useTranslation();
  const graphRef = useRef();
  const containerRef = useRef(null);
  const [size, setSize] = useState({ width: 900, height: 560 });
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const selectedId = selectedNode?.id;

  const graphData = useMemo(
    () => ({
      nodes: graph.nodes.map((node) => ({ ...node })),
      links: graph.links.map((link, index) => ({ ...link, id: `${link.source}-${link.target}-${link.relation}-${index}` })),
    }),
    [graph],
  );
  const denseGraph = graphData.nodes.length > 34;

  const connectedNodeIds = useMemo(() => {
    if (!selectedId) return new Set();
    const ids = new Set([selectedId]);
    graph.links.forEach((link) => {
      if (link.source === selectedId || link.target === selectedId) {
        ids.add(link.source);
        ids.add(link.target);
      }
    });
    return ids;
  }, [graph.links, selectedId]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.max(360, Math.round(width)), height: Math.max(360, Math.round(height)) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const forceGraph = graphRef.current;
    if (!forceGraph) return undefined;
    forceGraph.d3Force('charge')?.strength?.(denseGraph ? -390 : -260);
    const linkForce = forceGraph.d3Force('link');
    linkForce?.distance?.(denseGraph ? 176 : 150);
    linkForce?.strength?.(denseGraph ? 0.34 : 0.42);
    forceGraph.d3Force('center')?.strength?.(denseGraph ? 0.03 : 0.042);
    forceGraph.d3ReheatSimulation();
    const fitTimer = setTimeout(() => forceGraph.zoomToFit(720, denseGraph ? 72 : 48), 180);
    return () => clearTimeout(fitTimer);
  }, [denseGraph, graphData]);

  const isActiveLink = useCallback(
    (link) => Boolean(selectedId) && (getNodeId(link.source) === selectedId || getNodeId(link.target) === selectedId),
    [selectedId],
  );

  const drawNode = useCallback(
    (node, ctx, globalScale) => {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
      const selected = selectedId === node.id;
      const connected = connectedNodeIds.has(node.id);
      const hovered = hoveredNodeId === node.id;
      const dimmed = selectedId && !connected;
      const radius = NODE_SIZE * (selected ? 1.18 : connected ? 1.08 : 1);
      const color = colorOf(node);

      ctx.save();
      ctx.globalAlpha = dimmed ? 0.28 : 1;
      if (selected || connected) {
        const haloRadius = radius * (selected ? 3.15 : 1.95);
        const halo = ctx.createRadialGradient(node.x, node.y, radius * 0.7, node.x, node.y, haloRadius);
        halo.addColorStop(0, withAlpha(color, selected ? 0.44 : 0.22));
        halo.addColorStop(1, withAlpha(color, 0));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(node.x, node.y, haloRadius, 0, TWO_PI);
        ctx.fill();
      }

      ctx.shadowColor = withAlpha(color, selected ? 0.62 : 0.22);
      ctx.shadowBlur = selected ? 28 : connected ? 18 : 8;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, TWO_PI);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.lineWidth = (selected ? 3.2 : connected ? 2.1 : 1.35) / globalScale;
      ctx.strokeStyle = selected ? 'rgba(255, 255, 255, 0.96)' : 'rgba(226, 232, 240, 0.72)';
      ctx.stroke();

      const showLabel = denseGraph ? selected || hovered : !dimmed || hovered;
      if (showLabel) drawNodeLabel(ctx, node, radius, globalScale, { selected, connected: connected || hovered, color, dense: denseGraph });
      ctx.restore();
    },
    [connectedNodeIds, denseGraph, hoveredNodeId, selectedId],
  );

  const drawNodeHitArea = useCallback((node, paintColor, ctx) => {
    ctx.fillStyle = paintColor;
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_SIZE + 18, 0, TWO_PI);
    ctx.fill();
  }, []);

  const drawLinkLabel = useCallback(
    (link, ctx, globalScale) => {
      const { source, target } = link;
      if (typeof source?.x !== 'number' || typeof target?.x !== 'number') return;
      const active = isActiveLink(link);
      if (denseGraph && !active) return;

      const x = (source.x + target.x) / 2;
      const y = (source.y + target.y) / 2;
      const fontSize = (denseGraph ? 8.4 : 9.5) / globalScale;
      const paddingX = 6 / globalScale;
      const paddingY = 3.5 / globalScale;

      ctx.save();
      ctx.globalAlpha = selectedId && !active ? 0.28 : active ? 0.96 : 0.72;
      ctx.font = `700 ${fontSize}px "Plus Jakarta Sans", sans-serif`;
      const width = ctx.measureText(link.relation).width + paddingX * 2;
      const height = fontSize + paddingY * 2;
      drawRoundRect(ctx, x - width / 2, y - height / 2, width, height, 8 / globalScale);
      ctx.fillStyle = active ? 'rgba(15, 23, 42, 0.84)' : 'rgba(15, 23, 42, 0.62)';
      ctx.fill();
      ctx.fillStyle = active ? '#e0f2fe' : '#cbd5e1';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(link.relation, x, y + 0.25 / globalScale);
      ctx.restore();
    },
    [denseGraph, isActiveLink, selectedId],
  );

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden rounded-2xl bg-slate-950"
      role="img"
      aria-label={t('graph.canvasLabel')}
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[length:34px_34px,34px_34px]" />
      <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[330px] rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-[11px] font-semibold leading-4 text-slate-300 backdrop-blur">
        {t('graph.hint')}
      </div>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={size.width}
        height={size.height}
        backgroundColor="rgba(2, 6, 23, 0)"
        nodeId="id"
        nodeVal={NODE_SIZE}
        nodeCanvasObjectMode={() => 'replace'}
        nodeCanvasObject={drawNode}
        nodePointerAreaPaint={drawNodeHitArea}
        nodeLabel={(node) => node.title}
        linkLabel={(link) => link.relation}
        linkColor={(link) => (isActiveLink(link) ? 'rgba(125, 211, 252, 0.82)' : selectedId ? 'rgba(71, 85, 105, 0.3)' : 'rgba(148, 163, 184, 0.46)')}
        linkWidth={(link) => (isActiveLink(link) ? 2.25 : selectedId ? 0.7 : 1.15)}
        linkCurvature={0.05}
        linkCanvasObjectMode={() => 'after'}
        linkCanvasObject={drawLinkLabel}
        enableNodeDrag
        enablePanInteraction
        enableZoomInteraction
        showPointerCursor={(object) => Boolean(object)}
        minZoom={0.45}
        maxZoom={3.6}
        d3VelocityDecay={denseGraph ? 0.28 : 0.24}
        warmupTicks={denseGraph ? 90 : 70}
        cooldownTicks={200}
        onNodeClick={(node) => onSelectNode(node)}
        onNodeHover={(node) => setHoveredNodeId(node?.id || null)}
        onNodeDrag={(node) => {
          node.fx = node.x;
          node.fy = node.y;
        }}
        onNodeDragEnd={(node) => {
          node.fx = undefined;
          node.fy = undefined;
        }}
      />
    </div>
  );
}

function getNodeId(nodeOrId) {
  return nodeOrId && typeof nodeOrId === 'object' ? nodeOrId.id : nodeOrId;
}

function withAlpha(hex, alpha) {
  const bigint = Number.parseInt(hex.replace('#', ''), 16);
  return `rgba(${(bigint >> 16) & 255}, ${(bigint >> 8) & 255}, ${bigint & 255}, ${alpha})`;
}

function drawNodeLabel(ctx, node, radius, globalScale, state) {
  const lines = splitLabel(node.title, state.dense ? 16 : 18);
  const fontSize = (state.dense ? 9.8 : 11.5) / globalScale;
  const lineHeight = (state.dense ? 11.8 : 13.5) / globalScale;
  const paddingX = (state.dense ? 6 : 7) / globalScale;
  const paddingY = (state.dense ? 4 : 5) / globalScale;
  const labelY = node.y + radius + 11 / globalScale;

  ctx.font = `800 ${fontSize}px "Plus Jakarta Sans", sans-serif`;
  const width = Math.max(...lines.map((line) => ctx.measureText(line).width)) + paddingX * 2;
  const height = lines.length * lineHeight + paddingY * 2;

  drawRoundRect(ctx, node.x - width / 2, labelY, width, height, 9 / globalScale);
  ctx.fillStyle = state.selected ? 'rgba(240, 253, 250, 0.94)' : state.connected ? 'rgba(15, 23, 42, 0.78)' : 'rgba(15, 23, 42, 0.58)';
  ctx.fill();
  if (state.selected || state.connected) {
    ctx.strokeStyle = withAlpha(state.color, state.selected ? 0.76 : 0.46);
    ctx.lineWidth = 1 / globalScale;
    ctx.stroke();
  }

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = state.selected ? '#0f172a' : '#f8fafc';
  lines.forEach((line, index) => {
    ctx.fillText(line, node.x, labelY + paddingY + lineHeight * index + lineHeight / 2);
  });
}

function splitLabel(label, maxLength = 18) {
  if (label.length <= maxLength) return [label];
  const lines = [];
  let current = '';
  label.split(' ').forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxLength && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });
  if (current) lines.push(current);
  return lines.slice(0, 2).map((line, index) => (index === 1 && lines.length > 2 ? `${line}...` : line));
}

function drawRoundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export default KnowledgeGraph;
