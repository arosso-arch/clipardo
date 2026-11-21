import React from "react";
import { AbsoluteFill, Composition, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Logo5 } from "./Logos2";

// Logos de las dos cuentas, misma familia que el logo Rec (cartel rojo CLIPARDO con la O de grabación):
// - @clipardo (general): el Rec original, fondo azul.
// - @clipardoarg: mismo cartel sobre la bandera argentina (celeste-blanco-celeste) + Sol de Mayo con "ARG".
const ROJO = "#FF2E3E";
const BL = "#FFFFFF";
const CELESTE = "#6CACE4";
const CELESTE_OSC = "#3E86C8";
const SOL = "#F6B40E";
const S = 1080;

const Sol: React.FC<{ x: number; y: number; r: number; giro: number }> = ({ x, y, r, giro }) => (
  <g transform={`translate(${x} ${y})`}>
    <g transform={`rotate(${giro})`}>
      {Array.from({ length: 16 }).map((_, i) => (
        <path key={i} d={i % 2 ? `M-9 ${-r * 0.95} L0 ${-r * 1.55} L9 ${-r * 0.95} Z` : `M-6 ${-r * 0.95} Q14 ${-r * 1.25} 0 ${-r * 1.6} Q-14 ${-r * 1.25} -6 ${-r * 0.95} Z`}
          fill={SOL} transform={`rotate(${i * 22.5})`} />
      ))}
    </g>
    <circle r={r} fill={SOL} stroke="#C98A00" strokeWidth="5" />
    <text y={r * 0.32} textAnchor="middle" fontFamily="PoppinsXB" fontSize={r * 0.82} fill="#0B2F5E">ARG</text>
  </g>
);

export const LogoArg: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 140 } });
  const sello = spring({ frame: f - 10, fps, config: { damping: 9, stiffness: 170 } });
  const rec = f % 30 < 18 ? 1 : 0.3;
  const brillo = interpolate(f % 90, [20, 50], [-400, 1400], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      <svg width={S} height={S} viewBox="0 0 1080 1080">
        <defs>
          <clipPath id="ca"><circle cx="540" cy="540" r="520" /></clipPath>
          <clipPath id="tagA"><rect x="150" y="430" width="780" height="220" rx="40" /></clipPath>
        </defs>
        <g clipPath="url(#ca)">
          {/* bandera: celeste - blanco - celeste */}
          <rect width="1080" height="1080" fill={CELESTE} />
          <rect y="360" width="1080" height="360" fill={BL} />
          {/* marco de cámara, igual que el Rec */}
          {[[170, 230, 1, 1], [910, 230, -1, 1], [170, 850, 1, -1], [910, 850, -1, -1]].map(([x, y, sx, sy], i) => (
            <path key={i} d={`M${x} ${y + sy * 90} L${x} ${y} L${x + sx * 90} ${y}`} stroke={BL} strokeWidth="18"
              fill="none" strokeLinecap="round" />
          ))}
          <g transform={`translate(540 540) scale(${entra}) rotate(${-6 * entra}) translate(-540 -540)`}>
            <rect x="160" y="444" width="780" height="220" rx="40" fill={CELESTE_OSC} opacity="0.55" />
            <rect x="150" y="430" width="780" height="220" rx="40" fill={ROJO} />
            <text x="505" y="582" textAnchor="middle" fontFamily="PoppinsXB" fontSize="128" fill={BL} letterSpacing="2">CLIPARD</text>
            <circle cx="845" cy="540" r="46" fill={BL} opacity={rec} />
            <circle cx="845" cy="540" r="46" fill="none" stroke={BL} strokeWidth="10" />
            <g clipPath="url(#tagA)">
              <rect x={brillo} y="380" width="70" height="320" fill={BL} opacity="0.35" transform="skewX(-20)" />
            </g>
          </g>
          {/* sello Sol de Mayo con ARG, entra con rebote y gira despacio */}
          <g transform={`translate(855 330) scale(${sello}) translate(-855 -330)`}>
            <Sol x={855} y={330} r={72} giro={f * 1.2} />
          </g>
        </g>
      </svg>
    </AbsoluteFill>
  );
};

export const LogosCuentas = () => (
  <>
    <Composition id="Logo-Clipardo" component={Logo5} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Logo-ClipardoArg" component={LogoArg} durationInFrames={90} fps={30} width={S} height={S} />
  </>
);
