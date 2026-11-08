"use client";

import React, { useEffect, useRef, useState } from "react";

export type JourneyStage = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
export type PortalStage = JourneyStage;
export type ExceptionBranchId =
  | null
  | "needs_revision"
  | "withdrawn"
  | "human_alternative"
  | "tech_issue"
  | "not_fitted";

export interface PortalScene3DProps {
  stage: JourneyStage;
  exceptionBranch?: ExceptionBranchId;
  questionCardFlipped?: boolean;
  onToggleQuestionFlip?: () => void;
  evidenceHighlighted?: boolean;
  onToggleEvidenceHighlight?: () => void;
  stage5Beat?: 1 | 2;
  onChangeStage5Beat?: (beat: 1 | 2) => void;
  reducedMotion?: boolean;
  compact?: boolean;
  showControls?: boolean;
  className?: string;
}

// ============================================================================
// 3D MATH & STUDIO LIGHTING ENGINE (Runs natively on HTML5 <canvas> everywhere,
// including Chrome with --use-gl=disabled as well as GPU-accelerated browsers)
// ============================================================================

interface Vec3 {
  x: number;
  y: number;
  z: number;
}

interface ProjectedPoint {
  x: number;
  y: number;
  z: number;
}

interface CameraBasis {
  pos: Vec3;
  right: Vec3;
  up: Vec3;
  forward: Vec3;
  focal: number;
  cx: number;
  cy: number;
}

function vec3(x: number, y: number, z: number): Vec3 {
  return { x, y, z };
}

function sub3(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function add3(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function dot3(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross3(a: Vec3, b: Vec3): Vec3 {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  };
}

function norm3(v: Vec3): Vec3 {
  const len = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / len, y: v.y / len, z: v.z / len };
}

function damp(
  current: number,
  target: number,
  lambda: number,
  dt: number,
): number {
  return current + (target - current) * (1 - Math.exp(-lambda * dt));
}

function rotatePointEuler(p: Vec3, rx: number, ry: number, rz: number): Vec3 {
  let { x, y, z } = p;
  if (rx !== 0) {
    const c = Math.cos(rx);
    const s = Math.sin(rx);
    const ny = y * c - z * s;
    const nz = y * s + z * c;
    y = ny;
    z = nz;
  }
  if (ry !== 0) {
    const c = Math.cos(ry);
    const s = Math.sin(ry);
    const nx = x * c + z * s;
    const nz = -x * s + z * c;
    x = nx;
    z = nz;
  }
  if (rz !== 0) {
    const c = Math.cos(rz);
    const s = Math.sin(rz);
    const nx = x * c - y * s;
    const ny = x * s + y * c;
    x = nx;
    y = ny;
  }
  return { x, y, z };
}

function transformLocalToWorld(
  local: Vec3,
  pos: Vec3,
  rot: [number, number, number],
  scale = 1,
): Vec3 {
  const scaled = {
    x: local.x * scale,
    y: local.y * scale,
    z: local.z * scale,
  };
  const rotated = rotatePointEuler(scaled, rot[0], rot[1], rot[2]);
  return add3(rotated, pos);
}

function buildCameraBasis(
  pos: Vec3,
  target: Vec3,
  fovDeg: number,
  width: number,
  height: number,
): CameraBasis {
  const forward = norm3(sub3(target, pos));
  const worldUp = vec3(0, 1, 0);
  const right = norm3(cross3(forward, worldUp));
  const up = norm3(cross3(right, forward));
  const fovRad = (fovDeg * Math.PI) / 180;
  const focal = (height * 0.5) / Math.tan(fovRad * 0.5);
  return {
    pos,
    right,
    up,
    forward,
    focal,
    cx: width * 0.5,
    cy: height * 0.53,
  };
}

function projectPoint(world: Vec3, cam: CameraBasis): ProjectedPoint {
  const rel = sub3(world, cam.pos);
  const vx = dot3(rel, cam.right);
  const vy = dot3(rel, cam.up);
  const vz = Math.max(0.2, dot3(rel, cam.forward));
  const scale = cam.focal / vz;
  return {
    x: cam.cx + vx * scale,
    y: cam.cy - vy * scale,
    z: vz,
  };
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function shadeColor(hex: string, normal: Vec3, specularBoost = 0): string {
  const [r, g, b] = hexToRgb(hex);
  const keyDir = norm3(vec3(0.52, 0.76, 0.38));
  const fillDir = norm3(vec3(-0.62, 0.34, 0.52));
  const rimDir = norm3(vec3(0.08, 0.52, -0.84));

  const n = norm3(normal);
  const key = Math.max(0, dot3(n, keyDir));
  const fill = Math.max(0, dot3(n, fillDir));
  const rim = Math.max(0, dot3(n, rimDir));

  const lightFactor =
    0.56 + key * 0.44 + fill * 0.16 + rim * 0.1 + specularBoost;

  const shadowMix = Math.max(0, 1 - lightFactor);
  const nr = Math.min(
    255,
    Math.max(0, Math.round(r * lightFactor - shadowMix * 8)),
  );
  const ng = Math.min(
    255,
    Math.max(0, Math.round(g * lightFactor - shadowMix * 3)),
  );
  const nb = Math.min(
    255,
    Math.max(0, Math.round(b * lightFactor + shadowMix * 5)),
  );
  return `rgb(${nr}, ${ng}, ${nb})`;
}

function makeRoundedRectContourXZ(
  w: number,
  d: number,
  radius: number,
  segmentsPerCorner = 4,
): Array<{ x: number; z: number; nx: number; nz: number }> {
  const hw = w * 0.5;
  const hd = d * 0.5;
  const r = Math.min(radius, hw * 0.48, hd * 0.48);
  const pts: Array<{ x: number; z: number; nx: number; nz: number }> = [];

  const corners = [
    { cx: hw - r, cz: hd - r, startAngle: 0 },
    { cx: -hw + r, cz: hd - r, startAngle: Math.PI * 0.5 },
    { cx: -hw + r, cz: -hd + r, startAngle: Math.PI },
    { cx: hw - r, cz: -hd + r, startAngle: Math.PI * 1.5 },
  ];

  for (const corner of corners) {
    for (let i = 0; i <= segmentsPerCorner; i++) {
      const ang =
        corner.startAngle + (i / segmentsPerCorner) * (Math.PI * 0.5);
      const nx = Math.cos(ang);
      const nz = Math.sin(ang);
      pts.push({
        x: corner.cx + nx * r,
        z: corner.cz + nz * r,
        nx,
        nz,
      });
    }
  }
  return pts;
}

interface FacePoly {
  pts: ProjectedPoint[];
  fill: string;
  stroke?: string;
  strokeWidth?: number;
  depth: number;
}

function drawFacePoly(
  ctx: CanvasRenderingContext2D,
  f: FacePoly,
  dpr: number,
) {
  if (f.pts.length < 3) return;
  ctx.beginPath();
  f.pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.fillStyle = f.fill;
  ctx.fill();
  if (f.stroke) {
    ctx.strokeStyle = f.stroke;
    ctx.lineWidth = (f.strokeWidth ?? 0.7) * dpr;
    ctx.lineJoin = "round";
    ctx.stroke();
  }
}

// Immediately render a single 3D rounded prism with internal back-to-front face sorting.
// Calling this in structural layer order (e.g., Base -> Sheet -> Surface Details)
// guarantees zero Z-fighting and zero clipping of surface details!
function drawRoundedBox3D(
  ctx: CanvasRenderingContext2D,
  cam: CameraBasis,
  dpr: number,
  opts: {
    size: [number, number, number];
    pos: Vec3;
    rot?: [number, number, number];
    radius?: number;
    topColor: string;
    sideColor?: string;
    bottomColor?: string;
    rimHighlight?: string;
    scale?: number;
  },
) {
  const [w, h, d] = opts.size;
  const rot: [number, number, number] = opts.rot ?? [0, 0, 0];
  const sc = opts.scale ?? 1;
  if (sc <= 0.01) return;

  const r = opts.radius ?? Math.min(w, d) * 0.08;
  const contour = makeRoundedRectContourXZ(w, d, r, 4);
  const hh = h * 0.5;
  const topColor = opts.topColor;
  const sideColor = opts.sideColor ?? opts.topColor;
  const bottomColor = opts.bottomColor ?? sideColor;

  const topWorld: Vec3[] = [];
  const botWorld: Vec3[] = [];
  const sideNormalsWorld: Vec3[] = [];

  for (const pt of contour) {
    topWorld.push(
      transformLocalToWorld(vec3(pt.x, hh, pt.z), opts.pos, rot, sc),
    );
    botWorld.push(
      transformLocalToWorld(vec3(pt.x, -hh, pt.z), opts.pos, rot, sc),
    );
    sideNormalsWorld.push(
      rotatePointEuler(vec3(pt.nx, 0, pt.nz), rot[0], rot[1], rot[2]),
    );
  }

  const topProj = topWorld.map((p) => projectPoint(p, cam));
  const botProj = botWorld.map((p) => projectPoint(p, cam));

  const sideFaces: FacePoly[] = [];
  const nPts = contour.length;
  for (let i = 0; i < nPts; i++) {
    const next = (i + 1) % nPts;
    const w0 = topWorld[i];
    const w1 = topWorld[next];
    const w2 = botWorld[next];
    const w3 = botWorld[i];

    const quadCenter = {
      x: (w0.x + w1.x + w2.x + w3.x) * 0.25,
      y: (w0.y + w1.y + w2.y + w3.y) * 0.25,
      z: (w0.z + w1.z + w2.z + w3.z) * 0.25,
    };

    const avgNormal = norm3({
      x: (sideNormalsWorld[i].x + sideNormalsWorld[next].x) * 0.5,
      y: (sideNormalsWorld[i].y + sideNormalsWorld[next].y) * 0.5,
      z: (sideNormalsWorld[i].z + sideNormalsWorld[next].z) * 0.5,
    });

    const toCam = sub3(cam.pos, quadCenter);
    if (dot3(avgNormal, toCam) <= -0.05) continue;

    const p0 = topProj[i];
    const p1 = topProj[next];
    const p2 = botProj[next];
    const p3 = botProj[i];
    const avgDepth = (p0.z + p1.z + p2.z + p3.z) * 0.25;

    const shaded = shadeColor(sideColor, avgNormal);
    sideFaces.push({
      pts: [p0, p1, p2, p3],
      fill: shaded,
      stroke: shaded,
      strokeWidth: 0.65,
      depth: avgDepth,
    });
  }

  sideFaces.sort((a, b) => b.depth - a.depth);
  for (const sf of sideFaces) {
    drawFacePoly(ctx, sf, dpr);
  }

  // Draw visible cap (Top or Bottom) on top of the side walls of this prism
  const topNormal = rotatePointEuler(vec3(0, 1, 0), rot[0], rot[1], rot[2]);
  const topCenter = transformLocalToWorld(vec3(0, hh, 0), opts.pos, rot, sc);
  if (dot3(topNormal, sub3(cam.pos, topCenter)) > 0) {
    drawFacePoly(
      ctx,
      {
        pts: topProj,
        fill: shadeColor(topColor, topNormal, 0.04),
        stroke: opts.rimHighlight ?? "rgba(255,255,255,0.45)",
        strokeWidth: 0.9,
        depth: 0,
      },
      dpr,
    );
  } else {
    const botNormal = rotatePointEuler(vec3(0, -1, 0), rot[0], rot[1], rot[2]);
    drawFacePoly(
      ctx,
      {
        pts: botProj,
        fill: shadeColor(bottomColor, botNormal),
        depth: 0,
      },
      dpr,
    );
  }
}

// Draw a 3D Upright Panel (such as a Monitor Housing, Screen, Tilted Calendar Board, or Speech Card)
// where the thickness is along local Z (`size: [widthX, heightY, thicknessZ]`), so the front face (+Z)
// is the main display surface and the perimeter walls wrap around the XY rectangle!
function drawPanelZ3D(
  ctx: CanvasRenderingContext2D,
  cam: CameraBasis,
  dpr: number,
  opts: {
    size: [number, number, number]; // [width X, height Y, thickness Z]
    pos: Vec3;
    rot?: [number, number, number];
    radius?: number;
    frontColor: string;
    edgeColor?: string;
    rimHighlight?: string;
    scale?: number;
  },
) {
  const [w, h, t] = opts.size;
  const baseRot = opts.rot ?? [0, 0, 0];
  // Rotate +90° around local X so local Y becomes +Z (front face) and local Z becomes -Y
  const panelRot: [number, number, number] = [
    baseRot[0] + Math.PI * 0.5,
    baseRot[1],
    baseRot[2],
  ];
  drawRoundedBox3D(ctx, cam, dpr, {
    size: [w, t, h],
    pos: opts.pos,
    rot: panelRot,
    radius: opts.radius,
    topColor: opts.frontColor,
    sideColor: opts.edgeColor ?? opts.frontColor,
    bottomColor: opts.edgeColor ?? opts.frontColor,
    rimHighlight: opts.rimHighlight,
    scale: opts.scale,
  });
}

function drawProjectedShadowEllipse(
  ctx: CanvasRenderingContext2D,
  cam: CameraBasis,
  center: Vec3,
  rx: number,
  rz: number,
  rotY: number,
  color: string,
  blurPx: number,
) {
  const segs = 28;
  const pts: ProjectedPoint[] = [];
  for (let i = 0; i < segs; i++) {
    const a = (i / segs) * Math.PI * 2;
    const lx = Math.cos(a) * rx;
    const lz = Math.sin(a) * rz;
    const wx = center.x + lx * Math.cos(rotY) + lz * Math.sin(rotY);
    const wz = center.z - lx * Math.sin(rotY) + lz * Math.cos(rotY);
    pts.push(projectPoint(vec3(wx, center.y, wz), cam));
  }

  ctx.save();
  if (blurPx > 0) {
    ctx.filter = `blur(${blurPx}px)`;
  }
  ctx.beginPath();
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

function drawSphere3D(
  ctx: CanvasRenderingContext2D,
  cam: CameraBasis,
  center: Vec3,
  radius: number,
  baseHex: string,
  highlightHex = "#FFFFFF",
) {
  const pCenter = projectPoint(center, cam);
  const pEdge = projectPoint(
    add3(center, {
      x: cam.right.x * radius,
      y: cam.right.y * radius,
      z: cam.right.z * radius,
    }),
    cam,
  );
  const rPx = Math.max(2, Math.hypot(pEdge.x - pCenter.x, pEdge.y - pCenter.y));

  ctx.save();
  const grad = ctx.createRadialGradient(
    pCenter.x - rPx * 0.32,
    pCenter.y - rPx * 0.35,
    rPx * 0.08,
    pCenter.x,
    pCenter.y,
    rPx,
  );
  grad.addColorStop(0, highlightHex);
  grad.addColorStop(0.28, shadeColor(baseHex, vec3(0.4, 0.8, 0.4), 0.1));
  grad.addColorStop(0.78, baseHex);
  grad.addColorStop(1, shadeColor(baseHex, vec3(-0.5, -0.6, -0.4)));

  ctx.beginPath();
  ctx.arc(pCenter.x, pCenter.y, rPx, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.restore();
}

interface SceneLoopProps {
  stage: JourneyStage;
  exceptionBranch: ExceptionBranchId;
  questionCardFlipped: boolean;
  evidenceHighlighted: boolean;
  stage5Beat: 1 | 2;
  reducedMotion: boolean;
  isInView: boolean;
}

export function StaticPortalFallback({
  stage = 0,
  exceptionBranch = null,
}: {
  stage?: JourneyStage;
  exceptionBranch?: ExceptionBranchId;
}) {
  return (
    <PortalScene3D
      stage={stage}
      exceptionBranch={exceptionBranch}
      reducedMotion={true}
      compact={true}
      showControls={false}
    />
  );
}

export default function PortalScene3D({
  stage,
  exceptionBranch = null,
  questionCardFlipped = false,
  onToggleQuestionFlip,
  evidenceHighlighted = false,
  onToggleEvidenceHighlight,
  stage5Beat = 2,
  onChangeStage5Beat,
  reducedMotion,
  compact = false,
  showControls = false,
  className = "",
}: PortalScene3DProps) {
  "use no memo";
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(
    () => {
      if (typeof window === "undefined" || !window.matchMedia) return false;
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    },
  );

  const [isInView, setIsInView] = useState<boolean>(true);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsInView(entry.isIntersecting);
      },
      { rootMargin: "120px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const effectiveReducedMotion = reducedMotion ?? prefersReducedMotion;

  const propsRef = useRef<SceneLoopProps>({
    stage,
    exceptionBranch,
    questionCardFlipped,
    evidenceHighlighted,
    stage5Beat,
    reducedMotion: effectiveReducedMotion,
    isInView,
  });

  useEffect(() => {
    propsRef.current = {
      stage,
      exceptionBranch,
      questionCardFlipped,
      evidenceHighlighted,
      stage5Beat,
      reducedMotion: effectiveReducedMotion,
      isInView,
    };
  }, [
    stage,
    exceptionBranch,
    questionCardFlipped,
    evidenceHighlighted,
    stage5Beat,
    effectiveReducedMotion,
    isInView,
  ]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    return startInterviewSceneLoop(canvas, container, propsRef);
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative w-full ${
        compact
          ? "h-[320px] sm:h-[360px]"
          : "h-[440px] sm:h-[520px] lg:h-[580px]"
      } ${className}`}
    >
      {showControls && (
        <div className="absolute right-3 top-3 z-10 flex flex-wrap items-center gap-1.5">
          {stage === 3 && onToggleQuestionFlip && (
            <button
              type="button"
              onClick={onToggleQuestionFlip}
              aria-pressed={questionCardFlipped}
              className="rounded-full border border-[#DEE5ED] bg-white/95 px-3 py-1.5 text-xs font-bold text-[#183153] shadow-sm transition hover:border-[#7963BE]"
            >
              {questionCardFlipped ? "Đang xem mặt sau thẻ" : "Lật thẻ câu hỏi"}
            </button>
          )}

          {stage === 5 && onChangeStage5Beat && (
            <div className="inline-flex rounded-full border border-[#DEE5ED] bg-white/95 p-0.5 shadow-sm">
              <button
                type="button"
                onClick={() => onChangeStage5Beat(1)}
                className={`rounded-full px-2.5 py-1 text-xs font-bold transition ${
                  stage5Beat === 1
                    ? "bg-[#087F78] text-white"
                    : "text-[#586779] hover:text-[#183153]"
                }`}
              >
                Nhịp 1: Đặt lịch
              </button>
              <button
                type="button"
                onClick={() => onChangeStage5Beat(2)}
                className={`rounded-full px-2.5 py-1 text-xs font-bold transition ${
                  stage5Beat === 2
                    ? "bg-[#087F78] text-white"
                    : "text-[#586779] hover:text-[#183153]"
                }`}
              >
                Nhịp 2: Bàn phỏng vấn
              </button>
            </div>
          )}

          {stage === 6 && onToggleEvidenceHighlight && (
            <button
              type="button"
              onClick={onToggleEvidenceHighlight}
              aria-pressed={evidenceHighlighted}
              className="rounded-full border border-[#DEE5ED] bg-white/95 px-3 py-1.5 text-xs font-bold text-[#183153] shadow-sm transition hover:border-[#087F78]"
            >
              {evidenceHighlighted ? "Đang sáng bằng chứng" : "Mở bằng chứng"}
            </button>
          )}
        </div>
      )}

      <canvas
        ref={canvasRef}
        className="block h-full w-full"
        aria-label={`Cảnh bàn phỏng vấn với hai phía đối thoại (Chặng ${stage})`}
      />
    </div>
  );
}

function startInterviewSceneLoop(
  canvas: HTMLCanvasElement,
  container: HTMLDivElement,
  propsRef: React.MutableRefObject<SceneLoopProps>,
): () => void {
  "use no memo";
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};

  let animId = 0;
  let lastTime = performance.now();
  let elapsed = 0;

  const camPos = vec3(1.52, 2.38, 4.45);
  const camLook = vec3(0.0, 0.1, 0.0);

  let jdX = -1.48;
  let jdY = 0.21;
  let jdZ = 0.34;

  let cvX = 1.42;
  let cvY = 0.21;
  let cvZ = 0.36;

  let calScale = 1.0;
  let sysY = 0.78;
  let sysScale = 0.88;
  let candY = 0.72;
  let candScale = 0.88;

  let qFlipRotY = 0;
  let qLiftY = 0.18;
  let qScale = 0.0;

  let kgScale = 0.0;
  let reportScale = 0.0;
  let mgrScale = 0.0;

  const waveHeights = [0.5, 0.8, 0.6, 0.95, 0.65, 0.85, 0.55];

  const renderFrame = (now: number) => {
    const dt = Math.min(0.05, Math.max(0.001, (now - lastTime) / 1000));
    lastTime = now;

    const {
      stage: curStage,
      exceptionBranch: curEx,
      questionCardFlipped: curFlip,
      evidenceHighlighted: curEv,
      stage5Beat: curBeat,
      reducedMotion: curReduced,
      isInView: curInView,
    } = propsRef.current;

    if (!curInView) {
      animId = requestAnimationFrame(renderFrame);
      return;
    }

    elapsed += dt;
    const clockT = now / 1000;

    const rect = container.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const targetW = Math.max(300, Math.round(rect.width * dpr));
    const targetH = Math.max(240, Math.round(rect.height * dpr));
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }

    const W = canvas.width;
    const H = canvas.height;
    ctx.save();
    ctx.clearRect(0, 0, W, H);

    // 1. 3D Camera Choreography per stage (Framed so the entire table, legs, monitor & candidate fit cleanly)
    const camTargets: Record<
      JourneyStage,
      { pos: [number, number, number]; look: [number, number, number] }
    > = {
      0: { pos: [1.36, 2.32, 4.25], look: [0.0, 0.08, 0.0] },
      1: { pos: [-0.95, 2.25, 4.05], look: [-0.18, 0.1, 0.05] },
      2: { pos: [-1.1, 2.28, 4.05], look: [-0.24, 0.16, 0.0] },
      3: { pos: [-0.72, 2.18, 3.95], look: [-0.15, 0.15, 0.08] },
      4: { pos: [1.28, 2.24, 4.08], look: [0.22, 0.12, 0.04] },
      5:
        curBeat === 1
          ? { pos: [0.88, 2.18, 3.92], look: [0.04, 0.1, 0.16] }
          : { pos: [0.72, 2.22, 4.12], look: [0.02, 0.15, 0.0] },
      6: { pos: [0.45, 2.22, 4.05], look: [0.0, 0.1, 0.12] },
      7: { pos: [1.08, 2.3, 4.22], look: [0.0, 0.15, -0.02] },
    };

    const introPullback =
      curStage === 0 && !curReduced
        ? Math.max(0, 0.45 * Math.exp(-elapsed * 2.2))
        : 0;

    const tCam = camTargets[curStage];
    camPos.x = damp(camPos.x, tCam.pos[0] + introPullback * 0.35, 4.2, dt);
    camPos.y = damp(camPos.y, tCam.pos[1] + introPullback * 0.22, 4.2, dt);
    camPos.z = damp(camPos.z, tCam.pos[2] + introPullback * 0.85, 4.2, dt);

    camLook.x = damp(camLook.x, tCam.look[0], 4.5, dt);
    camLook.y = damp(camLook.y, tCam.look[1], 4.5, dt);
    camLook.z = damp(camLook.z, tCam.look[2], 4.5, dt);

    const cam = buildCameraBasis(camPos, camLook, 33.5, W, H);

    // 2. Staged Choreography of JD, CV, Calendar, and Dialogue Slabs
    const jdReady = curReduced || elapsed > 0.22;
    jdX = damp(jdX, jdReady ? -1.04 : -1.48, 4.8, dt);
    jdY = damp(jdY, curStage === 1 ? 0.24 : 0.21, 4.8, dt);
    jdZ = damp(jdZ, curStage === 1 || curStage === 3 ? 0.36 : 0.32, 4.8, dt);

    const cvReady = curReduced || elapsed > 0.68;
    cvX = damp(cvX, cvReady ? 0.88 : 1.38, 4.8, dt);
    cvY = damp(cvY, curStage === 4 ? 0.24 : 0.21, 4.8, dt);
    cvZ = damp(cvZ, curStage === 4 ? 0.38 : 0.34, 4.8, dt);

    const calEmp = curStage === 1 || (curStage === 5 && curBeat === 1);
    calScale = damp(calScale, calEmp ? 1.12 : 1.0, 4.5, dt);

    const dialogueReady = curReduced || elapsed > 1.25;
    const cyclePhase = clockT % 8.0;

    const sysActive =
      dialogueReady && (curStage === 0 || curStage === 5 || curStage === 3);
    const sysTurn =
      !curReduced && cyclePhase >= 0.4 && cyclePhase < 3.6 ? 0.035 : 0.0;
    sysY = damp(sysY, (sysActive ? 0.78 : 0.68) + sysTurn, 4.5, dt);
    sysScale = damp(sysScale, sysActive ? 1.0 : 0.88, 4.5, dt);

    const candReady = curReduced || elapsed > 1.85;
    const candActive =
      candReady && (curStage === 0 || curStage === 5 || curStage === 6);
    const candTurn =
      !curReduced && cyclePhase >= 3.2 && cyclePhase < 6.8 ? 0.04 : 0.0;
    candY = damp(candY, (candActive ? 0.72 : 0.62) + candTurn, 4.5, dt);
    candScale = damp(candScale, candActive ? 1.0 : 0.88, 4.5, dt);

    const showQ = curStage === 3 || curFlip;
    qScale = damp(qScale, showQ ? 1.0 : 0.0, 5.5, dt);
    qFlipRotY = damp(qFlipRotY, curFlip ? Math.PI : 0, 6.0, dt);
    qLiftY = damp(qLiftY, showQ ? 0.46 : 0.18, 4.8, dt);

    kgScale = damp(
      kgScale,
      curStage === 2 || curStage === 3 ? 1.0 : 0.0,
      4.5,
      dt,
    );

    const showRep = curStage === 6 || curStage === 7 || curEv;
    reportScale = damp(reportScale, showRep ? 1.0 : 0.0, 5.0, dt);

    const showMgr = curStage === 7 || curEx === "human_alternative";
    mgrScale = damp(mgrScale, showMgr ? 1.0 : 0.0, 5.0, dt);

    for (let i = 0; i < waveHeights.length; i++) {
      const isSpeaking =
        !curReduced &&
        dialogueReady &&
        (curStage === 0 || curStage === 5) &&
        cyclePhase < 5.8;
      const targetH = isSpeaking
        ? 0.38 + Math.abs(Math.sin(clockT * 4.4 + i * 0.75)) * 0.62
        : 0.4 + (i % 3) * 0.18;
      waveHeights[i] = damp(waveHeights[i], targetH, 8.0, dt);
    }

    const accentStatusColor =
      curEx === "withdrawn"
        ? "#B54747"
        : curEx === "needs_revision" || curEx === "tech_issue"
          ? "#AD661B"
          : "#087F78";

    // ======================================================================
    // PASS 1: FLOOR CONTACT SHADOWS & SOFT AMBIENT SHADOWS (y = -0.68)
    // ======================================================================
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(0.0, -0.68, 0.0),
      1.85,
      1.15,
      -0.24,
      "rgba(24, 49, 83, 0.13)",
      16 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(-1.24, -0.67, 0.0),
      0.24,
      0.74,
      -0.24,
      "rgba(16, 34, 59, 0.25)",
      7 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(1.24, -0.67, 0.0),
      0.24,
      0.74,
      -0.24,
      "rgba(16, 34, 59, 0.25)",
      7 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(1.12, -0.67, -0.28),
      0.38,
      0.38,
      0,
      "rgba(16, 34, 59, 0.2)",
      9 * dpr,
    );

    // ======================================================================
    // PASS 2: UNDER-TABLE STRUCTURE (LEGS, CROSSBAR, APRON, CHAIR BASE)
    // ======================================================================
    const underFaces: FacePoly[] = [];
    const addUnderBox = (opts: Parameters<typeof drawRoundedBox3D>[3]) => {
      // Collect into underFaces for unified depth sorting under the table
      const [w, h, d] = opts.size;
      const rot: [number, number, number] = opts.rot ?? [0, 0, 0];
      const r = opts.radius ?? Math.min(w, d) * 0.08;
      const contour = makeRoundedRectContourXZ(w, d, r, 3);
      const hh = h * 0.5;
      const topW = contour.map((pt) =>
        transformLocalToWorld(vec3(pt.x, hh, pt.z), opts.pos, rot),
      );
      const botW = contour.map((pt) =>
        transformLocalToWorld(vec3(pt.x, -hh, pt.z), opts.pos, rot),
      );
      const norms = contour.map((pt) =>
        rotatePointEuler(vec3(pt.nx, 0, pt.nz), rot[0], rot[1], rot[2]),
      );
      const topP = topW.map((p) => projectPoint(p, cam));
      const botP = botW.map((p) => projectPoint(p, cam));
      for (let i = 0; i < contour.length; i++) {
        const next = (i + 1) % contour.length;
        const avgN = norm3(add3(norms[i], norms[next]));
        const qc = {
          x: (topW[i].x + botW[next].x) * 0.5,
          y: (topW[i].y + botW[next].y) * 0.5,
          z: (topW[i].z + botW[next].z) * 0.5,
        };
        if (dot3(avgN, sub3(cam.pos, qc)) <= -0.05) continue;
        const sh = shadeColor(opts.sideColor ?? opts.topColor, avgN);
        underFaces.push({
          pts: [topP[i], topP[next], botP[next], botP[i]],
          fill: sh,
          stroke: sh,
          strokeWidth: 0.6,
          depth: (topP[i].z + topP[next].z + botP[next].z + botP[i].z) * 0.25,
        });
      }
      const topN = rotatePointEuler(vec3(0, 1, 0), rot[0], rot[1], rot[2]);
      const topC = transformLocalToWorld(vec3(0, hh, 0), opts.pos, rot);
      if (dot3(topN, sub3(cam.pos, topC)) > 0) {
        underFaces.push({
          pts: topP,
          fill: shadeColor(opts.topColor, topN, 0.04),
          depth:
            topP.reduce((a, p) => a + p.z, 0) / topP.length - 0.01,
        });
      }
    };

    // Chair Base & Stem
    addUnderBox({
      size: [0.54, 0.05, 0.54],
      pos: vec3(1.12, -0.62, -0.28),
      rot: [0, -0.54, 0],
      radius: 0.24,
      topColor: "#23436E",
      sideColor: "#183153",
    });
    addUnderBox({
      size: [0.11, 0.54, 0.11],
      pos: vec3(1.12, -0.34, -0.28),
      rot: [0, -0.54, 0],
      radius: 0.04,
      topColor: "#23436E",
      sideColor: "#183153",
    });
    addUnderBox({
      size: [0.58, 0.09, 0.52],
      pos: vec3(1.06, -0.04, -0.22),
      rot: [0, -0.54, 0],
      radius: 0.04,
      topColor: "#23436E",
      sideColor: "#183153",
    });

    // Left Trestle Leg Assembly
    addUnderBox({
      size: [0.16, 0.045, 1.34],
      pos: vec3(-1.26, -0.64, 0),
      radius: 0.02,
      topColor: "#183153",
      sideColor: "#10223B",
    });
    addUnderBox({
      size: [0.15, 0.065, 1.3],
      pos: vec3(-1.26, -0.59, 0),
      radius: 0.022,
      topColor: "#E5DFD0",
      sideColor: "#CFC8B6",
    });
    addUnderBox({
      size: [0.125, 0.6, 0.125],
      pos: vec3(-1.24, -0.3, 0.52),
      rot: [0.08, 0, -0.05],
      radius: 0.028,
      topColor: "#2B4F80",
      sideColor: "#1E3A5F",
    });
    addUnderBox({
      size: [0.125, 0.6, 0.125],
      pos: vec3(-1.24, -0.3, -0.52),
      rot: [-0.08, 0, -0.05],
      radius: 0.028,
      topColor: "#2B4F80",
      sideColor: "#1E3A5F",
    });

    // Right Trestle Leg Assembly
    addUnderBox({
      size: [0.16, 0.045, 1.34],
      pos: vec3(1.26, -0.64, 0),
      radius: 0.02,
      topColor: "#183153",
      sideColor: "#10223B",
    });
    addUnderBox({
      size: [0.15, 0.065, 1.3],
      pos: vec3(1.26, -0.59, 0),
      radius: 0.022,
      topColor: "#E5DFD0",
      sideColor: "#CFC8B6",
    });
    addUnderBox({
      size: [0.125, 0.6, 0.125],
      pos: vec3(1.24, -0.3, 0.52),
      rot: [0.08, 0, 0.05],
      radius: 0.028,
      topColor: "#2B4F80",
      sideColor: "#1E3A5F",
    });
    addUnderBox({
      size: [0.125, 0.6, 0.125],
      pos: vec3(1.24, -0.3, -0.52),
      rot: [-0.08, 0, 0.05],
      radius: 0.028,
      topColor: "#2B4F80",
      sideColor: "#1E3A5F",
    });

    // Central Crossbar & Collar
    addUnderBox({
      size: [2.48, 0.075, 0.1],
      pos: vec3(0, -0.39, 0),
      radius: 0.022,
      topColor: "#2B4F80",
      sideColor: "#183153",
    });
    addUnderBox({
      size: [0.34, 0.095, 0.13],
      pos: vec3(0, -0.39, 0),
      radius: 0.024,
      topColor: "#0A968E",
      sideColor: "#087F78",
    });

    // Under-Table Navy Apron
    addUnderBox({
      size: [2.88, 0.13, 1.48],
      pos: vec3(0, -0.04, 0),
      radius: 0.035,
      topColor: "#23436E",
      sideColor: "#183153",
    });

    underFaces.sort((a, b) => b.depth - a.depth);
    for (const f of underFaces) {
      drawFacePoly(ctx, f, dpr);
    }

    // ======================================================================
    // PASS 3: DOUBLE-STEPPED ARCHITECTURAL TABLETOP SLAB (Ordered bottom -> top)
    // ======================================================================
    drawRoundedBox3D(ctx, cam, dpr, {
      size: [3.28, 0.16, 1.84],
      pos: vec3(0, 0.075, 0),
      radius: 0.08,
      topColor: "#EAE4D6",
      sideColor: "#D5CEBC",
      rimHighlight: "rgba(255,255,255,0.65)",
    });

    drawRoundedBox3D(ctx, cam, dpr, {
      size: [3.14, 0.055, 1.7],
      pos: vec3(0, 0.16, 0),
      radius: 0.065,
      topColor: "#FCFBF7",
      sideColor: "#E5DFD0",
      rimHighlight: "rgba(255,255,255,0.88)",
    });

    drawRoundedBox3D(ctx, cam, dpr, {
      size: [1.68, 0.018, 1.0],
      pos: vec3(-0.04, 0.188, -0.02),
      radius: 0.035,
      topColor: "#EFEAE0",
      sideColor: "#DED7C7",
      rimHighlight: "rgba(24,49,83,0.08)",
    });

    drawRoundedBox3D(ctx, cam, dpr, {
      size: [1.16, 0.022, 0.055],
      pos: vec3(-0.02, 0.192, -0.06),
      radius: 0.012,
      topColor: accentStatusColor,
      sideColor: accentStatusColor,
    });

    // ======================================================================
    // PASS 4: TABLETOP CONTACT SHADOWS UNDER DESKTOP OBJECTS
    // ======================================================================
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(-0.82, 0.19, -0.18),
      0.34,
      0.26,
      0.46,
      "rgba(24, 49, 83, 0.22)",
      5 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(-0.42, 0.19, 0.02),
      0.13,
      0.13,
      0,
      "rgba(24, 49, 83, 0.2)",
      4 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(jdX, 0.19, jdZ),
      0.38,
      0.46,
      0.36,
      "rgba(24, 49, 83, 0.2)",
      5 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(cvX, 0.19, cvZ),
      0.38,
      0.46,
      -0.34,
      "rgba(24, 49, 83, 0.2)",
      5 * dpr,
    );
    drawProjectedShadowEllipse(
      ctx,
      cam,
      vec3(-0.08, 0.19, 0.46),
      0.36 * calScale,
      0.22 * calScale,
      -0.18,
      "rgba(24, 49, 83, 0.22)",
      5 * dpr,
    );

    // ======================================================================
    // PASS 5: COMPOSITE 3D OBJECTS SORTED BY GROUP DEPTH (BACK-TO-FRONT),
    //         WITH EXACT STRUCTURAL LAYER ORDER INSIDE EACH OBJECT!
    // ======================================================================
    interface RenderableGroup {
      depth: number;
      draw: () => void;
    }
    const groups: RenderableGroup[] = [];

    // Group 1: Manager Figure at Head of Table (Stage 7 / H1)
    if (mgrScale > 0.02) {
      const mgrPos = vec3(0.05, 0.34, -0.68);
      groups.push({
        depth: projectPoint(mgrPos, cam).z,
        draw: () => {
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.5, 0.38, 0.26],
            pos: mgrPos,
            radius: 0.09,
            topColor: "#23436E",
            sideColor: "#183153",
            scale: mgrScale,
          });
          drawSphere3D(
            ctx,
            cam,
            vec3(0.05, 0.64, -0.68),
            0.14 * mgrScale,
            "#287A55",
            "#86EFAC",
          );
        },
      });
    }

    // Group 2: SpeakCV 3D Interview Terminal (Left Side of Table)
    const monOrigin = vec3(-0.82, 0.19, -0.18);
    const monRot: [number, number, number] = [0, 0.46, 0];
    groups.push({
      depth: projectPoint(vec3(-0.82, 0.48, -0.18), cam).z,
      draw: () => {
        // 1. Cast Base & Stone Inlay
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.54, 0.055, 0.38],
          pos: transformLocalToWorld(vec3(0, 0.028, 0), monOrigin, monRot),
          rot: monRot,
          radius: 0.03,
          topColor: "#2B4F80",
          sideColor: "#183153",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.38, 0.022, 0.24],
          pos: transformLocalToWorld(vec3(0, 0.058, 0.02), monOrigin, monRot),
          rot: monRot,
          radius: 0.015,
          topColor: "#EAE4D6",
          sideColor: "#D2CBB8",
        });
        // 2. Angled Neck & Rear Boss
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.12, 0.38, 0.095],
          pos: transformLocalToWorld(vec3(0, 0.21, -0.07), monOrigin, monRot),
          rot: [-0.16, 0.46, 0],
          radius: 0.025,
          topColor: "#2B4F80",
          sideColor: "#183153",
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.44, 0.28, 0.065],
          pos: transformLocalToWorld(vec3(0, 0.48, -0.075), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.025,
          frontColor: "#2B4F80",
          edgeColor: "#183153",
        });
        // 3. Thick Rear Navy Housing
        drawPanelZ3D(ctx, cam, dpr, {
          size: [1.04, 0.66, 0.095],
          pos: transformLocalToWorld(vec3(0, 0.5, -0.028), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.045,
          frontColor: "#23436E",
          edgeColor: "#183153",
          rimHighlight: "rgba(255,255,255,0.28)",
        });
        // 4. White Front Bezel Frame
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.98, 0.6, 0.046],
          pos: transformLocalToWorld(vec3(0, 0.5, 0.022), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.035,
          frontColor: "#FFFFFF",
          edgeColor: "#DCE4EE",
          rimHighlight: "rgba(255,255,255,0.95)",
        });
        // 5. Recessed Screen Canvas
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.88, 0.5, 0.018],
          pos: transformLocalToWorld(vec3(0, 0.5, 0.042), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.02,
          frontColor: "#F2F8F8",
          edgeColor: "#DCEFEB",
        });
        // 6. Screen UI Elements (Header, AI Badge, 7 Extruded Waveform Bars, Footer)
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.8, 0.068, 0.018],
          pos: transformLocalToWorld(vec3(0, 0.67, 0.052), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.01,
          frontColor: "#0A968E",
          edgeColor: "#087F78",
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.19, 0.22, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.28, 0.48, 0.052),
            monOrigin,
            monRot,
          ),
          rot: [-0.05, 0.46, 0],
          radius: 0.012,
          frontColor: "#DCEFEB",
          edgeColor: "#CBE6E2",
        });
        drawSphere3D(
          ctx,
          cam,
          transformLocalToWorld(vec3(-0.28, 0.49, 0.068), monOrigin, monRot),
          0.048,
          "#087F78",
          "#A7F3D0",
        );

        const waveOffsets = [-0.12, -0.04, 0.04, 0.12, 0.2, 0.28, 0.36];
        waveOffsets.forEach((wx, idx) => {
          const barH = 0.24 * waveHeights[idx];
          const barColor = idx % 2 === 0 ? "#087F78" : "#7963BE";
          drawPanelZ3D(ctx, cam, dpr, {
            size: [0.046, barH, 0.026],
            pos: transformLocalToWorld(vec3(wx, 0.48, 0.056), monOrigin, monRot),
            rot: [-0.05, 0.46, 0],
            radius: 0.01,
            frontColor: barColor,
            edgeColor: barColor,
          });
        });

        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.8, 0.045, 0.018],
          pos: transformLocalToWorld(vec3(0, 0.31, 0.052), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.008,
          frontColor: "#23436E",
          edgeColor: "#183153",
        });
        // 7. Top Webcam Pill & Lens
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.22, 0.052, 0.05],
          pos: transformLocalToWorld(vec3(0, 0.81, 0.02), monOrigin, monRot),
          rot: [-0.05, 0.46, 0],
          radius: 0.018,
          frontColor: "#2B4F80",
          edgeColor: "#183153",
        });
        drawSphere3D(
          ctx,
          cam,
          transformLocalToWorld(vec3(0, 0.81, 0.048), monOrigin, monRot),
          0.015,
          "#087F78",
          "#6EE7B7",
        );
      },
    });

    // Group 3: Studio Desk Microphone Pod
    groups.push({
      depth: projectPoint(vec3(-0.42, 0.25, 0.02), cam).z,
      draw: () => {
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.18, 0.04, 0.18],
          pos: vec3(-0.42, 0.21, 0.02),
          radius: 0.08,
          topColor: "#2B4F80",
          sideColor: "#183153",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.14, 0.02, 0.14],
          pos: vec3(-0.42, 0.235, 0.02),
          radius: 0.06,
          topColor: "#0A968E",
          sideColor: "#087F78",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.065, 0.13, 0.065],
          pos: vec3(-0.42, 0.29, 0.02),
          rot: [0, 0, -0.14],
          radius: 0.028,
          topColor: "#2B4F80",
          sideColor: "#183153",
        });
      },
    });

    // Group 4: Candidate Seated in Studio Chair (Right Side of Table)
    const candOrigin = vec3(0.98, 0.02, -0.14);
    const candRot: [number, number, number] = [0, -0.54, 0];
    groups.push({
      depth: projectPoint(vec3(0.98, 0.36, -0.14), cam).z,
      draw: () => {
        // Backrest Outer Stone Shell & Inner Navy Cushion
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.58, 0.54, 0.05],
          pos: transformLocalToWorld(
            vec3(0.14, 0.35, -0.39),
            candOrigin,
            candRot,
          ),
          rot: [-0.08, -0.54, 0],
          radius: 0.04,
          frontColor: "#EAE4D6",
          edgeColor: "#D2CBB8",
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.6, 0.56, 0.08],
          pos: transformLocalToWorld(
            vec3(0.14, 0.35, -0.34),
            candOrigin,
            candRot,
          ),
          rot: [-0.08, -0.54, 0],
          radius: 0.045,
          frontColor: "#23436E",
          edgeColor: "#183153",
        });
        // Candidate Torso, Collar & Head Sphere
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.56, 0.44, 0.32],
          pos: transformLocalToWorld(
            vec3(0.06, 0.28, -0.1),
            candOrigin,
            candRot,
          ),
          rot: candRot,
          radius: 0.12,
          topColor: "#4B8FD6",
          sideColor: "#387BC1",
          rimHighlight: "rgba(255,255,255,0.4)",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.17, 0.09, 0.17],
          pos: transformLocalToWorld(
            vec3(0.06, 0.53, -0.1),
            candOrigin,
            candRot,
          ),
          rot: candRot,
          radius: 0.07,
          topColor: "#FCFBF7",
          sideColor: "#E2DDD0",
        });
        drawSphere3D(
          ctx,
          cam,
          transformLocalToWorld(vec3(0.06, 0.69, -0.1), candOrigin, candRot),
          0.165,
          "#183153",
          "#6482A8",
        );
      },
    });

    // Group 5: JD Document Binder Stack (Foreground-Left)
    const jdOrigin = vec3(jdX, jdY, jdZ);
    const jdRot: [number, number, number] = [0, 0.36, 0];
    groups.push({
      depth: projectPoint(jdOrigin, cam).z,
      draw: () => {
        // 1. Purple Binder Base
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.64, 0.05, 0.8],
          pos: jdOrigin,
          rot: jdRot,
          radius: 0.022,
          topColor: "#8B76CE",
          sideColor: "#6B54B2",
        });
        // 2. Offset Cream Middle Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.58, 0.038, 0.73],
          pos: transformLocalToWorld(
            vec3(0.025, 0.038, -0.01),
            jdOrigin,
            jdRot,
          ),
          rot: [0, 0.29, 0],
          radius: 0.016,
          topColor: "#F5F2EA",
          sideColor: "#DDD6C5",
        });
        // 3. Top White JD Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.57, 0.042, 0.72],
          pos: transformLocalToWorld(vec3(0.01, 0.072, 0.01), jdOrigin, jdRot),
          rot: [0, 0.4, 0],
          radius: 0.016,
          topColor: "#FFFFFF",
          sideColor: "#E2E8F0",
          rimHighlight: "rgba(255,255,255,0.95)",
        });
        // 4. Crisp Header, Requirement Lines & Approval Stamp ON TOP of the White JD Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.4, 0.02, 0.08],
          pos: transformLocalToWorld(
            vec3(-0.03, 0.096, -0.21),
            jdOrigin,
            jdRot,
          ),
          rot: [0, 0.4, 0],
          radius: 0.008,
          topColor: "#183153",
          sideColor: "#10223B",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.36, 0.016, 0.048],
          pos: transformLocalToWorld(
            vec3(-0.05, 0.095, -0.08),
            jdOrigin,
            jdRot,
          ),
          rot: [0, 0.4, 0],
          radius: 0.006,
          topColor: "#94A3B8",
          sideColor: "#64748B",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.32, 0.016, 0.048],
          pos: transformLocalToWorld(vec3(-0.07, 0.095, 0.01), jdOrigin, jdRot),
          rot: [0, 0.4, 0],
          radius: 0.006,
          topColor: "#94A3B8",
          sideColor: "#64748B",
        });
        const jdSealColor = curEx === "needs_revision" ? "#AD661B" : "#287A55";
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.28, 0.024, 0.095],
          pos: transformLocalToWorld(vec3(0.07, 0.097, 0.19), jdOrigin, jdRot),
          rot: [0, 0.4, 0],
          radius: 0.01,
          topColor: jdSealColor,
          sideColor: jdSealColor,
        });
      },
    });

    // Group 6: CV & Profile Folder Stack (Foreground-Right)
    const cvOrigin = vec3(cvX, cvY, cvZ);
    const cvRot: [number, number, number] = [0, -0.34, 0];
    groups.push({
      depth: projectPoint(cvOrigin, cam).z,
      draw: () => {
        // 1. Candidate Blue Folder Base
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.64, 0.05, 0.8],
          pos: cvOrigin,
          rot: cvRot,
          radius: 0.022,
          topColor: "#4B8FD6",
          sideColor: "#2C67A8",
        });
        // 2. Offset Cream Middle Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.58, 0.036, 0.73],
          pos: transformLocalToWorld(vec3(-0.02, 0.036, -0.01), cvOrigin, cvRot),
          rot: [0, -0.28, 0],
          radius: 0.016,
          topColor: "#F5F2EA",
          sideColor: "#DDD6C5",
        });
        // 3. Top White CV Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.57, 0.042, 0.72],
          pos: transformLocalToWorld(vec3(-0.01, 0.07, 0.01), cvOrigin, cvRot),
          rot: [0, -0.38, 0],
          radius: 0.016,
          topColor: "#FFFFFF",
          sideColor: "#E2E8F0",
          rimHighlight: "rgba(255,255,255,0.95)",
        });
        // 4. CV Header, Experience Lines & Fit Badge ON TOP of White CV Sheet
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.38, 0.02, 0.08],
          pos: transformLocalToWorld(vec3(-0.04, 0.095, -0.2), cvOrigin, cvRot),
          rot: [0, -0.38, 0],
          radius: 0.008,
          topColor: "#387BC1",
          sideColor: "#2C67A8",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.36, 0.016, 0.048],
          pos: transformLocalToWorld(
            vec3(-0.05, 0.094, -0.07),
            cvOrigin,
            cvRot,
          ),
          rot: [0, -0.38, 0],
          radius: 0.006,
          topColor: "#94A3B8",
          sideColor: "#64748B",
        });
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.3, 0.016, 0.048],
          pos: transformLocalToWorld(vec3(-0.08, 0.094, 0.02), cvOrigin, cvRot),
          rot: [0, -0.38, 0],
          radius: 0.006,
          topColor: "#94A3B8",
          sideColor: "#64748B",
        });
        const cvSealColor = curEx === "withdrawn" ? "#B54747" : "#287A55";
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.28, 0.024, 0.092],
          pos: transformLocalToWorld(vec3(0.06, 0.096, 0.19), cvOrigin, cvRot),
          rot: [0, -0.38, 0],
          radius: 0.01,
          topColor: cvSealColor,
          sideColor: cvSealColor,
        });
      },
    });

    // Group 7: 3D Tent/Prism Desk Calendar (Midground-Front)
    const calOrigin = vec3(-0.08, 0.25, 0.46);
    const calRot: [number, number, number] = [0, -0.18, 0];
    groups.push({
      depth: projectPoint(calOrigin, cam).z,
      draw: () => {
        // 1. Base Tray
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.62, 0.048, 0.36],
          pos: transformLocalToWorld(
            vec3(0, -0.045, 0),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: calRot,
          radius: 0.018,
          topColor: "#2B4F80",
          sideColor: "#183153",
          scale: calScale,
        });
        // 2. Rear Tent Support Flap
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.54, 0.3, 0.036],
          pos: transformLocalToWorld(
            vec3(0, 0.07, -0.06),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [0.44, -0.18, 0],
          radius: 0.014,
          frontColor: "#EAE4D6",
          edgeColor: "#D2CBB8",
          scale: calScale,
        });
        // 3. Tilted Front White Calendar Board
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.56, 0.32, 0.044],
          pos: transformLocalToWorld(
            vec3(0, 0.08, 0.048),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [-0.44, -0.18, 0],
          radius: 0.018,
          frontColor: "#FFFFFF",
          edgeColor: "#DCE4EE",
          rimHighlight: "rgba(255,255,255,0.95)",
          scale: calScale,
        });
        // 4. Calendar Time-Slot Tiles ON TOP of Front Calendar Board
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.14, 0.065, 0.022],
          pos: transformLocalToWorld(
            vec3(-0.14, 0.11, 0.072),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [-0.44, -0.18, 0],
          radius: 0.008,
          frontColor: "#DCE4EE",
          edgeColor: "#CBD5E1",
          scale: calScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.14, 0.065, 0.022],
          pos: transformLocalToWorld(
            vec3(0.02, 0.11, 0.072),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [-0.44, -0.18, 0],
          radius: 0.008,
          frontColor: "#DCE4EE",
          edgeColor: "#CBD5E1",
          scale: calScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.14, 0.065, 0.022],
          pos: transformLocalToWorld(
            vec3(-0.1, 0.035, 0.104),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [-0.44, -0.18, 0],
          radius: 0.008,
          frontColor: "#DCE4EE",
          edgeColor: "#CBD5E1",
          scale: calScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.16, 0.075, 0.028],
          pos: transformLocalToWorld(
            vec3(0.13, 0.035, 0.108),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: [-0.44, -0.18, 0],
          radius: 0.01,
          frontColor: "#0A968E",
          edgeColor: "#087F78",
          scale: calScale,
        });
        // 5. Top Calendar Spine Bar
        drawRoundedBox3D(ctx, cam, dpr, {
          size: [0.54, 0.042, 0.052],
          pos: transformLocalToWorld(
            vec3(0, 0.22, -0.005),
            calOrigin,
            calRot,
            calScale,
          ),
          rot: calRot,
          radius: 0.012,
          topColor: "#2B4F80",
          sideColor: "#183153",
          scale: calScale,
        });
      },
    });

    // Group 8: Interactive 3D Question Slab (Stage 3)
    if (qScale > 0.02) {
      const qOrigin = vec3(-0.56, qLiftY, 0.34);
      const qRot: [number, number, number] = [0, 0.18 + qFlipRotY, 0];
      groups.push({
        depth: projectPoint(qOrigin, cam).z - 0.05,
        draw: () => {
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.58, 0.058, 0.44],
            pos: qOrigin,
            rot: qRot,
            radius: 0.02,
            topColor: "#FFFFFF",
            sideColor: "#D8D0F0",
            scale: qScale,
          });
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.46, 0.024, 0.08],
            pos: transformLocalToWorld(
              vec3(0, 0.034, -0.08),
              qOrigin,
              qRot,
              qScale,
            ),
            rot: qRot,
            radius: 0.008,
            topColor: curFlip ? "#287A55" : "#7963BE",
            sideColor: curFlip ? "#287A55" : "#7963BE",
            scale: qScale,
          });
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.4, 0.02, 0.055],
            pos: transformLocalToWorld(
              vec3(-0.03, 0.034, 0.05),
              qOrigin,
              qRot,
              qScale,
            ),
            rot: qRot,
            radius: 0.008,
            topColor: "#183153",
            sideColor: "#183153",
            scale: qScale,
          });
        },
      });
    }

    // Group 9: Evaluation Report Clipboard (Stages 6 & 7)
    if (reportScale > 0.02) {
      const repOrigin = vec3(-0.04, 0.23, 0.14);
      const repRot: [number, number, number] = [0, 0.06, 0];
      groups.push({
        depth: projectPoint(repOrigin, cam).z - 0.04,
        draw: () => {
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.68, 0.048, 0.48],
            pos: repOrigin,
            rot: repRot,
            radius: 0.02,
            topColor: "#FFFFFF",
            sideColor: "#DCE4EE",
            scale: reportScale,
          });
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.24, 0.032, 0.065],
            pos: transformLocalToWorld(
              vec3(0, 0.032, -0.18),
              repOrigin,
              repRot,
              reportScale,
            ),
            rot: repRot,
            radius: 0.008,
            topColor: "#183153",
            sideColor: "#183153",
            scale: reportScale,
          });
          drawRoundedBox3D(ctx, cam, dpr, {
            size: [0.52, 0.024, 0.13],
            pos: transformLocalToWorld(
              vec3(0, 0.03, 0.04),
              repOrigin,
              repRot,
              reportScale,
            ),
            rot: repRot,
            radius: 0.008,
            topColor: curStage === 6 || curEv ? "#087F78" : "#287A55",
            sideColor: curStage === 6 || curEv ? "#087F78" : "#287A55",
            scale: reportScale,
          });
        },
      });
    }

    // Group 10: System Question Bubble Slab (Floating in open space to right of monitor)
    const sysOrigin = vec3(-0.12, sysY, -0.22);
    const sysRot: [number, number, number] = [0, 0.26, 0];
    groups.push({
      depth: projectPoint(sysOrigin, cam).z - 0.08,
      draw: () => {
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.68, 0.28, 0.048],
          pos: transformLocalToWorld(
            vec3(0, 0, -0.02),
            sysOrigin,
            sysRot,
            sysScale,
          ),
          rot: sysRot,
          radius: 0.026,
          frontColor: "#0A968E",
          edgeColor: "#087F78",
          scale: sysScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.66, 0.26, 0.046],
          pos: sysOrigin,
          rot: sysRot,
          radius: 0.024,
          frontColor: "#FFFFFF",
          edgeColor: "#DCE4EE",
          rimHighlight: "rgba(255,255,255,0.95)",
          scale: sysScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.52, 0.046, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.02, 0.052, 0.026),
            sysOrigin,
            sysRot,
            sysScale,
          ),
          rot: sysRot,
          radius: 0.01,
          frontColor: "#087F78",
          edgeColor: "#087F78",
          scale: sysScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.44, 0.032, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.06, -0.018, 0.026),
            sysOrigin,
            sysRot,
            sysScale,
          ),
          rot: sysRot,
          radius: 0.008,
          frontColor: "#183153",
          edgeColor: "#183153",
          scale: sysScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.32, 0.028, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.12, -0.072, 0.026),
            sysOrigin,
            sysRot,
            sysScale,
          ),
          rot: sysRot,
          radius: 0.008,
          frontColor: "#7963BE",
          edgeColor: "#7963BE",
          scale: sysScale,
        });
      },
    });

    // Group 11: Candidate Answer Bubble Slab (Floating in open space in front of candidate)
    const candBubbleOrigin = vec3(0.5, candY, -0.1);
    const candBubbleRot: [number, number, number] = [0, -0.28, 0];
    groups.push({
      depth: projectPoint(candBubbleOrigin, cam).z - 0.08,
      draw: () => {
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.68, 0.28, 0.048],
          pos: transformLocalToWorld(
            vec3(0, 0, -0.02),
            candBubbleOrigin,
            candBubbleRot,
            candScale,
          ),
          rot: candBubbleRot,
          radius: 0.026,
          frontColor: "#4B8FD6",
          edgeColor: "#387BC1",
          scale: candScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.66, 0.26, 0.046],
          pos: candBubbleOrigin,
          rot: candBubbleRot,
          radius: 0.024,
          frontColor: "#FFFFFF",
          edgeColor: "#DCE4EE",
          rimHighlight: "rgba(255,255,255,0.95)",
          scale: candScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.52, 0.046, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.02, 0.052, 0.026),
            candBubbleOrigin,
            candBubbleRot,
            candScale,
          ),
          rot: candBubbleRot,
          radius: 0.01,
          frontColor: "#387BC1",
          edgeColor: "#387BC1",
          scale: candScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.46, 0.032, 0.018],
          pos: transformLocalToWorld(
            vec3(-0.05, -0.018, 0.026),
            candBubbleOrigin,
            candBubbleRot,
            candScale,
          ),
          rot: candBubbleRot,
          radius: 0.008,
          frontColor: "#183153",
          edgeColor: "#183153",
          scale: candScale,
        });
        drawPanelZ3D(ctx, cam, dpr, {
          size: [0.28, 0.028, 0.018],
          pos: transformLocalToWorld(
            vec3(0.04, -0.072, 0.026),
            candBubbleOrigin,
            candBubbleRot,
            candScale,
          ),
          rot: candBubbleRot,
          radius: 0.008,
          frontColor: "#287A55",
          edgeColor: "#287A55",
          scale: candScale,
        });
      },
    });

    // Sort all composite 3D groups from farthest to nearest and draw each cleanly
    groups.sort((a, b) => b.depth - a.depth);
    for (const g of groups) {
      g.draw();
    }

    // ======================================================================
    // PASS 6: KNOWLEDGE GRAPH ARCHING NODES (Stages 2 & 3)
    // ======================================================================
    if (kgScale > 0.02) {
      const kgNodes = [
        vec3(-1.26, 0.84, 0.05),
        vec3(-0.92, 1.08, 0.12),
        vec3(-0.58, 0.86, 0.18),
      ];
      const kgProj = kgNodes.map((n) => projectPoint(n, cam));
      ctx.save();
      ctx.strokeStyle = "rgba(121, 99, 190, 0.78)";
      ctx.lineWidth = 2.4 * dpr * kgScale;
      ctx.beginPath();
      ctx.moveTo(kgProj[0].x, kgProj[0].y);
      ctx.lineTo(kgProj[1].x, kgProj[1].y);
      ctx.lineTo(kgProj[2].x, kgProj[2].y);
      ctx.lineTo(kgProj[0].x, kgProj[0].y);
      ctx.stroke();
      ctx.restore();

      for (const node of kgNodes) {
        drawSphere3D(ctx, cam, node, 0.078 * kgScale, "#7963BE", "#DDD6FE");
      }
    }

    ctx.restore();
    animId = requestAnimationFrame(renderFrame);
  };

  animId = requestAnimationFrame(renderFrame);
  return () => cancelAnimationFrame(animId);
}
