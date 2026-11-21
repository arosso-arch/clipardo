---
name: ig-editor
description: Edita los clips en bruto de clip-finder y los convierte en Reels de Instagram listos para publicar (9:16, subtítulos quemados, hook, zoom, audio -14 LUFS, portada y caption). Usar cuando el usuario dice "editá los clips", "pasalos a reels", "renderizá", o después de cortar clips con clip-finder.
---

# ig-editor

Rutas:
- Python: `<CLIPARDO_HOME>\.venv\Scripts\python.exe` (siempre con `-I`)
- Script: `<CLIPARDO_HOME>\.claude\skills\ig-editor\igeditor.py` · configuración: `config.json` en esta carpeta
- Entrada: `<CLIPARDO_HOME>\clips\raw\<job>\NN_titulo.mp4` + `.json` (los genera clip-finder)
- Salida: `<CLIPARDO_HOME>\clips\final\<job>\NN_titulo.mp4 / .jpg / .txt / .json` + `clips\final\registro.csv`

**Para cambiar algo del editor, leé primero `MAPA.md`** (qué función/parámetro toca cada cosa) y abrí solo esa parte del código: no leas `igeditor.py` entero.

Antes de renderizar, **leé `tipos-de-clip.md`** (cada tipo de clip tiene su receta; el script detecta el tipo y lo muestra en la tabla; si sale `desconocido` o un tipo sin receta, preguntale al usuario cómo editarlo y anotalo ahí), **`aprendizajes.md`** (correcciones previas del usuario; cada corrección nueva se anota ahí en el momento) y **`referencias-estilo.md`** (el estilo de los Reels de referencia que hay que recrear) y cargá la skill `clipardo-marca` y revisá hook y caption contra su checklist. El hook y la portada salen en el verde de marca (`color` en `hook` y `portada` de `config.json`).

## Paso 0: analizar el clip y compararlo con su referencia

Antes de renderizar: hoja de contactos de cada clip en bruto (`ffmpeg -i <raw.mp4> -vf "fps=12/<dur>,scale=320:180,tile=4x3" -frames:v 1 hoja.jpg`), reconocer el tipo y abrir la hoja de la referencia de ese tipo (`tipos-de-clip.md` dice cuál, en `<CLIPARDO_HOME>\referencias\hojas\`). Si llegan referencias nuevas, regenerá las hojas con `analizar_refs.py <carpeta_salida>`.

## Paso 1: revisar los subtítulos (obligatorio, cuesta pocos tokens)

Whisper se equivoca con el slang y los nombres, y esos errores quedan quemados en el video. Listá las palabras de cada clip:
```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I -c "import json,glob;[print(p.split('\\')[-1],'->',' '.join(w[2] for w in json.load(open(p,encoding='utf-8'))['words'])) for p in sorted(glob.glob(r'<CLIPARDO_HOME>\clips\raw\<job>\0*.json'))]"
```
Si hay palabras mal transcriptas, agregá en el `.json` de ese clip:
`"correcciones": {"palabra_mal_en_minusculas": "palabra bien"}`.
Si el clip va a durar más de 40 s (el script lo avisa), leé la transcripción por frases y agregá `"recortes": [[ini, fin], ...]` (segundos del clip en bruto) con las partes lentas: setups largos, explicaciones que no suman al chiste.
Opcional: `"remate_t": <segundos desde el inicio del clip>` fuerza el momento del zoom (si no, se elige el pico de volumen del último 45%).

## Paso 2: renderizar

```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\ig-editor\igeditor.py render <job> [--estilo limpio|bubble|ab] [--layout auto|cara|hablante|mosaico|apilado|blur] [--solo 03]
```
**Agregá siempre `--capcut`**: arma la base que usa Remotion. El borrador de CapCut (skill `capcut-editor`) es solo a pedido. Tarda ~1 min por clip en CPU. `--estilo ab` (por defecto) alterna los dos estilos de subtítulos para comparar en la Fase 4.

## Paso 2b: capa final con Remotion (siempre)

Después del render con `--capcut`, pasá cada Reel por Remotion (pedido del usuario, 2026-11-17):
```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\ig-editor\remotion_final.py <job> [--solo 03]
```
Agrega sobre el video base: subtítulos con rebote que siguen la cara, zoom de golpe con desenfoque en el remate y la marca `@clipardo`. Reemplaza `NN.mp4` (la versión FFmpeg queda como `NN_ffmpeg.mp4`). Proyecto: `<CLIPARDO_HOME>\remotion-clipardo` (composición `ClipEfectos` en `src/Composition.tsx`). Tarda ~1 min por cada 20 s de clip. Remotion es gratis para equipos de hasta 3 personas.

Efectos nuevos (insertos de imagen al nombrar algo, carita del que habla) se suman en esa composición, no en FFmpeg.

## Paso 3: autocorrección (obligatorio, pedido del usuario 2026-11-19)

El usuario quiere que no dependas de sus correcciones: revisá y corregí solo hasta que el Reel esté lo más cerca posible de las referencias.
1. `revisar.py <job> --arreglar` (la cola de edición ya lo corre): mide título vs subtítulos, cara entera en la cámara de gaming y título sobre la cara; arregla solo lo que puede (`titulo_y`, re-render) y deja en la tabla lo que queda.
2. Mirá la hoja de cada clip (abajo). Si algo no te convence (cámara sin la persona, textos que se pisan, juego en negro o pantalla de carga, final cortado, subtítulo mal transcripto), corregí en el `.json` del clip (`correcciones`, `recortes`, `titulo_y`, `subtitulos: false`) o en el código según `MAPA.md`, y re-renderizá con `--solo NN`. Máximo 2 vueltas por clip; si no queda bien, descartalo del calendario y avisá en una línea.
3. Toda corrección que hagas por tu cuenta también va a `aprendizajes.md`.

## Paso 3b: revisar y reportar

Armá una hoja de contacto (8 fotogramas por clip) y miralas antes de dar el OK:
```bash
ffmpeg -i <final.mp4> -vf "fps=8/<duración>,scale=270:480,tile=4x2" -frames:v 1 hoja.jpg
```
Chequeá: que la cara quede dentro del recorte, que los subtítulos no tapen la cara, que el hook se lea y que la portada tenga cara. Reportá la tabla que imprime el script.

## Qué hace (y dónde ajustarlo en `config.json`)

| Paso | Cómo | Parámetros |
|---|---|---|
| Recorte de silencios | Corta huecos entre palabras > 0,8 s **solo si el audio es bajo** (no corta risas) | `silencios` |
| Layout (cámara virtual) | **Mosaico de Discord**: recuadro de quien habla (anillo verde) agrandado sobre fondo desenfocado; pantalla compartida completa. **2 caras en una cámara**: primer plano 9:16 de quien habla (movimiento de boca). **1 cara**: recorte 9:16 que la sigue. Sin cara: fondo blur. Solo se corta de persona con un tramo propio (≥3 palabras o ≥0,8 s) | `layout` (`hablante`, `camara`, `mosaico`) |
| Subtítulos | ASS: 1-2 palabras, minúsculas, centrados a 42% de la altura (50% en apilado, sobre la unión). Estilo "limpio" (Montserrat ExtraBold + sombra) o "bubble" (Luckiest Guy + borde grueso) | `subtitulos` |
| Hook | Caja negra translúcida arriba (y=270, fuera de la UI de IG) los primeros 2,2 s | `hook` |
| Crédito | `@streamer · plataforma` chico y semitransparente | `credito` |
| Punch-in | Zoom 112% durante 1,3 s en el remate | `punch_in` |
| Audio | `loudnorm` en 2 pasadas a -14 LUFS / -1 dBTP | `audio` |
| Portada | Fotograma con la cara más grande + hook en mayúsculas dentro del recorte 4:5 de la grilla | `portada` |
| Exportación | H.264 high 4.1, CRF 19, máx. 12 Mbps, 30 fps, AAC 192k 48 kHz, faststart | `salida` |

Al terminar, el calendario marca esos clips como "listo para subir" y `registro.csv` guarda layout y estilo de cada Reel (para cruzar con métricas en la Fase 4).

## Un clic sin Claude: `<CLIPARDO_HOME>\clipardo.bat`

El usuario lo corre solo (no gasta tokens). Hace: preparar inbox → cortar (si hay `selections.json`) → editar → Remotion → hoja de revisión en `clips\final\<job>\revision\`. Lo único que necesita a Claude es **elegir los clips** (Paso 2 de clip-finder, leyendo solo `review.md`): cuando el usuario diga "elegí los clips de <job>", hacé eso y decile que vuelva a darle doble clic al .bat. Orquestador: `clipardo.py`.
