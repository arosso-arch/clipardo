import React from "react";
import { AbsoluteFill, Composition, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Fotos de perfil v2: pensadas para verse en chiquito (40-110 px en IG), como los canales de clips grandes:
// cartel más grande y gordo, borde blanco grueso, sin detalles finos, rayos de luz y aro exterior de color.
const ROJO = "#FF2E3E";
const BL = "#FFFFFF";
const S = 1080;

type Tema = { fondo1: string; fondo2: string; rayos: string; aro: string; arg: boolean };
const GENERAL: Tema = { fondo1: "#2457FF", fondo2: "#0A1F8F", rayos: "#FFFFFF", aro: "#FFFFFF", arg: false };
const ARG: Tema = { fondo1: "#7DBDF0", fondo2: "#3E86C8", rayos: "#FFFFFF", aro: "#F6B40E", arg: true };

const Sol: React.FC<{ r: number; giro: number }> = ({ r, giro }) => (
  <g>
    <g transform={`rotate(${giro})`}>
      {Array.from({ length: 16 }).map((_, i) => (
        <path key={i} d={`M-10 ${-r * 0.92} L0 ${-r * 1.5} L10 ${-r * 0.92} Z`} fill="#F6B40E" transform={`rotate(${i * 22.5})`} />
      ))}
    </g>
    <circle r={r} fill="#F6B40E" stroke="#B87A00" strokeWidth="6" />
    <text y={r * 0.33} textAnchor="middle" fontFamily="PoppinsXB" fontSize={r * 0.85} fill="#0B2F5E">ARG</text>
  </g>
);

const Perfil: React.FC<{ t: Tema }> = ({ t }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 140 } });
  const rec = f % 30 < 18 ? 1 : 0.35;
  const giro = f * 0.6;
  const brillo = interpolate(f % 90, [20, 50], [-400, 1500], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      <svg width={S} height={S} viewBox="0 0 1080 1080">
        <defs>
          <clipPath id="cv2"><circle cx="540" cy="540" r="505" /></clipPath>
          <radialGradient id="gv2" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor={t.fondo1} />
            <stop offset="100%" stopColor={t.fondo2} />
          </radialGradient>
          <clipPath id="tagv2"><rect x="80" y="400" width="920" height="280" rx="56" /></clipPath>
        </defs>
        <g clipPath="url(#cv2)">
          <rect width="1080" height="1080" fill="url(#gv2)" />
          {t.arg ? <rect y="360" width="1080" height="360" fill="#FFFFFF" opacity="0.9" /> : null}
          {/* rayos de luz que giran despacio */}
          <g transform={`rotate(${giro} 540 540)`} opacity={t.arg ? 0.18 : 0.14}>
            {Array.from({ length: 12 }).map((_, i) => (
              <path key={i} d="M540 540 L490 -60 L590 -60 Z" fill={t.arg ? "#3E86C8" : t.rayos} transform={`rotate(${i * 30} 540 540)`} />
            ))}
          </g>
          {/* cartel grande: borde blanco grueso + sombra */}
          <g transform={`translate(540 540) scale(${entra}) rotate(${-6 * entra}) translate(-540 -540)`}>
            <rect x="92" y="420" width="920" height="280" rx="56" fill="#000" opacity="0.28" />
            <rect x="80" y="400" width="920" height="280" rx="56" fill={BL} />
            <rect x="100" y="420" width="880" height="240" rx="44" fill={ROJO} />
            <text x="482" y="590" textAnchor="middle" fontFamily="PoppinsXB" fontSize="150" fill={BL} letterSpacing="1">CLIPARD</text>
            <circle cx="882" cy="540" r="56" fill={BL} opacity={rec} />
            <circle cx="882" cy="540" r="56" fill="none" stroke={BL} strokeWidth="12" />
            <g clipPath="url(#tagv2)">
              <rect x={brillo} y="350" width="80" height="400" fill={BL} opacity="0.3" transform="skewX(-20)" />
            </g>
          </g>
          {t.arg ? <g transform="translate(830 250)"><Sol r={86} giro={f * 1.2} /></g> : null}
        </g>
        {/* aro exterior de color: resalta en el feed */}
        <circle cx="540" cy="540" r="505" fill="none" stroke={t.aro} strokeWidth="26" />
      </svg>
    </AbsoluteFill>
  );
};

export const PerfilGeneral: React.FC = () => <Perfil t={GENERAL} />;
export const PerfilArg: React.FC = () => <Perfil t={ARG} />;

export const LogosV2 = () => (
  <>
    <Composition id="Perfil-Clipardo-v2" component={PerfilGeneral} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Perfil-ClipardoArg-v2" component={PerfilArg} durationInFrames={90} fps={30} width={S} height={S} />
  </>
);
