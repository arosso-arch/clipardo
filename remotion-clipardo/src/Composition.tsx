import React from "react";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Composition,
  OffthreadVideo,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Seguir } from "./Seguir";
import { Titulo } from "./Titulo";
import { Sonidos, tramosCensura } from "./Sonidos";

// Datos que arma ig-editor (--capcut): video base sin textos + subtítulos con seguimiento + momento del golpe
type Sub = {
  start: number;
  end: number;
  text: string;
  color: string;
  x: number;
  y: number;
  x2?: number;
  y2?: number;
};

export type ClipProps = {
  video: string; // archivo dentro de public/
  duracion: number;
  subtitulos: Sub[];
  golpe: number | null; // segundos: zoom con desenfoque (remate)
  golpesExtra?: number[]; // clips de acción: pulsos de zoom más suaves en los picos (tiros, choques)
  marca: string;
  marcaPos: [number, number, number, number, string][]; // [inicio, fin, x, y, "centro" | "izq"]
  marcaAlpha: number;
  tamSub: number;
  seguir: { inicio: number | null; dur: number; usuario: string; y?: number };
  sfx?: Record<string, number>; // volumen de cada efecto (0 = no va)
  titulo?: string;
  tituloY?: number;
};

const FPS = 30;

const fontReady = (() => {
  if (typeof document === "undefined") return null;
  const h = delayRender("Poppins");
  const f = new FontFace("PoppinsXB", `url(${staticFile("Poppins-ExtraBold.ttf")})`);
  f.load()
    .then((ff) => {
      document.fonts.add(ff);
      continueRender(h);
    })
    .catch(() => continueRender(h));
  return h;
})();

const calculateMetadata: CalculateMetadataFunction<ClipProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.round(props.duracion * FPS)),
});

// Zoom de golpe con desenfoque de movimiento: el video crece de golpe y deja una estela que se desvanece
const Golpe: React.FC<{ video: string; t: number | null; extra?: number[]; mudo: [number, number][] }> = ({ video, t, extra, mudo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // el golpe principal (remate) y los pulsos de acción: se usa el último que empezó; los de acción pegan con 60 % de fuerza
  const todos = [...(t == null ? [] : [{ f: Math.round(t * fps), k: 1 }]), ...(extra ?? []).map((x) => ({ f: Math.round(x * fps), k: 0.6 }))];
  const g = todos.filter((x) => frame >= x.f && frame - x.f < 24).sort((a, b) => b.f - a.f)[0];
  const f0 = g ? g.f : -1000;
  const fuerza = g ? g.k : 1;
  const d = frame - f0;
  const activo = d >= 0 && d < 24;
  const pulso = activo ? spring({ frame: d, fps, config: { damping: 9, stiffness: 180 } }) : 0;
  const decae = activo ? interpolate(d, [0, 24], [1, 0], { extrapolateRight: "clamp" }) : 0;
  const escala = 1 + fuerza * (0.07 * pulso * decae + (activo ? 0.02 : 0));
  const blur = d >= 0 && d < 8 ? interpolate(d, [0, 8], [10, 0]) : 0;
  const estela = [1.06, 1.12, 1.18];
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${escala})`, filter: blur ? `blur(${blur}px)` : undefined }}>
        {/* en las palabras censuradas se baja la voz (suena el pitido encima) */}
        <OffthreadVideo src={staticFile(video)}
          volume={(fr) => (mudo.some(([a, b]) => fr / 30 >= a && fr / 30 < b) ? 0.05 : 1)} />
      </AbsoluteFill>
      {d >= 0 && d < 8
        ? estela.map((k, i) => (
            <AbsoluteFill
              key={k}
              style={{
                transform: `scale(${escala * k})`,
                opacity: interpolate(d, [0, 8], [0.28 - i * 0.07, 0], { extrapolateRight: "clamp" }),
                filter: `blur(${6 + i * 4}px)`,
                mixBlendMode: "screen",
              }}
            >
              <OffthreadVideo src={staticFile(video)} muted />
            </AbsoluteFill>
          ))
        : null}
    </AbsoluteFill>
  );
};

// Subtítulo: pop con resorte + seguimiento de la cara (x,y → x2,y2 durante el bloque)
// seguido = el bloque anterior del mismo que habla terminó recién: cambio suave (sin rebote fuerte), como las referencias
const Subtitulo: React.FC<{ s: Sub; tam: number; seguido: boolean }> = ({ s, tam, seguido }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (t < s.start || t >= s.end) return null;
  const local = Math.round((t - s.start) * fps);
  const pop = spring({ frame: local, fps, config: { damping: 11, stiffness: 260, mass: 0.6 } });
  // que nunca se salga de la pantalla: si el bloque es muy largo, se achica (ancho aprox. de Poppins ExtraBold)
  const entra = Math.min(1, (1080 * 0.88) / Math.max(1, s.text.length * tam * 0.6));
  const escala = interpolate(pop, [0, 1], [seguido ? 0.9 : 0.6, 1]) * entra;
  const giro = seguido ? 0 : interpolate(pop, [0, 1], [-4, 0]);
  const r = interpolate(t, [s.start, s.end], [0, 1]);
  const x = s.x2 != null ? s.x + (s.x2 - s.x) * r : s.x;
  const y = s.y2 != null ? s.y + (s.y2 - s.y) * r : s.y;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${escala}) rotate(${giro}deg)`,
        fontFamily: "PoppinsXB",
        fontSize: tam,
        color: `#${s.color}`,
        whiteSpace: "nowrap",
        WebkitTextStroke: "12px black",
        paintOrder: "stroke fill",
        textShadow: "6px 6px 0 #000",
      }}
    >
      {s.text}
    </div>
  );
};

// Marca de agua @clipardo: blanca semitransparente con brillo suave, donde la ubicó ig-editor
const Marca: React.FC<{ texto: string; pos: ClipProps["marcaPos"]; alpha: number; oculta: [number, number] | null; conTitulo: boolean }> = ({ texto, pos, alpha, oculta, conTitulo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (oculta && t >= oculta[0] && t < oculta[1]) return null; // mientras está la tarjeta "Seguir", no se pisan
  const sp = pos.find(([a, b]) => t >= a && t < b) ?? null;
  if (!sp) return null;
  let [, , x, y, ancla] = sp;
  if (conTitulo && y < 450) {
    // arriba está el título: la marca baja (debajo de los subtítulos, arriba de la interfaz de IG)
    x = 540; y = 1480; ancla = "centro";
  }
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: ancla === "centro" ? "translate(-50%, -50%)" : undefined,
        fontFamily: "PoppinsXB",
        fontSize: 42,
        whiteSpace: "nowrap",
        color: `rgba(255,255,255,${alpha})`,
        textShadow: "0 0 10px rgba(255,255,255,0.3), 0 0 2px rgba(0,0,0,0.4)",
      }}
    >
      {texto}
    </div>
  );
};

export const ClipEfectos: React.FC<ClipProps> = (p) => {
  void fontReady;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Golpe video={p.video} t={p.golpe} extra={p.golpesExtra ?? []} mudo={tramosCensura(p.subtitulos)} />
      <Sonidos golpe={p.golpe} subtitulos={p.subtitulos} seguir={p.seguir} vol={p.sfx ?? {}} />
      <Titulo texto={p.titulo ?? ""} y={p.tituloY ?? 200}
        oculta={p.seguir?.inicio != null ? [p.seguir.inicio, p.seguir.inicio + p.seguir.dur] : null} />
      <Seguir inicio={p.seguir?.inicio ?? null} dur={p.seguir?.dur ?? 2.8} usuario={p.seguir?.usuario ?? "@clipardo"} y={p.seguir?.y ?? 236} />
      {p.subtitulos.map((s, i) => (
        <Subtitulo
          key={i}
          s={s}
          tam={p.tamSub}
          seguido={i > 0 && p.subtitulos[i - 1].color === s.color && s.start - p.subtitulos[i - 1].end < 0.15}
        />
      ))}
      <Marca texto={p.marca} pos={p.marcaPos} alpha={p.marcaAlpha} conTitulo={!!p.titulo && (p.tituloY ?? 200) < 450}
        oculta={p.seguir?.inicio != null ? [p.seguir.inicio, p.seguir.inicio + p.seguir.dur] : null} />
    </AbsoluteFill>
  );
};

export const MyComposition = () => {
  return (
    <Composition
      id="ClipEfectos"
      component={ClipEfectos}
      durationInFrames={60}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={{ video: "base.mp4", duracion: 2, subtitulos: [], golpe: null, marca: "@clipardo", marcaPos: [], marcaAlpha: 0.5, tamSub: 88, seguir: { inicio: 0.3, dur: 2.8, usuario: "@clipardo" } }}
      calculateMetadata={calculateMetadata}
    />
  );
};
