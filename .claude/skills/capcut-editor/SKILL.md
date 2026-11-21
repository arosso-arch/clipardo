---
name: capcut-editor
description: Arma borradores editables de CapCut con la edición de Clipardo (cámara, cortes, zoom, B/N y audio hechos por ig-editor; subtítulos de colores por persona, crédito y hook como capas de texto editables). Usar SIEMPRE que se editen clips para Clipardo, y cuando el usuario diga "pasalo a CapCut", "borrador de CapCut", "quiero retocarlo en CapCut" o "editá en CapCut".
---

# capcut-editor

Es el paso de CapCut de la edición: **siempre que edites clips para Clipardo, generá también el borrador de CapCut** (salvo que el usuario diga que no). Así el usuario retoca textos, colores o tiempos a mano en CapCut sin rehacer nada.

Rutas:
- Exportador: `C:\workspace\clips-ig\tools\capcut_export.py`, con el Python de VectCutAPI `C:\workspace\clips-ig\tools\vectcut\.venv\Scripts\python.exe` (siempre `-I` y `PYTHONIOENCODING=utf-8`)
- Borradores: `<CLIPARDO_HOME>\capcut_borradores\clipardo_<clip>\`
- **Todo lo pesado va en la carpeta del proyecto** (elegí un disco con lugar). El borrador (también el de Proyectos de CapCut, que está en C) es solo texto, sin copia del video: apunta al video base en `<CLIPARDO_HOME>\clips\final\<job>\capcut\`. Si se mueve o borra ese video, CapCut lo pide "sin conexión"
- Carpeta de CapCut (solo para decírsela al usuario): `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`

## Reglas (del usuario, no se negocian)

- **Los borradores se dejan directo en Proyectos de CapCut** con `--a-capcut` (el usuario lo pidió el 2026-11-17; antes los copiaba él). Queda **una sola versión por clip**: la anterior del mismo clip (mismo nombre o `_vN`) va a la **Papelera de reciclaje** (se puede recuperar), nunca se borra del todo (pedido del 2026-11-17: "lo que no utilizás, eliminalo"). Si el usuario había retocado esa versión en CapCut, avisale antes de re-exportar. Si no aparecen, que cierre y abra CapCut.
- Lo que no se usa más (borradores de prueba, archivos temporales de `<CLIPARDO_HOME>\work` de clips ya terminados) también va a la Papelera al terminar.
- **Sin subidas**: VectCutAPI con `auto_deploy=False` / `is_upload_draft=false`. Nada sale a internet.
- No instalar nada nuevo sin preguntar.
- Las correcciones de edición se anotan en `ig-editor/aprendizajes.md` como siempre; si una corrección es solo de CapCut (tamaño de letra, posición, fuente), aplicala en `capcut_export.py` y anotala igual.

## Paso 1: ig-editor con `--capcut`

Seguí la skill `ig-editor` (aprendizajes, referencias, revisión de subtítulos) y renderizá agregando `--capcut`:
```powershell
& <CLIPARDO_HOME>\.venv\Scripts\python.exe -I <CLIPARDO_HOME>\.claude\skills\ig-editor\igeditor.py render <job> --estilo limpio --capcut [--solo 03]
```
Además del Reel terminado, deja en `<CLIPARDO_HOME>\clips\final\<job>\capcut\`:
- `NN_clip_base.mp4`: la edición completa **sin textos quemados**
- `NN_clip_capcut.json`: cada subtítulo con tiempo, texto, color de quien habla y altura

## Paso 2: armar los borradores

```powershell
$env:PYTHONIOENCODING='utf-8'; & C:\workspace\clips-ig\tools\vectcut\.venv\Scripts\python.exe -I C:\workspace\clips-ig\tools\capcut_export.py <CLIPARDO_HOME>\clips\final\<job> --a-capcut [--solo 03]
```
Cada borrador tiene tres pistas:
| Pista | Qué tiene |
|---|---|
| `video` | el video base a pantalla completa (1080x1920) |
| `subtitulos` | un texto por bloque de 1-3 palabras, Poppins Bold, borde + sombra negra, color por persona (blanco, rosa, azul, naranja), misma altura que en el Reel |
| `marca_agua` | `@clipardo` arriba a la izquierda, todo el clip |
| `credito` | `@streamer · plataforma` semitransparente |
| `hook` | solo si `hook.mostrar` está activo en `ig-editor/config.json` |

## Paso 3: verificar y avisar

Chequeá cada `draft_info.json`: pista de video con el archivo existente, cantidad de subtítulos y colores. Después decile al usuario:
- dónde están los borradores
- con qué nombre quedó cada uno en Proyectos de CapCut (ojo con los `_v2`)
- que el tamaño de letra en CapCut es aproximado (`TAM_POR_PX` en el exportador): si lo ve chico o grande, se ajusta ahí y se anota en aprendizajes

## Límites conocidos

- El Reel final pasa por Remotion (zoom de golpe con desenfoque, rebote): eso **no** está en el borrador de CapCut, que lleva el video base y los subtítulos como texto editable (con animación "Pop Up" de CapCut).

- CapCut no trae Poppins ExtraBold: se usa **Poppins Bold**, la más parecida.
- El pop de los subtítulos pasa a CapCut como animación de entrada "Pop Up" (parecida, no idéntica a la del Reel).
- En CapCut la @ de la marca de agua sale blanca (en el Reel va verde).
- La cámara virtual, los cortes y el zoom vienen ya hechos en el video base: para cambiarlos hay que re-renderizar con ig-editor.
