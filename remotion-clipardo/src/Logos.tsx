import React from "react";
import { AbsoluteFill, Composition, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Bocetos de foto de perfil de Clipardo (animados, en loop de 3 s). Marca: verde #53FC18 sobre negro + blanco.
const V = "#53FC18";
const N = "#000000";
const B = "#FFFFFF";
const S = 1080;

const Circulo: React.FC<{ children: React.ReactNode; aro?: boolean }> = ({ children, aro = true }) => (
  <AbsoluteFill style={{ backgroundColor: "#111" }}>
    <svg width={S} height={S} viewBox="0 0 1080 1080">
      <defs>
        <clipPath id="c">
          <circle cx="540" cy="540" r="520" />
        </clipPath>
      </defs>
      <g clipPath="url(#c)">
        <rect width="1080" height="1080" fill={N} />
        {children}
      </g>
      {aro ? <circle cx="540" cy="540" r="512" fill="none" stroke={V} strokeWidth="16" /> : null}
    </svg>
  </AbsoluteFill>
);

// 1. "Pardo": leopardo streamer con auriculares (mascota fácil de recordar)
export const Logo1: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 10, stiffness: 120 } });
  const parpadeo = f % 90 >= 52 && f % 90 <= 57 ? 0.12 : 1;
  const bob = Math.sin((f / 90) * Math.PI * 2) * 10;
  const rec = f % 30 < 18 ? 1 : 0.25;
  return (
    <Circulo>
      <g transform={`translate(540 ${600 + bob}) scale(${0.6 + 0.4 * entra}) translate(-540 -600)`}>
        {/* orejas */}
        <path d="M300 420 L360 230 L470 360 Z" fill={V} />
        <path d="M780 420 L720 230 L610 360 Z" fill={V} />
        <path d="M335 380 L370 280 L430 355 Z" fill={N} />
        <path d="M745 380 L710 280 L650 355 Z" fill={N} />
        {/* cabeza */}
        <ellipse cx="540" cy="600" rx="290" ry="270" fill={V} />
        {/* manchas de leopardo */}
        {[
          [360, 520, 26], [410, 760, 22], [690, 470, 24], [720, 740, 28], [540, 410, 20], [620, 360, 14], [455, 400, 14],
        ].map(([x, y, r], i) => (
          <g key={i} fill={N} transform={`rotate(${i * 47} ${x} ${y})`}>
            {/* roseta de leopardo: 3 manchas alrededor de un hueco */}
            <ellipse cx={x - r * 0.9} cy={y} rx={r * 0.45} ry={r * 0.7} />
            <ellipse cx={x + r * 0.5} cy={y - r * 0.75} rx={r * 0.6} ry={r * 0.4} />
            <ellipse cx={x + r * 0.55} cy={y + r * 0.75} rx={r * 0.55} ry={r * 0.4} />
          </g>
        ))}
        {/* ojos */}
        <g transform={`translate(0 ${560 * (1 - parpadeo)}) scale(1 ${parpadeo})`}>
          <ellipse cx="445" cy="560" rx="48" ry="58" fill={N} />
          <ellipse cx="635" cy="560" rx="48" ry="58" fill={N} />
          <circle cx="462" cy="540" r="15" fill={B} />
          <circle cx="652" cy="540" r="15" fill={B} />
        </g>
        {/* nariz y boca */}
        <path d="M510 650 L570 650 L540 685 Z" fill={N} />
        <path d="M540 685 Q540 725 495 725 M540 685 Q540 725 585 725" stroke={N} strokeWidth="12" fill="none" strokeLinecap="round" />
        {/* auriculares */}
        <path d="M250 600 Q250 300 540 290 Q830 300 830 600" fill="none" stroke={B} strokeWidth="34" strokeLinecap="round" />
        <rect x="205" y="540" width="90" height="170" rx="40" fill={B} />
        <rect x="785" y="540" width="90" height="170" rx="40" fill={B} />
        <rect x="222" y="560" width="56" height="130" rx="26" fill={N} />
        <rect x="802" y="560" width="56" height="130" rx="26" fill={N} />
      </g>
      {/* REC */}
      <circle cx="540" cy="955" r="22" fill="#FF2D2D" opacity={rec} />
    </Circulo>
  );
};

// 2. "C-Play": monograma, la C de Clipardo que encierra el botón de play
export const Logo2: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const largo = 2 * Math.PI * 300 * 0.78;
  const dibuja = interpolate(f, [0, 22], [largo, 0], { extrapolateRight: "clamp" });
  const play = spring({ frame: f - 18, fps, config: { damping: 8, stiffness: 160 } });
  const glitch = f % 90 >= 70 && f % 90 < 74 ? (f % 2 ? 14 : -14) : 0;
  const giro = interpolate(f % 90, [0, 90], [0, 360]);
  return (
    <Circulo>
      {/* destellos que giran */}
      <g transform={`rotate(${giro} 540 540)`} opacity={0.35}>
        {[0, 120, 240].map((a) => (
          <rect key={a} x="530" y="70" width="20" height="90" rx="10" fill={V} transform={`rotate(${a} 540 540)`} />
        ))}
      </g>
      <g transform={`translate(${glitch} 0)`}>
        {glitch ? (
          <circle cx="540" cy="540" r="300" fill="none" stroke="#FF2D9A" strokeWidth="110" strokeDasharray={`${largo} 9999`}
            transform="rotate(50 540 540) translate(-10 0)" opacity="0.6" />
        ) : null}
        <circle cx="540" cy="540" r="300" fill="none" stroke={V} strokeWidth="110" strokeLinecap="round"
          strokeDasharray={`${largo} 9999`} strokeDashoffset={dibuja} transform="rotate(50 540 540)" />
        <g transform={`translate(560 540) scale(${play}) translate(-560 -540)`}>
          <path d="M470 400 L690 540 L470 680 Z" fill={B} stroke={B} strokeWidth="30" strokeLinejoin="round" />
        </g>
      </g>
    </Circulo>
  );
};

// 3. "Ojos en la oscuridad": dos ojos de leopardo verdes que se abren + claqueta arriba
export const Logo3: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const abre = spring({ frame: f - 6, fps, config: { damping: 12, stiffness: 140 } });
  const parpadeo = f % 90 >= 62 && f % 90 <= 67 ? 0.08 : 1;
  const ojo = abre * parpadeo;
  const pupila = interpolate(Math.sin((f / 90) * Math.PI * 2), [-1, 1], [14, 34]);
  const claqueta = f % 90 < 8 ? interpolate(f % 90, [0, 8], [-24, 0]) : 0;
  const brillo = 0.5 + 0.5 * Math.sin((f / 45) * Math.PI);
  const Ojo = ({ cx }: { cx: number }) => (
    <g transform={`translate(${cx} 600) scale(1 ${ojo}) translate(${-cx} -600)`}>
      <path d={`M${cx - 120} 600 Q${cx} 485 ${cx + 120} 600 Q${cx} 715 ${cx - 120} 600 Z`} fill={V}
        style={{ filter: `drop-shadow(0 0 ${20 + 30 * brillo}px ${V})` }} />
      <ellipse cx={cx} cy="600" rx={pupila} ry="105" fill={N} />
      <circle cx={cx + 40} cy="565" r="14" fill={B} />
    </g>
  );
  return (
    <Circulo>
      {/* claqueta */}
      <g transform={`rotate(${claqueta} 250 330)`}>
        <rect x="250" y="270" width="580" height="80" rx="12" fill={B} />
        {[0, 1, 2, 3, 4].map((i) => (
          <path key={i} d={`M${290 + i * 110} 270 L${350 + i * 110} 270 L${310 + i * 110} 350 L${250 + i * 110} 350 Z`} fill={N} />
        ))}
      </g>
      <rect x="250" y="360" width="580" height="22" rx="8" fill={B} opacity="0.9" />
      <Ojo cx={395} />
      <Ojo cx={685} />
      <text x="540" y="870" textAnchor="middle" fill={B} fontFamily="Arial Black, sans-serif" fontWeight="900" fontSize="96"
        letterSpacing="6">CLIPARDO</text>
    </Circulo>
  );
};

export const Bocetos = () => (
  <>
    <Composition id="Logo1-Pardo" component={Logo1} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Logo2-CPlay" component={Logo2} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Logo3-Ojos" component={Logo3} durationInFrames={90} fps={30} width={S} height={S} />
  </>
);
