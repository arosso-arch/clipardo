import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Título de INTRODUCCIÓN + fijo (estilo virales de TikTok): los primeros ~2 s aparece GRANDE en el centro
// contando qué pasa ("LA PRIMERA MUERTE DE RUBIUS EN GTA 6"), después sube y queda chico donde corresponde
// (arriba, o en el juego en gaming) todo el clip. Se oculta mientras está la tarjeta "Seguir".
export const Titulo: React.FC<{ texto: string; oculta: [number, number] | null; y: number }> = ({ texto, oculta, y }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  if (!texto) return null;
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 170 } });
  // 0 = intro grande al centro, 1 = posición final
  const p = interpolate(t, [1.9, 2.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  let alpha = 1;
  if (oculta) {
    alpha = interpolate(t, [oculta[0] - 0.2, oculta[0], oculta[1], oculta[1] + 0.2], [1, 0, 0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  }
  const largo = texto.length;
  const tamFinal = largo > 26 ? 62 : largo > 18 ? 70 : 78; // más grande, como los clips de @gonchotwm
  const tamIntro = largo > 26 ? 84 : largo > 18 ? 96 : 108;
  const tam = tamIntro + (tamFinal - tamIntro) * p;
  const yIntro = y; // la intro crece en su lugar final: en el centro chocaba con los subtítulos (corrección del usuario 2026-11-19)
  const top = yIntro + (y - yIntro) * p;
  const caja = 0.88 + 0.08 * p; // caja blanca casi opaca (estilo de las cuentas de clips de los streamers, 2026-11-19)
  return (
    <div style={{ position: "absolute", left: 50, right: 50, top, display: "flex", justifyContent: "center",
      opacity: alpha, transform: `scale(${(0.8 + 0.2 * entra) * (1 + 0.04 * (1 - p) * Math.sin(f / 3))})` }}>
      <div style={{ background: `rgba(255,255,255,${caja})`, color: "#0d0d0d", fontFamily: "PoppinsXB", fontSize: tam, lineHeight: 1.1,
        textAlign: "center", padding: `${14 + 10 * (1 - p)}px ${26 + 10 * (1 - p)}px`, borderRadius: 20, maxWidth: 780,
        letterSpacing: 0.5, textWrap: "balance", boxShadow: "0 6px 22px rgba(0,0,0,0.45)", textTransform: "uppercase" }}>
        {texto}
      </div>
    </div>
  );
};
