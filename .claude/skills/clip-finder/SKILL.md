---
name: clip-finder
description: Encuentra y corta los momentos más graciosos o virales de un stream (VOD de Twitch, Kick, YouTube o archivo local) para la cuenta de clips de Instagram. Usar cuando el usuario pasa un link de un stream, dice "procesá el inbox", "buscá clips", "sacá los mejores momentos" o similar.
---

# clip-finder

Pipeline en dos mitades:
- **Pesada y sin tokens** (`prepare`, en la PC del usuario): descarga solo audio + chat, transcribe el VOD entero por partes de 10 min (≈ 8x tiempo real en la GTX 1650: 10 h → ~75 min) y arma 30 candidatos: la mitad por audio/chat y la mitad por texto (risas transcriptas, frases gatillo), con un tope de 4 por hora. Si `transcripcion.completa` es false, transcribe solo los candidatos (más rápido, pero en Kick sin chat encuentra mucho menos humor).
- **Criterio (vos, Claude)**: leés `review.md`, puntuás y escribís `selections.json`; después `cut` corta solo esos tramos del video y los agrega al calendario.

Rutas:
- Python: `<CLIPARDO_HOME>\.venv\Scripts\python.exe` (siempre con `-I`)
- Script: `<CLIPARDO_HOME>\.claude\skills\clip-finder\clipfinder.py`
- Datos: `<CLIPARDO_HOME>\` (`inbox\`, `jobs\<job>\`, `clips\raw\<job>\`, `calendario\calendario.csv`)
- Configuración: `config.json` en esta carpeta (umbrales, cantidad, duraciones, palabras gatillo, pesos)

## Paso 1: preparar (largo: correrlo en segundo plano)

```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\clip-finder\clipfinder.py prepare "<URL o ruta>"
# o todo lo pendiente del inbox (links.txt + videos sueltos):
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\clip-finder\clipfinder.py prepare --inbox
```
Usar `run_in_background: true`. Es reanudable: si se corta, volver a correrlo retoma donde quedó. La última línea imprime `JOB=<ruta>`.

## Paso 2: puntuar (lo hacés vos)

Leé **solo** `jobs\<job>\review.md` (no leas `transcripts.json` ni el audio: gastan tokens). Cada candidato trae su ventana, las señales (audio/chat/emotes en σ = cuánto se despega del resto del stream) y la transcripción con segundos absolutos.

Puntuá de 0 a 100 cada candidato que valga la pena con estos criterios (los pesos están en `config.json → puntaje_pesos`; si cambian, reescalá):

| Criterio | Máx | 0 | Máximo |
|---|---|---|---|
| hook | 25 | arranca lento, "bueno chat…" | en el primer 1,5 s pasa algo que te frena el scroll |
| contexto | 25 | necesita conocer el stream | se entiende 100% sin contexto |
| emocion | 20 | tono plano | risa, grito o sorpresa genuina |
| rewatch | 15 | se ve una vez | final que invita a verlo de nuevo o hace loop |
| share | 15 | nadie lo manda | "mandáselo a tu amigo": frase citable, situación identificable |

Reglas:
- **Mínimo 5 clips por stream y SIN MÁXIMO** (pedido del usuario, 2026-11-18): si hay 30 momentos con potencial (puntaje ≥55), se cortan los 30. Para el usuario la abundancia es contenido y ayuda a la viralidad; después se ordena en el calendario. `cut` ya no recorta (top_n 100). Si los 30 candidatos no alcanzan, buscá en `full_transcript.json` con un script que puntúe ventanas por palabras clave (Juli/vida personal, anécdotas, reacciones a videos/TikTok, risas, "no puede ser") y leé solo las ventanas que salgan arriba. **El gaming también suma**: caos, risa, roleplay absurdo, fails identificables (puntaje mínimo 55). Armá series con el mismo personaje o situación.
- Elegí `start` justo antes de la frase que funciona como hook (podés empezar en el medio de la ventana) y `end` apenas termina la reacción o el remate. Duración ideal de 8 a 30 s; máximo 60. **GTA/gaming: 25-35 s** (las cuentas que más pegan, @elcokismo y Kick Argentina, suben 30 s exactos, 2026-11-21), arrancando en plena acción. Los clips de acción se detectan solos en la edición (sin subtítulos + pulsos de zoom); no hace falta marcar `subtitulos: false` salvo que quieras forzarlo. `cut` ajusta solo a los bordes de palabra.
- **Descartá** (no los incluyas): candidatos con `⚠️ casino` que promocionen un sitio, código o bono; insultos discriminatorios; momentos que solo se entienden con contexto; música de fondo protagonista (se mutea en IG).
- Las señales son pistas, no la verdad: un pico de chat sin nada gracioso en la transcripción vale poco; una frase buenísima con chat tranquilo puede valer mucho.
- `tipo`: frase | risa | absurdo | bardeo | no-puede-ser.
- Antes de escribir `hook_text` y `caption`, cargá la skill `clipardo-marca` (voz, registro amigo/picante/neutral, plantillas).
- `hook_text`: texto en pantalla de 2 s, ≤ 8 palabras, minúsculas, que genere intriga sin spoilear el remate.
- `titulo_pantalla`: título fijo arriba del Reel, estilo virales de TikTok: MAYÚSCULAS, 3-6 palabras, "NOMBRE + qué pasó" (ej. `COKER LA OBLIGA A PEDIR PERDÓN`), sin spoilear el remate.
- Clips de **GTA VI** (o el juego del momento): agregá `"receta": "gta"`; si es de acción (lo que importa es lo que se ve), `"subtitulos": false`. El `titulo_pantalla` cuenta qué pasa ("LA PRIMERA MUERTE DE RUBIUS EN GTA 6"). Streams de España/LatAm → cuenta @clipardo.todo, caption en español neutro.
- `caption`: `TÍTULO EN MAYÚSCULAS` + 1 línea de contexto + CTA (pregunta o "mandáselo a…") + `🎥 @<instagram del streamer, de clipardo-marca/instagram.json> en vivo en <plataforma>` + 7 a 10 hashtags (siempre `#clipardo`). El crédito se queda (campañas pagas de clipping, reposts del streamer); plantilla en `clipardo-marca`.

Escribí `jobs\<job>\selections.json`:
```json
{"clips": [
  {"id": "C07", "start": 5025.2, "end": 5049.8, "score": 82,
   "breakdown": {"hook": 22, "contexto": 20, "emocion": 17, "rewatch": 12, "share": 11},
   "tipo": "frase", "titulo": "coscu y el millon", "hook_text": "le preguntaron qué haría con un palo verde",
   "caption": "…", "transcript": "texto del tramo elegido", "motivo": "por qué funciona, en 1 línea"}
]}
```

## Paso 3: cortar

```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\clip-finder\clipfinder.py cut <nombre-del-job> [--top 8] [--min-score 60]
```
Descarga **solo** esos tramos del video (máximo 1080p) y genera en `<CLIPARDO_HOME>\clips\raw\<job>\`: `NN_titulo.mp4`, `.json` (con palabras y tiempos para subtítulos), `.srt` (para Premiere), `results.md` / `results.json`. Además agrega los clips a `calendario\calendario.csv` con estado "a editar".

**Otra tanda del mismo stream** (sin pisar los clips ya editados): escribí `selections_2.json` y cortá con `cut <job> --sel selections_2.json --desde <siguiente número>`.

## Paso 4: reportar al usuario

Mostrá la tabla de `results.md` (inicio, fin, puntaje, desglose, tipo, hook) + el caption sugerido de cada clip, y qué candidatos descartaste y por qué (en una línea cada uno).

## Otros
- `clipfinder.py status`: estado de cada trabajo.
- Chat: Twitch (TwitchDownloaderCLI) y YouTube (yt-dlp) sí; Kick todavía no (solo audio + transcripción).
- Si un streamer pide la baja: borrar sus clips de `clips\` y sus filas del calendario.

## Clips de la comunidad (instantáneos, sin esperar el VOD) — desde 2026-11-19

`comunidad.py` trae los clips que hacen los espectadores en Kick (API pública) y Twitch (yt-dlp), con vistas, mientras el stream sigue. Corre en bucle cada 30 min (`comunidad.py --horas 3 --preparar --top 6`): prepara los 6 mejores nuevos y avisa en `tmp\comunidad-estado.txt`; la lista completa queda en `<CLIPARDO_HOME>\comunidad\candidatos.md`.
- Son cortos (10-90 s) y ya vienen "votados": revisá el review.md del job, elegí el tramo (casi siempre el clip entero, recortando el arranque lento) y seguí con `cut` → edición como cualquier job.
- Kick: desde 40 vistas (con 15-25 salían clips mudos o sin remate). Twitch: desde 300. Si el clip no tiene charla (review.md casi vacío), descartarlo: sin voz no hay gancho.
- No usar: sorteos/casino/códigos, spoilers de historia y easter eggs de GTA 6 (Trevor, Bigfoot, etc.), insultos.
- Se suman a la cola de edición y al calendario como los demás: así hay Reels del stream de hoy el mismo día.
- Links de VOD de Kick (2026-11-20): usar el ID que aparece en la página `kick.com/<canal>/videos` (empieza con `01a1…`). El `video.uuid` de la API v2 da NOT_FOUND en yt-dlp y corta todo el `prepare --inbox`.
- Momo (Gero, @gero.momo) es `kick.com/momoladinastia`; `kick.com/momo` es otra streamer.
