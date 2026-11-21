import React from "react";
import { Audio, Sequence, staticFile, useVideoConfig } from "remotion";

// Efectos de sonido automáticos (kit en public/sfx, generado por ig-editor/sfx_kit.py).
// Se ubican en los momentos que ya conoce el editor: zoom de golpe, palabras censuradas y tarjeta "Seguir".
type Sub = { start: number; end: number; text: string };

export const CENSURA = /[@#]|\d/; // censor() de ig-editor reemplaza vocales por @ 3 1 0 #

export const tramosCensura = (subs: Sub[]): [number, number][] =>
  subs.filter((s) => CENSURA.test(s.text)).map((s) => [s.start, Math.min(s.end, s.start + 0.6)]);

const Sfx: React.FC<{ t: number; src: string; vol: number }> = ({ t, src, vol }) => {
  const { fps } = useVideoConfig();
  if (t < 0 || vol <= 0) return null; // volumen 0 = ese efecto no va en este clip
  return (
    <Sequence from={Math.round(t * fps)} layout="none">
      <Audio src={staticFile(`sfx/${src}.wav`)} volume={vol} />
    </Sequence>
  );
};

export const Sonidos: React.FC<{
  golpe: number | null;
  subtitulos: Sub[];
  seguir: { inicio: number | null; dur: number } | undefined;
  vol: Record<string, number>;
}> = ({ golpe, subtitulos, seguir, vol }) => (
  <>
    {golpe != null ? (
      <>
        <Sfx t={golpe - 0.3} src="whoosh" vol={vol.whoosh ?? 0} />
        <Sfx t={golpe} src="golpe" vol={vol.golpe ?? 0} />
      </>
    ) : null}
    {tramosCensura(subtitulos).map(([a], i) => (
      <Sfx key={`c${i}`} t={a} src="pitido" vol={vol.pitido ?? 0.25} />
    ))}
    {seguir?.inicio != null ? (
      <>
        <Sfx t={seguir.inicio} src="pop" vol={vol.pop ?? 0} />
        <Sfx t={seguir.inicio + seguir.dur * 0.5} src="clic" vol={vol.clic ?? 0} />
      </>
    ) : null}
  </>
);
