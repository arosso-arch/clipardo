import React from "react";
import { AbsoluteFill, Composition, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Fotos de perfil v3, "semi-realistas": mismo diseño que la v2 (se lee en chiquito) pero con volumen y luz:
// cartel con relieve (brillo, sombra, bisel), fondo con profundidad y luces desenfocadas, REC que brilla,
// Sol de Mayo dorado metálico en la de Argentina. Se renderizan a 2160 px (--scale=2) para que no pierdan calidad.
const S = 1080;
type Tema = { id: string; c1: string; c2: string; c3: string; aro1: string; aro2: string; arg: boolean };
const GENERAL: Tema = { id: "g", c1: "#3D6BFF", c2: "#1435C9", c3: "#050F4A", aro1: "#FFFFFF", aro2: "#9DB4FF", arg: false };
const ARG: Tema = { id: "a", c1: "#B9DDF7", c2: "#5FA6DE", c3: "#1F5C9C", aro1: "#FFE27A", aro2: "#C98A00", arg: true };

const Luces: React.FC<{ f: number; arg: boolean }> = ({ f, arg }) => {
  const puntos = [[200, 260, 40], [880, 820, 55], [820, 210, 30], [240, 860, 48], [540, 140, 26], [130, 560, 22], [960, 520, 24]];
  return (
    <g filter="url(#bokeh)">
      {puntos.map(([x, y, r], i) => (
        <circle key={i} cx={x + Math.sin((f + i * 20) / 40) * 12} cy={y + Math.cos((f + i * 15) / 50) * 10} r={r}
          fill={arg ? "#FFFFFF" : "#A9C4FF"} opacity={0.18 + 0.1 * Math.sin((f + i * 30) / 25)} />
      ))}
    </g>
  );
};

const SolMetal: React.FC<{ r: number; giro: number; id: string }> = ({ r, giro, id }) => (
  <g filter={`url(#sombraSol${id})`}>
    <g transform={`rotate(${giro})`}>
      {Array.from({ length: 16 }).map((_, i) => (
        <path key={i} d={i % 2 ? `M-11 ${-r * 0.9} L0 ${-r * 1.55} L11 ${-r * 0.9} Z` : `M-8 ${-r * 0.9} Q16 ${-r * 1.25} 0 ${-r * 1.62} Q-16 ${-r * 1.25} -8 ${-r * 0.9} Z`}
          fill={`url(#oro${id})`} stroke="#9A6A00" strokeWidth="2" transform={`rotate(${i * 22.5})`} />
      ))}
    </g>
    <circle r={r} fill={`url(#oro${id})`} stroke="#8A5E00" strokeWidth="6" />
    <circle r={r * 0.82} fill="none" stroke="#FFF3B0" strokeWidth="4" opacity="0.7" />
    <ellipse cx={-r * 0.3} cy={-r * 0.4} rx={r * 0.45} ry={r * 0.22} fill="#FFFFFF" opacity="0.35" />
    <text y={r * 0.33} textAnchor="middle" fontFamily="PoppinsXB" fontSize={r * 0.85} fill="#0B2F5E">ARG</text>
  </g>
);

const Perfil: React.FC<{ t: Tema }> = ({ t }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 140 } });
  const rec = f % 30 < 18 ? 1 : 0.35;
  const brillo = interpolate(f % 90, [20, 52], [-400, 1500], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const id = t.id;
  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0b0b" }}>
      <svg width={S} height={S} viewBox="0 0 1080 1080">
        <defs>
          <clipPath id={`c${id}`}><circle cx="540" cy="540" r="500" /></clipPath>
          <radialGradient id={`fondo${id}`} cx="50%" cy="42%" r="62%">
            <stop offset="0%" stopColor={t.c1} />
            <stop offset="55%" stopColor={t.c2} />
            <stop offset="100%" stopColor={t.c3} />
          </radialGradient>
          <radialGradient id={`vin${id}`} cx="50%" cy="50%" r="50%">
            <stop offset="70%" stopColor="#000" stopOpacity="0" />
            <stop offset="100%" stopColor="#000" stopOpacity="0.45" />
          </radialGradient>
          {/* cartel rojo con volumen: brillo arriba, rojo profundo abajo */}
          <linearGradient id={`rojo${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FF6B76" />
            <stop offset="45%" stopColor="#FF2E3E" />
            <stop offset="100%" stopColor="#B3101F" />
          </linearGradient>
          <linearGradient id={`borde${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="100%" stopColor="#D9DDE8" />
          </linearGradient>
          <linearGradient id={`oro${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#FFF0A0" />
            <stop offset="45%" stopColor="#F6B40E" />
            <stop offset="100%" stopColor="#B87A00" />
          </linearGradient>
          <linearGradient id={`aro${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={t.aro1} />
            <stop offset="100%" stopColor={t.aro2} />
          </linearGradient>
          <radialGradient id={`recluz${id}`}>
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="60%" stopColor="#FFE0E3" />
            <stop offset="100%" stopColor="#FFB3BA" />
          </radialGradient>
          <filter id="bokeh" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14" /></filter>
          <filter id={`sombra${id}`} x="-20%" y="-30%" width="140%" height="170%">
            <feDropShadow dx="0" dy="22" stdDeviation="20" floodColor="#000" floodOpacity="0.45" />
          </filter>
          <filter id={`sombraSol${id}`} x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="10" stdDeviation="10" floodColor="#000" floodOpacity="0.4" />
          </filter>
          <filter id={`glow${id}`} x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="16" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id={`texto${id}`} x="-10%" y="-20%" width="120%" height="150%">
            <feDropShadow dx="0" dy="6" stdDeviation="4" floodColor="#6B0010" floodOpacity="0.6" />
          </filter>
          <clipPath id={`tag${id}`}><rect x="100" y="420" width="880" height="240" rx="44" /></clipPath>
        </defs>
        <g clipPath={`url(#c${id})`}>
          <rect width="1080" height="1080" fill={`url(#fondo${id})`} />
          {t.arg ? <rect y="370" width="1080" height="340" fill="#FFFFFF" opacity="0.85" /> : null}
          {/* rayos suaves */}
          <g transform={`rotate(${f * 0.5} 540 540)`} opacity={t.arg ? 0.16 : 0.12}>
            {Array.from({ length: 12 }).map((_, i) => (
              <path key={i} d="M540 540 L495 -60 L585 -60 Z" fill={t.arg ? "#5FA6DE" : "#FFFFFF"} transform={`rotate(${i * 30} 540 540)`} />
            ))}
          </g>
          <Luces f={f} arg={t.arg} />
          <rect width="1080" height="1080" fill={`url(#vin${id})`} />
          {/* cartel con relieve */}
          <g transform={`translate(540 540) scale(${entra}) rotate(${-6 * entra}) translate(-540 -540)`}>
            <g filter={`url(#sombra${id})`}>
              <rect x="80" y="400" width="920" height="280" rx="56" fill={`url(#borde${id})`} />
            </g>
            <rect x="100" y="420" width="880" height="240" rx="44" fill={`url(#rojo${id})`} />
            {/* bisel: luz fina arriba y sombra fina abajo */}
            <rect x="104" y="424" width="872" height="232" rx="41" fill="none" stroke="#FFFFFF" strokeOpacity="0.35" strokeWidth="5" />
            <path d="M120 652 H960" stroke="#5A0010" strokeOpacity="0.35" strokeWidth="6" strokeLinecap="round" />
            {/* brillo de "vidrio" en la mitad de arriba */}
            <g clipPath={`url(#tag${id})`}>
              <ellipse cx="540" cy="440" rx="520" ry="95" fill="#FFFFFF" opacity="0.16" />
              <rect x={brillo} y="350" width="80" height="400" fill="#FFFFFF" opacity="0.28" transform="skewX(-20)" />
            </g>
            <g filter={`url(#texto${id})`}>
              <text x="482" y="590" textAnchor="middle" fontFamily="PoppinsXB" fontSize="150" fill="#FFFFFF" letterSpacing="1">CLIPARD</text>
            </g>
            {/* REC con luz propia */}
            <g filter={`url(#glow${id})`} opacity={rec}>
              <circle cx="882" cy="540" r="54" fill={`url(#recluz${id})`} />
            </g>
            <circle cx="882" cy="540" r="56" fill="none" stroke="#FFFFFF" strokeWidth="12" />
          </g>
          {t.arg ? <g transform="translate(830 250)"><SolMetal r={88} giro={f * 1.1} id={id} /></g> : null}
        </g>
        {/* aro exterior metálico */}
        <circle cx="540" cy="540" r="500" fill="none" stroke={`url(#aro${id})`} strokeWidth="30" />
        <circle cx="540" cy="540" r="487" fill="none" stroke="#000" strokeOpacity="0.25" strokeWidth="4" />
      </svg>
    </AbsoluteFill>
  );
};

export const PerfilGeneralV3: React.FC = () => <Perfil t={GENERAL} />;
export const PerfilArgV3: React.FC = () => <Perfil t={ARG} />;

export const LogosV3 = () => (
  <>
    <Composition id="Perfil-Clipardo-v3" component={PerfilGeneralV3} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Perfil-ClipardoArg-v3" component={PerfilArgV3} durationInFrames={90} fps={30} width={S} height={S} />
  </>
);
