import React from "react";
import {
  AbsoluteFill,
  Composition,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// Bocetos 4-6: la palabra CLIPARDO animada. Rojo + blanco sobre fondo azul (pedido del usuario).
const ROJO = "#FF2E3E";
const BL = "#FFFFFF";
const AZUL = "#1747FF";
const AZUL_OSC = "#0A1F8F";
const S = 1080;

if (typeof document !== "undefined") {
  for (const [fam, file] of [["Luckiest", "LuckiestGuy-Regular.ttf"], ["PoppinsXB", "Poppins-ExtraBold.ttf"]]) {
    const h = delayRender(fam);
    new FontFace(fam, `url(${staticFile(file)})`).load()
      .then((ff) => { document.fonts.add(ff); continueRender(h); })
      .catch(() => continueRender(h));
  }
}

const Fondo: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ backgroundColor: "#111" }}>
    <svg width={S} height={S} viewBox="0 0 1080 1080">
      <defs>
        <clipPath id="c2"><circle cx="540" cy="540" r="520" /></clipPath>
        <radialGradient id="g" cx="50%" cy="45%" r="60%">
          <stop offset="0%" stopColor={AZUL} />
          <stop offset="100%" stopColor={AZUL_OSC} />
        </radialGradient>
      </defs>
      <g clipPath="url(#c2)">
        <rect width="1080" height="1080" fill="url(#g)" />
        {children}
      </g>
    </svg>
  </AbsoluteFill>
);

const LETRAS = "CLIPARDO".split("");

// 4. "Sticker": letras blancas gordas con borde rojo y sombra 3D, entran una por una y hacen la ola
export const Logo4: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ancho = 118;
  const x0 = 540 - (ancho * LETRAS.length) / 2 + ancho / 2;
  return (
    <Fondo>
      {/* rayos de luz detrás */}
      <g transform={`rotate(${f * 1.2} 540 540)`} opacity="0.18">
        {Array.from({ length: 12 }).map((_, i) => (
          <path key={i} d="M540 540 L500 -40 L580 -40 Z" fill={BL} transform={`rotate(${i * 30} 540 540)`} />
        ))}
      </g>
      {LETRAS.map((l, i) => {
        const e = spring({ frame: f - i * 3, fps, config: { damping: 9, stiffness: 170 } });
        const ola = Math.sin(((f - i * 4) / 90) * Math.PI * 4) * 14 * (f > 30 ? 1 : 0);
        const x = x0 + i * ancho;
        const y = 600 + ola;
        return (
          <g key={i} transform={`translate(${x} ${y}) scale(${e}) rotate(${(i % 2 ? 4 : -4) * e})`}>
            <text textAnchor="middle" fontFamily="Luckiest" fontSize="190" fill={ROJO} x="10" y="14">{l}</text>
            <text textAnchor="middle" fontFamily="Luckiest" fontSize="190" fill={BL} stroke={ROJO} strokeWidth="14"
              paintOrder="stroke fill">{l}</text>
          </g>
        );
      })}
    </Fondo>
  );
};

// 5. "Etiqueta REC": cartel rojo con CLIPARDO en blanco; la O es un punto de grabación que titila
export const Logo5: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 140 } });
  const rec = f % 30 < 18 ? 1 : 0.3;
  const brillo = interpolate((f % 90), [20, 50], [-400, 1400], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Fondo>
      {/* marco de cámara (esquinas) */}
      {[[170, 260, 1, 1], [910, 260, -1, 1], [170, 820, 1, -1], [910, 820, -1, -1]].map(([x, y, sx, sy], i) => (
        <path key={i} d={`M${x} ${y + sy * 90} L${x} ${y} L${x + sx * 90} ${y}`} stroke={BL} strokeWidth="18"
          fill="none" strokeLinecap="round" opacity="0.9" />
      ))}
      <g transform={`translate(540 540) scale(${entra}) rotate(${-6 * entra}) translate(-540 -540)`}>
        <defs>
          <clipPath id="tag"><rect x="150" y="430" width="780" height="220" rx="40" /></clipPath>
        </defs>
        <rect x="160" y="444" width="780" height="220" rx="40" fill={AZUL_OSC} opacity="0.6" />
        <rect x="150" y="430" width="780" height="220" rx="40" fill={ROJO} />
        <text x="505" y="582" textAnchor="middle" fontFamily="PoppinsXB" fontSize="128" fill={BL} letterSpacing="2">CLIPARD</text>
        <circle cx="845" cy="540" r="46" fill={BL} opacity={rec} />
        <circle cx="845" cy="540" r="46" fill="none" stroke={BL} strokeWidth="10" />
        {/* reflejo que cruza */}
        <g clipPath="url(#tag)">
          <rect x={brillo} y="380" width="70" height="320" fill={BL} opacity="0.35" transform="skewX(-20)" />
        </g>
      </g>
    </Fondo>
  );
};

// 6. "Apilado": CLIP grande blanco arriba, ARDO rojo abajo, con corte de glitch y una tira de película
export const Logo6: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame: f, fps, config: { damping: 11, stiffness: 150 } });
  const b = spring({ frame: f - 6, fps, config: { damping: 11, stiffness: 150 } });
  const glitch = f % 90 >= 60 && f % 90 < 66;
  const dx = glitch ? (f % 2 ? 16 : -16) : 0;
  const tira = (f * 6) % 120;
  return (
    <Fondo>
      {/* tira de película que corre */}
      <g opacity="0.25">
        <rect x="0" y="120" width="1080" height="90" fill={AZUL_OSC} />
        <rect x="0" y="870" width="1080" height="90" fill={AZUL_OSC} />
        {Array.from({ length: 11 }).map((_, i) => (
          <g key={i}>
            <rect x={i * 120 - tira} y="145" width="60" height="40" rx="8" fill={BL} />
            <rect x={i * 120 + tira - 120} y="895" width="60" height="40" rx="8" fill={BL} />
          </g>
        ))}
      </g>
      <g transform={`translate(${-700 * (1 - a) + dx} 0)`}>
        {glitch ? <text x="532" y="525" textAnchor="middle" fontFamily="PoppinsXB" fontSize="300" fill="#00E5FF" opacity="0.7">CLIP</text> : null}
        <text x="540" y="525" textAnchor="middle" fontFamily="PoppinsXB" fontSize="300" fill={BL}>CLIP</text>
      </g>
      <g transform={`translate(${700 * (1 - b) - dx} 0)`}>
        <rect x="190" y="560" width="700" height="230" rx="30" fill={ROJO} />
        {glitch ? <text x="548" y="740" textAnchor="middle" fontFamily="PoppinsXB" fontSize="210" fill="#FFE600" opacity="0.6">ARDO</text> : null}
        <text x="540" y="740" textAnchor="middle" fontFamily="PoppinsXB" fontSize="210" fill={BL}>ARDO</text>
      </g>
    </Fondo>
  );
};

export const Bocetos2 = () => (
  <>
    <Composition id="Logo4-Sticker" component={Logo4} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Logo5-Rec" component={Logo5} durationInFrames={90} fps={30} width={S} height={S} />
    <Composition id="Logo6-Apilado" component={Logo6} durationInFrames={90} fps={30} width={S} height={S} />
  </>
);
