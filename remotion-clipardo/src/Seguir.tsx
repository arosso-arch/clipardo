import React from "react";
import { AbsoluteFill, Easing, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Logo5 } from "./Logos2";

// Tarjeta "Seguir" lo más parecida a la interfaz real de Instagram (como la referencia de profounder):
// tarjeta blanca compacta, avatar con aro de historia, usuario en negrita, botón azul de IG,
// un puntero que entra, hace clic (con onda) y el botón pasa a "Siguiendo ⌄" en gris.
const AZUL_IG = "#0095F6";
const FUENTE_IG = "'Segoe UI', -apple-system, 'Helvetica Neue', Arial, sans-serif"; // la fuente del sistema, como la app

const Puntero: React.FC<{ apretando: boolean }> = ({ apretando }) => (
  <svg width="64" height="64" viewBox="0 0 24 24" style={{ transform: `scale(${apretando ? 0.86 : 1})`, transformOrigin: "4px 3px",
    filter: "drop-shadow(0 3px 4px rgba(0,0,0,0.35))" }}>
    <path d="M4 2 L4 19 L8.5 15 L11.5 21.5 L14.2 20.3 L11.3 14 L17.5 14 Z" fill="#111" stroke="white" strokeWidth="1.4"
      strokeLinejoin="round" />
  </svg>
);

const Tarjeta: React.FC<{ usuario: string; dur: number; y: number }> = ({ usuario, dur, y: top }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fin = Math.round(dur * fps);
  const entra = spring({ frame: f, fps, config: { damping: 14, stiffness: 170 } });
  const sale = interpolate(f, [fin - 9, fin], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  const clic = Math.round(fin * 0.5);
  const siguiendo = f >= clic;
  const apretando = f >= clic - 2 && f < clic + 2;
  // el puntero viaja desde abajo a la derecha hasta el botón
  const viaje = interpolate(f, [clic - 18, clic - 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const punteroVis = f >= clic - 18 && f < clic + 14;
  const onda = interpolate(f, [clic, clic + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const x = interpolate(entra, [0, 1], [-720, 0]) + interpolate(sale, [0, 1], [0, -720]);
  return (
    <div style={{ position: "absolute", left: 56, top, transform: `translateX(${x}px)`, fontFamily: FUENTE_IG }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22, background: "white", borderRadius: 26, padding: "20px 24px 20px 20px",
        boxShadow: "0 10px 34px rgba(0,0,0,0.28), 0 1px 3px rgba(0,0,0,0.12)", width: 700 }}>
        {/* avatar con aro de historia (degradé de IG) */}
        <div style={{ width: 118, height: 118, borderRadius: "50%", padding: 6, flexShrink: 0,
          background: "conic-gradient(from 200deg, #FEDA75, #FA7E1E, #D62976, #962FBF, #4F5BD5, #FEDA75)" }}>
          <div style={{ width: "100%", height: "100%", borderRadius: "50%", background: "white", padding: 5 }}>
            <div style={{ width: "100%", height: "100%", borderRadius: "50%", overflow: "hidden", position: "relative" }}>
              <div style={{ width: 1080, height: 1080, transform: `scale(${96 / 1080})`, transformOrigin: "0 0", position: "absolute" }}>
                <Logo5 />
              </div>
            </div>
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 38, fontWeight: 700, color: "#000", letterSpacing: -0.3 }}>{usuario.replace("@", "")}</div>
          <div style={{ fontSize: 29, color: "#737373", marginTop: 2 }}>Clips de streamers</div>
        </div>
        <div style={{ position: "relative" }}>
          <div style={{ background: siguiendo ? "#EFEFEF" : AZUL_IG, color: siguiendo ? "#000" : "white", fontSize: 32, fontWeight: 600,
            borderRadius: 16, padding: "16px 30px", minWidth: 150, textAlign: "center", transform: `scale(${apretando ? 0.95 : 1})`,
            whiteSpace: "nowrap" }}>
            {siguiendo ? "Siguiendo ⌄" : "Seguir"}
          </div>
          {/* onda del clic */}
          {f >= clic && f < clic + 10 ? (
            <div style={{ position: "absolute", left: "50%", top: "50%", width: 40 + 140 * onda, height: 40 + 140 * onda,
              transform: "translate(-50%, -50%)", borderRadius: "50%", border: "5px solid rgba(0,149,246,0.6)", opacity: 1 - onda }} />
          ) : null}
          {punteroVis ? (
            <div style={{ position: "absolute", left: 70 + 260 * (1 - viaje), top: 34 + 300 * (1 - viaje) }}>
              <Puntero apretando={apretando} />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

// y = lugar libre que eligió remotion_final.py (sin caras, subtítulos ni título); null = sin tarjeta
export const Seguir: React.FC<{ inicio: number | null; dur: number; usuario: string; y?: number }> = ({ inicio, dur, usuario, y = 236 }) => {
  const { fps } = useVideoConfig();
  if (inicio == null) return null;
  return (
    <Sequence from={Math.round(inicio * fps)} durationInFrames={Math.round(dur * fps)} layout="none">
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <Tarjeta usuario={usuario} dur={dur} y={y} />
      </AbsoluteFill>
    </Sequence>
  );
};
