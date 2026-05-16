import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { graphCategories } from '../data/mockGraph.js';

const categoryColorMap = new Map(graphCategories.map((category) => [category.label, category.color]));
const TWO_PI = Math.PI * 2;
const priorityLabelIds = new Set([
  'hiring-knowledge-core',
  'company-culture',
  'job-description',
  'company-tech-stack',
  'interview-rubric',
  'candidate-passport-schema',
  'talent-pool-memory',
  'onboarding-playbook',
]);

function KnowledgeGraph({ graph, selectedNode, onSelectNode, pulseMemory, pulseNodeIds = [], memoryHubId, centerNonce }) {
  const graphRef = useRef();
  const containerRef = useRef(null);
  const liveMotionTimerRef = useRef(null);
  const [size, setSize] = useState({ width: 900, height: 560 });
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const selectedId = selectedNode?.id;
  const hubId = memoryHubId || graph.nodes.find((node) => node.kind === 'candidate-passport')?.id;

  const normalizedLinks = useMemo(
    () =>
      (graph.links || graph.edges || []).map((link, index) => {
        const source = link.source || link.from;
        const target = link.target || link.to;
        return {
          ...link,
          id: link.id || `${source}-${target}-${link.label}-${index}`,
          source,
          target,
        };
      }),
    [graph.links, graph.edges],
  );

  const graphData = useMemo(
    () => ({
      nodes: graph.nodes.map((node, index) => ({
        ...node,
        color: node.color || categoryColorMap.get(node.category) || '#64748b',
        size: node.size || 10,
        showLabel: node.showLabel || node.important || priorityLabelIds.has(node.id),
        _delay: index * 0.43,
      })),
      links: normalizedLinks.map((link) => ({ ...link })),
    }),
    [graph.nodes, normalizedLinks],
  );
  const denseGraph = graphData.nodes.length > 34;

  const connectedNodeIds = useMemo(() => {
    if (!selectedId) return new Set();
    const ids = new Set([selectedId]);
    normalizedLinks.forEach((link) => {
      const source = getNodeId(link.source);
      const target = getNodeId(link.target);
      if (source === selectedId || target === selectedId) {
        ids.add(source);
        ids.add(target);
      }
    });
    return ids;
  }, [normalizedLinks, selectedId]);

  const memoryNodeIds = useMemo(() => {
    const ids = new Set([hubId, ...pulseNodeIds]);
    normalizedLinks.forEach((link) => {
      const source = getNodeId(link.source);
      const target = getNodeId(link.target);
      if (source === hubId || target === hubId) {
        ids.add(source);
        ids.add(target);
      }
    });
    return ids;
  }, [hubId, normalizedLinks, pulseNodeIds]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return undefined;

    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({
        width: Math.max(360, Math.round(width)),
        height: Math.max(360, Math.round(height)),
      });
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const forceGraph = graphRef.current;
    if (!forceGraph) return undefined;

    const chargeForce = forceGraph.d3Force('charge');
    const linkForce = forceGraph.d3Force('link');
    const centerForce = forceGraph.d3Force('center');

    if (chargeForce?.strength) chargeForce.strength(denseGraph ? -390 : -260);
    if (linkForce?.distance) {
      linkForce.distance((link) => {
        const baseDistance = denseGraph ? 176 : 150;
        const activeDistance = denseGraph ? 158 : 138;
        const passiveDistance = denseGraph ? 184 : 156;
        return Math.max(link.distance || baseDistance, link.active ? activeDistance : passiveDistance);
      });
      linkForce.strength((link) => link.strength || (denseGraph ? 0.34 : 0.42));
    }
    if (centerForce?.strength) centerForce.strength(denseGraph ? 0.03 : 0.042);

    forceGraph.d3ReheatSimulation();
    const fitTimer = setTimeout(() => forceGraph.zoomToFit(720, denseGraph ? 72 : 48), 180);
    return () => clearTimeout(fitTimer);
  }, [denseGraph, graphData]);

  useEffect(() => {
    if (!centerNonce) return;
    graphRef.current?.zoomToFit(650, denseGraph ? 72 : 48);
    graphRef.current?.d3ReheatSimulation();
  }, [centerNonce, denseGraph]);

  useEffect(() => {
    if (!pulseMemory) return undefined;
    const forceGraph = graphRef.current;
    forceGraph?.d3ReheatSimulation();
    const pulseIds = new Set([hubId, ...pulseNodeIds]);

    const timers = graphData.links
      .filter((link) => isPulseRelationship(link, pulseIds))
      .flatMap((link, linkIndex) =>
        Array.from({ length: 5 }).map((_, particleIndex) =>
          setTimeout(() => forceGraph?.emitParticle(link), linkIndex * 90 + particleIndex * 160),
        ),
      );

    return () => timers.forEach((timer) => clearTimeout(timer));
  }, [graphData.links, hubId, pulseMemory, pulseNodeIds]);

  useEffect(
    () => () => {
      if (liveMotionTimerRef.current) clearTimeout(liveMotionTimerRef.current);
    },
    [],
  );

  const isActiveLink = useCallback(
    (link) => {
      const source = getNodeId(link.source);
      const target = getNodeId(link.target);
      return selectedId ? source === selectedId || target === selectedId : link.active || source === hubId || target === hubId;
    },
    [hubId, selectedId],
  );

  const isPulseLink = useCallback(
    (link) => {
      if (!pulseMemory) return false;
      return isPulseRelationship(link, new Set([hubId, ...pulseNodeIds]));
    },
    [hubId, pulseMemory, pulseNodeIds],
  );

  const drawNode = useCallback(
    (node, ctx, globalScale) => {
      const now = performance.now() / 1000;
      const selected = selectedId === node.id;
      const hubFocused = selectedId === hubId;
      const connected = connectedNodeIds.has(node.id) || (hubFocused && memoryNodeIds.has(node.id));
      const memoryPulse = pulseMemory && memoryNodeIds.has(node.id);
      const hovered = hoveredNodeId === node.id;
      const dimmed = selectedId && !connected && !selected;
      const breathe = 1 + Math.sin(now * 2.1 + node._delay) * (selected || memoryPulse ? 0.07 : 0.035);
      const radius = node.size * breathe * (selected ? 1.18 : connected || memoryPulse ? 1.08 : 1);
      const color = node.color || categoryColorMap.get(node.category) || '#64748b';
      const haloRadius = radius * (selected ? 3.15 : node.id === hubId || node.important || memoryPulse ? 2.45 : connected ? 1.95 : 1.45);
      const shouldShowDenseLabel = selected || hovered || node.showLabel || (connected && node.important && globalScale > 0.72);
      const shouldShowLabel = denseGraph ? shouldShowDenseLabel : !dimmed || node.important || hovered;

      ctx.save();
      ctx.globalAlpha = dimmed ? 0.28 : 1;

      if (selected || connected || node.id === hubId || node.important || memoryPulse) {
        const halo = ctx.createRadialGradient(node.x, node.y, radius * 0.7, node.x, node.y, haloRadius);
        halo.addColorStop(0, withAlpha(color, selected ? 0.44 : memoryPulse ? 0.34 : 0.22));
        halo.addColorStop(0.58, withAlpha(color, selected ? 0.15 : 0.08));
        halo.addColorStop(1, withAlpha(color, 0));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(node.x, node.y, haloRadius, 0, TWO_PI);
        ctx.fill();
      }

      ctx.shadowColor = withAlpha(color, selected ? 0.62 : connected || memoryPulse ? 0.38 : 0.22);
      ctx.shadowBlur = selected ? 28 : connected || memoryPulse ? 18 : node.important ? 14 : 8;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, TWO_PI);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.lineWidth = (selected ? 3.2 : connected || memoryPulse ? 2.1 : 1.35) / globalScale;
      ctx.strokeStyle = selected ? 'rgba(255, 255, 255, 0.96)' : connected || memoryPulse ? 'rgba(255, 255, 255, 0.78)' : 'rgba(226, 232, 240, 0.72)';
      ctx.stroke();

      ctx.fillStyle = 'rgba(2, 6, 23, 0.26)';
      ctx.beginPath();
      ctx.arc(node.x - radius * 0.24, node.y - radius * 0.24, radius * 0.42, 0, TWO_PI);
      ctx.fill();

      ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
      ctx.beginPath();
      ctx.arc(node.x - radius * 0.28, node.y - radius * 0.28, Math.max(1.8 / globalScale, radius * 0.13), 0, TWO_PI);
      ctx.fill();

      if (shouldShowLabel) {
        drawNodeLabel(ctx, node, radius, globalScale, {
          selected,
          connected: connected || hovered,
          dimmed,
          color,
          dense: denseGraph,
        });
      }

      ctx.restore();
    },
    [connectedNodeIds, denseGraph, hoveredNodeId, hubId, memoryNodeIds, pulseMemory, selectedId],
  );

  const drawNodeHitArea = useCallback((node, paintColor, ctx) => {
    ctx.fillStyle = paintColor;
    ctx.beginPath();
    ctx.arc(node.x, node.y, (node.size || 10) + 18, 0, TWO_PI);
    ctx.fill();
  }, []);

  const drawLinkLabel = useCallback(
    (link, ctx, globalScale) => {
      const source = link.source;
      const target = link.target;
      if (typeof source?.x !== 'number' || typeof target?.x !== 'number') return;

      const active = isActiveLink(link);
      const pulse = isPulseLink(link);
      if (denseGraph && !active && !link.showLabel) return;

      const muted = selectedId && !active && !pulse;
      const x = (source.x + target.x) / 2;
      const y = (source.y + target.y) / 2;
      const fontSize = (denseGraph ? 8.4 : 9.5) / globalScale;
      const paddingX = 6 / globalScale;
      const paddingY = 3.5 / globalScale;

      ctx.save();
      ctx.globalAlpha = muted ? 0.28 : active || pulse ? 0.96 : 0.72;
      ctx.font = `700 ${fontSize}px "Plus Jakarta Sans", sans-serif`;
      const textWidth = ctx.measureText(link.label).width;
      const width = textWidth + paddingX * 2;
      const height = fontSize + paddingY * 2;

      drawRoundRect(ctx, x - width / 2, y - height / 2, width, height, 8 / globalScale);
      ctx.fillStyle = active || pulse ? 'rgba(15, 23, 42, 0.84)' : 'rgba(15, 23, 42, 0.62)';
      ctx.fill();
      ctx.strokeStyle = active || pulse ? 'rgba(125, 211, 252, 0.65)' : 'rgba(148, 163, 184, 0.28)';
      ctx.lineWidth = 0.9 / globalScale;
      ctx.stroke();

      ctx.fillStyle = active || pulse ? '#e0f2fe' : '#cbd5e1';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(link.label, x, y + 0.25 / globalScale);
      ctx.restore();
    },
    [denseGraph, isActiveLink, isPulseLink, selectedId],
  );

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden rounded-2xl bg-slate-950"
      aria-label="Interactive force-directed RAG knowledge graph"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_52%_45%,rgba(99,102,241,0.2),transparent_34%),radial-gradient(circle_at_18%_22%,rgba(16,185,129,0.16),transparent_26%),linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[length:100%_100%,100%_100%,34px_34px,34px_34px]" />
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-full border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs font-extrabold text-cyan-100 shadow-lg shadow-cyan-950/30 backdrop-blur">
        Force-directed RAG memory
      </div>
      <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[330px] rounded-2xl border border-white/10 bg-slate-950/62 px-3 py-2 text-[11px] font-semibold leading-4 text-slate-300 backdrop-blur">
        Drag nodes to let nearby evidence rebalance. Click a node to inspect its memory role.
      </div>
      {size.width > 0 && size.height > 0 ? (
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(2, 6, 23, 0)"
          nodeId="id"
          nodeVal={(node) => node.size}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={drawNode}
          nodePointerAreaPaint={drawNodeHitArea}
          nodeLabel={(node) => `${node.label}<br/><span style="color:#94a3b8">${node.category}</span>`}
          linkLabel={(link) => `${link.label}`}
          linkColor={(link) => {
            if (isPulseLink(link)) return 'rgba(45, 212, 191, 0.86)';
            if (isActiveLink(link)) return 'rgba(125, 211, 252, 0.82)';
            if (selectedId) return 'rgba(71, 85, 105, 0.3)';
            return 'rgba(148, 163, 184, 0.46)';
          }}
          linkWidth={(link) => (isPulseLink(link) ? 2.7 : isActiveLink(link) ? 2.25 : selectedId ? 0.7 : 1.15)}
          linkCurvature={0.05}
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={drawLinkLabel}
          linkDirectionalParticles={(link) => (isPulseLink(link) ? 6 : isActiveLink(link) ? 4 : selectedId ? 0 : 1)}
          linkDirectionalParticleSpeed={(link) => (isPulseLink(link) || isActiveLink(link) ? 0.008 : 0.0035)}
          linkDirectionalParticleWidth={(link) => (isPulseLink(link) ? 4.2 : isActiveLink(link) ? 3.1 : 1.6)}
          linkDirectionalParticleColor={(link) => (isPulseLink(link) ? '#5eead4' : isActiveLink(link) ? '#7dd3fc' : '#a78bfa')}
          enableNodeDrag
          enablePanInteraction
          enableZoomInteraction
          showPointerCursor={(object) => Boolean(object)}
          minZoom={0.45}
          maxZoom={3.6}
          d3AlphaMin={0.001}
          d3AlphaDecay={denseGraph ? 0.009 : 0.012}
          d3VelocityDecay={denseGraph ? 0.28 : 0.24}
          warmupTicks={denseGraph ? 90 : 70}
          cooldownTicks={Infinity}
          autoPauseRedraw={false}
          onNodeClick={(node) => {
            onSelectNode(node);
            graphRef.current?.d3ReheatSimulation();
          }}
          onNodeHover={(node) => {
            setHoveredNodeId(node?.id || null);
            const relatedLink = node
              ? graphData.links.find((link) => getNodeId(link.source) === node.id || getNodeId(link.target) === node.id)
              : null;
            if (relatedLink) graphRef.current?.emitParticle(relatedLink);
          }}
          onNodeDrag={(node) => {
            node.fx = node.x;
            node.fy = node.y;
          }}
          onNodeDragEnd={(node) => {
            node.fx = undefined;
            node.fy = undefined;
            graphRef.current?.d3ReheatSimulation();
          }}
          onEngineStop={() => {
            if (liveMotionTimerRef.current) clearTimeout(liveMotionTimerRef.current);
            liveMotionTimerRef.current = setTimeout(() => graphRef.current?.d3ReheatSimulation(), 900);
          }}
        />
      ) : null}
    </div>
  );
}

function getNodeId(nodeOrId) {
  if (nodeOrId && typeof nodeOrId === 'object') return nodeOrId.id;
  return nodeOrId;
}

function isPulseRelationship(link, pulseIds) {
  return pulseIds.has(getNodeId(link.source)) || pulseIds.has(getNodeId(link.target));
}

function withAlpha(hex, alpha) {
  const normalized = hex.replace('#', '');
  const bigint = Number.parseInt(normalized.length === 3 ? normalized.split('').map((char) => char + char).join('') : normalized, 16);
  const red = (bigint >> 16) & 255;
  const green = (bigint >> 8) & 255;
  const blue = bigint & 255;
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function drawNodeLabel(ctx, node, radius, globalScale, state) {
  const lines = splitLabel(node.label, state.dense ? 16 : 18);
  const fontSize = (state.dense ? 9.8 : 11.5) / globalScale;
  const lineHeight = (state.dense ? 11.8 : 13.5) / globalScale;
  const paddingX = (state.dense ? 6 : 7) / globalScale;
  const paddingY = (state.dense ? 4 : 5) / globalScale;
  const labelY = node.y + radius + 11 / globalScale;

  ctx.font = `800 ${fontSize}px "Plus Jakarta Sans", sans-serif`;
  const width = Math.max(...lines.map((line) => ctx.measureText(line).width)) + paddingX * 2;
  const height = lines.length * lineHeight + paddingY * 2;

  drawRoundRect(ctx, node.x - width / 2, labelY, width, height, 9 / globalScale);
  ctx.fillStyle = state.selected
    ? 'rgba(240, 253, 250, 0.94)'
    : state.connected
      ? 'rgba(15, 23, 42, 0.78)'
      : 'rgba(15, 23, 42, 0.58)';
  ctx.fill();

  if (state.selected || state.connected) {
    ctx.strokeStyle = state.selected ? withAlpha(state.color, 0.76) : withAlpha(state.color, 0.46);
    ctx.lineWidth = 1 / globalScale;
    ctx.stroke();
  }

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = state.selected ? '#0f172a' : state.dimmed ? 'rgba(226, 232, 240, 0.68)' : '#f8fafc';
  lines.forEach((line, index) => {
    ctx.fillText(line, node.x, labelY + paddingY + lineHeight * index + lineHeight / 2);
  });
}

function splitLabel(label, maxLength = 18) {
  if (label.length <= maxLength) return [label];

  const words = label.split(' ');
  const lines = [];
  let current = '';

  words.forEach((word) => {
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
  const safeRadius = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + safeRadius, y);
  ctx.lineTo(x + width - safeRadius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  ctx.lineTo(x + width, y + height - safeRadius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
  ctx.lineTo(x + safeRadius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  ctx.lineTo(x, y + safeRadius);
  ctx.quadraticCurveTo(x, y, x + safeRadius, y);
  ctx.closePath();
}

export default KnowledgeGraph;
