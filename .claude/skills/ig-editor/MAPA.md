# Mapa del editor (leer ESTO antes que el código)

Para no gastar tokens: buscá acá qué función o parámetro toca lo que pide el usuario y abrí solo esa parte (`Grep` por el nombre de la función, después `Read` con offset). **No leas `igeditor.py` entero** (~1500 líneas).

## Flujo de un clip

`clipardo.bat` → `clipardo.py` (orquesta todo) → clip-finder (`prepare` / Claude elige / `cut`) → `igeditor.py render <job> --capcut` → `remotion_final.py <job>` → Reel final en `<CLIPARDO_HOME>\clips\final\<job>\NN.mp4`

Dentro de `igeditor.py` → `render_clip` hace, en orden:
1. `audio_db` + `keep_segments` (silencios) + `edit_cuts` (frases completas, repeticiones, risas largas, `recortes` a mano) → `subtract` → `mapper` (tiempo bruto → final)
2. `detect_faces` (caras + `cuerpo_x` por movimiento) / `detect_mosaic` + `MosaicProbe` (Discord) → `choose_layout` → tipo (`TIPOS`)
3. `voice_speakers` (+ `timbre_ratio`) → quién habla por voz
4. `plan_camera` (cara/hablante: sigue cara, `second_person`, cuerpo) o `plan_mosaic` (Discord: protagonistas, planos estables, `centered`) → `render_camera`
5. Colores por voz (en `render_clip`) → `sub_events` (bloques, seguimiento, posición) → `build_ass` (marca, portada)
6. FFmpeg final + base sin textos para Remotion/CapCut (`--capcut`: `capcut/NN_base.mp4` + `NN_capcut.json`)

## Qué tocar según el pedido

| Pedido del usuario | Dónde |
|---|---|
| Cortes, duración, arranque/final de frase, risas largas | `edit_cuts`; `config.json → recortes`; `.json` del clip → `recortes` |
| Silencios | `keep_segments`; `config → silencios` |
| Cámara de una persona (sigue cara/cuerpo, vibra) | `plan_camera` (rama cara); `config → layout.camara` |
| Otra persona entra a cuadro | `second_person`; `config → layout.segunda_persona` |
| Gaming (webcam arriba + juego abajo; tarjeta redondeada estilo @elcokismo: `layout.gta.tarjeta`) | `plan_gaming`; detección en `choose_layout`; webcam fija del stream: `webcam_del_job` + `caras_rapidas` (en `main`) y ajuste por clip en `render_clip`; `config → layout.gaming` |
| Autocorrección (textos que se pisan, cámara sin cara) | `revisar.py <job> --arreglar`; por clip `titulo_y` en el .json (lo lee `remotion_final.py`) |
| Discord: zoom, pantalla dividida, centrado | `plan_mosaic` (`centered`, `face_in`, caras quietas); `config → layout.mosaico`, `layout.reaccion` |
| Línea/borde raro en Discord | `plan_mosaic → centered` (margen `m_`) |
| Colores de subtítulos por voz | `render_clip` (bloque "color fijo por voz"); `voice_speakers`; `config → subtitulos.paleta_voces`, `subtitulos.voces` |
| Cantidad de palabras por subtítulo | `chunk_words`; `config → subtitulos.max_palabras` |
| Posición/movimiento de subtítulos | `sub_events` (seguimiento); `config → subtitulos.seguimiento` |
| Tipografía/tamaño (FFmpeg/CapCut) | `config → subtitulos.estilos.limpio` |
| Censura | `censor`; `config → subtitulos.censura` |
| Marca de agua @clipardo | `build_ass` (bloque marca, `marca_pos`); `config → marca_agua` |
| Zoom del remate (FFmpeg) | `punch_time`, `zoom_filter`; `config → punch_in` |
| Blanco y negro al final | `render_clip` (bloque `cierre_bn`); `config → cierre_bn` |
| Calidad de imagen | `config → salida` (`crf_base`), `config → remotion` |
| Portada / caption | `build_ass(cover=True)`, `cover_time`; `config → portada` |

## Remotion (capa final de efectos) — `<CLIPARDO_HOME>\remotion-clipardo\src\`

| Archivo | Qué tiene |
|---|---|
| `Composition.tsx` | `ClipEfectos`: video base + `Golpe` (zoom con desenfoque) + `Subtitulo` (rebote, seguimiento, `seguido`, `entra`) + `Marca` |
| `Seguir.tsx` | Tarjeta "Seguir" estilo Instagram (avatar con aro, botón, puntero, "Siguiendo") |
| `Sonidos.tsx` | Efectos de sonido automáticos: whoosh+golpe en el remate, pitido + voz baja en censura, pop+clic en la tarjeta |
| `Logos2.tsx` | Logo Rec (`Logo5`) y bocetos; `Logos.tsx` bocetos viejos |
| `public/sfx/*.wav` | Kit de sonidos (se regenera con `ig-editor/sfx_kit.py`) |

Props que arma `remotion_final.py` desde `NN_capcut.json`: `subtitulos`, `golpe`, `marcaPos`, `seguir` (`config → seguir`), `tamSub`.

## Otros archivos

| Archivo | Para qué |
|---|---|
| `aprendizajes.md` | Cada corrección del usuario (anotar ahí en el momento) |
| `tipos-de-clip.md` | Tipos de clip y su receta; referencias por tipo |
| `referencias-estilo.md` | Análisis de los 19 Reels de referencia |
| `analizar_refs.py` | Regenera hojas de referencia (`<CLIPARDO_HOME>\referencias\hojas\`) |
| `capcut_export.py` (en `C:\workspace\clips-ig\tools\`) | Borrador de CapCut, solo a pedido |
