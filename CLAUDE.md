# Clipardo (cuentas de clips de streamers)

Instrucciones para Claude Code. Abrí Claude Code **en esta carpeta** (la raíz del repo = `CLIPARDO_HOME`): así toma este archivo y las skills de `.claude/skills/`.
Las rutas que aparecen como `<CLIPARDO_HOME>` son esta carpeta. Las cuentas de Instagram están en `clipardo.config.json`.

## Regla de oro: gastar pocos tokens
- Cada sesión es para **una sola tarea**. Cuando termina, se abre otra nueva.
- Antes de tocar código del editor, leé `.claude/skills/ig-editor/MAPA.md` y abrí solo la función que hace falta (`igeditor.py` es largo: nunca entero).
- Para elegir clips: `jobs/<job>/review.md` o `.claude/skills/clip-finder/buscar_momentos.py <job>`. Nunca leer `full_transcript.json` entero.
- Imágenes: pocas y chicas (una hoja por clip).
- Lo pesado corre en la PC sin tokens: `clipardo.bat` (preparar → cortar → editar), `vigilar.bat` (avisa cuando termina un stream) y `arrancar-clipardo.bat` (todo junto).

## Menú de tareas (cada una = una sesión nueva)
| Sección | Qué pedir | Qué hacer |
|---|---|---|
| **Clipear** | "clipeá los streams nuevos" / "clipeá este VOD: <link>" | clip-finder: `prepare` (en segundo plano) → elegir con `review.md` + `buscar_momentos.py` (mínimo 5 por stream y sin máximo: todo lo que tenga potencial, `titulo_pantalla`, `receta: gta` si es GTA) → `cut` → `igeditor.py render --capcut` → `remotion_final.py` |
| **Correcciones** | "correcciones: clip 03 seg 12 …" | Aplicar en `config.json` o en la función que diga `MAPA.md`, anotar en `aprendizajes.md`, re-renderizar solo esos clips |
| **Calendario y publicación** | "armá el calendario de esta semana" / "valorá los clips" | Los clips listos están en `clips\final\<job>\` y en `calendario\publicacion.csv`. Captions con la skill `clipardo-marca`. El publicador sube solo lo "programado" |
| **Aprender** | "analizá estos reels: …" / "qué está funcionando" | `ig-editor/aprender.py` (sin bajar todo), resumen en `referencias\aprender\lo-que-funciona.md` |
| **Marca** | logos, bios, portadas, estética | Remotion en `remotion-clipardo` (logos en `src/Logos*.tsx`), archivos en `marca\` |
| **Mejoras** | efectos nuevos, recetas nuevas, arreglos del editor | `MAPA.md` primero; anotar en `aprendizajes.md` y `tipos-de-clip.md` |

## Cuentas (ver `clipardo.config.json`)
- Cuenta **arg**: streamers locales (lista `streamers_cuenta_local`), voz rioplatense.
- Cuenta **todo**: general (resto de streamers), español neutro.
- Marca de agua: `marca_agua.texto` en `.claude/skills/ig-editor/config.json`.

## Reglas fijas
Todo lo pesado dentro de `CLIPARDO_HOME` (en un disco con lugar). Nunca instalar sin preguntar. Cada corrección del usuario va a `ig-editor/aprendizajes.md` en el momento. Nada de casino ni códigos en los clips. CapCut solo a pedido. Lo descartado va a la Papelera. Nunca leer ni mostrar `publicador/tokens.env`.
