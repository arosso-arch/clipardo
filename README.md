# Clipardo

Sistema para manejar cuentas de Instagram de **clips de streamers** casi en piloto automático:
vigila streams de Kick / Twitch / YouTube, los transcribe con Whisper, Claude elige los mejores momentos,
los corta, los edita en vertical 9:16 con subtítulos y efectos, se autocorrige, los aprueba y un publicador
los sube a Instagram con la API oficial (1 Reel por hora por cuenta).

> Repo privado. Para instalarlo en tu PC seguí **[INSTALAR.md](INSTALAR.md)**.
> Para poder publicar necesitás tus propios tokens: mirá **[Tokens de las cuentas](#tokens-de-las-cuentas-para-poder-subir-los-videos)**.

---

## Cómo está armado

```
clipardo/                      <- CLIPARDO_HOME (la raíz; abrí Claude Code acá)
├─ CLAUDE.md                   instrucciones para Claude Code (menú de tareas, reglas)
├─ clipardo.config.json        TUS cuentas de Instagram y qué streamers van a cada una
├─ clipardo_rutas.py           todas las rutas en un solo lugar (lo usan todos los .py)
├─ entorno.bat / scripts/entorno.sh   lo mismo para los .bat y los .sh
├─ arrancar-clipardo.bat       abre todo junto (cada proceso en su ventana)
├─ clipardo.bat                un clic: preparar → cortar → editar lo nuevo del inbox
├─ vigilar.bat                 vigilante de streams
├─ reporte.bat                 reporte diario
├─ .claude/skills/             skills de Claude Code
│  ├─ clip-finder/             bajar, transcribir, puntuar y cortar
│  ├─ ig-editor/               edición 9:16, detección de acción, Remotion, autocorrector
│  ├─ clipardo-marca/          voz de la marca, captions, @ de cada streamer
│  └─ capcut-editor/           borradores de CapCut (opcional, ver abajo)
├─ scripts/                    bucles que corren solos (Git Bash)
├─ publicador/                 publicador, calendario, aprobación, limpieza, reporte
├─ remotion-clipardo/          capa final de efectos (título, golpe, tarjeta Seguir, sonidos)
├─ calendario/                 publicacion.csv (lo que se sube) y calendario.csv (registro de cortes)
└─ tools/fonts/                tipografías (licencia OFL)
```

Las carpetas de datos (`inbox`, `jobs`, `clips`, `tmp`, `reportes`, `referencias`, `comunidad`, `.venv`, `tools/ffmpeg`, modelos)
se crean solas al usar el sistema y **no** van al repo.

**Rutas:** todo cuelga de `CLIPARDO_HOME`. Si no definís esa variable, es la carpeta del repo. Si querés las skills en otro
lado, definí `CLIPARDO_SKILLS`. Ponelo en un disco con lugar: un stream bajado + clips ocupa varios GB.

**Cuentas:** en `clipardo.config.json` cambiá `tucuenta.arg` y `tucuenta.todo` por tus cuentas (sin @). La cuenta `arg`
recibe los streamers de `streamers_cuenta_local`; la cuenta `todo`, el resto. La marca de agua y el usuario de la
tarjeta "Seguir" se cambian en `.claude/skills/ig-editor/config.json` (`marca_agua.texto` y `seguir.usuario`).

---

## Qué hace cada pieza

### 1. Vigilante — `vigilar.bat` → `clip-finder/vigilar.py`
Cada 10 min mira si los canales de la lista `CANALES` (en `vigilar.py`) están en vivo, sin bajar nada (yt-dlp).
Cuando uno termina, busca el VOD y lo agrega a `inbox/links.txt`. Cada canal tiene filtro: `siempre` o `gta`
(solo si el título del directo menciona GTA). **Cambiá la lista por los streamers que te interesen.**

`clip-finder/comunidad.py` (bucle `scripts/comunidad-loop.sh`) trae además los clips más vistos que hizo la comunidad
en Kick/Twitch en las últimas horas y prepara los mejores.

### 2. Preparar / transcribir — `clipfinder.py prepare`
Baja solo el audio del VOD, lo transcribe completo con **Whisper large-v3-turbo** (GPU si hay, si no CPU), baja el chat
(Twitch con TwitchDownloaderCLI opcional, YouTube con yt-dlp) y puntúa cada tramo por audio, risas, palabras gatillo,
emotes y picos de chat. Deja todo en `jobs/<job>/` con un `review.md` corto para elegir.
`scripts/preparar-siempre.sh` lo corre en bucle sobre el inbox (nunca dos Whisper a la vez).

### 3. Elegir con Claude — skill `clip-finder`
En Claude Code: *"clipeá los streams nuevos"*. Claude lee `review.md` y `buscar_momentos.py <job>` (no la transcripción
entera, para gastar pocos tokens), elige los momentos, les pone título de pantalla, hook y caption.
Descarta solo lo que menciona casino/apuestas/códigos (`descartar_si_menciona` en `clip-finder/config.json`).

### 4. Cortar — `clipfinder.py cut <job>`
Baja **solo** esos tramos del video (hasta 1080p, la versión de más bitrate) y genera en `clips/raw/<job>/`
el `.mp4`, un `.json` con palabras y tiempos (para subtítulos) y un `.srt`.

### 5. Editar — skill `ig-editor` → `igeditor.py render <job>`
Pasa cada clip a 9:16: cámara tipo tarjeta (detecta la cara del streamer), layouts automáticos, subtítulos quemados
palabra por palabra, hook, zoom, audio normalizado a -14 LUFS, portada `.jpg` y caption `.txt`.
Todo se ajusta en `ig-editor/config.json`. El mapa de funciones del editor está en `ig-editor/MAPA.md`.

### 6. Detección de acción
`igeditor.py` mide el movimiento de la imagen (`movimiento()`): si el clip es de **acción** (gaming con mucho movimiento)
saca los subtítulos para no tapar y agrega pulsos de zoom al ritmo. `scripts/reeditar-accion.sh` re-edita con ese estilo
lo que ya estaba programado.

### 7. Capa final — `remotion_final.py` + `remotion-clipardo/`
Remotion pone encima: título, "golpe" (zoom con desenfoque en el remate), subtítulos con rebote que siguen la cara,
la tarjeta "Seguir" con tu logo, marca de agua y sonidos (`public/sfx`). Reemplaza el `.mp4` final.

### 8. Autocorrector — `revisar.py <job> --arreglar`
Revisa cada Reel terminado sin gastar tokens: que el título no se pise con los subtítulos, que en gaming la cámara
muestre una cara entera y que los textos no tapen la cara. Corrige solo lo que puede (mueve el título, vuelve a
renderizar con la webcam del stream) y deja `revision=ok` o "quedan problemas". El publicador **no sube** lo que no pasó la
revisión: en su lugar sale el siguiente de la misma cuenta que sí pasó.
`scripts/cola-edicion.sh` hace en cadena: render → Remotion → revisar, para cada job de `tmp/cola-edicion.txt`.

### 9. Auto-aprobar — `scripts/auto-aprobar.sh` → `publicador/aprobar_y_ordenar.py`
Cada job que la cola dejó con `revision=ok` se suma al calendario (`plan_contenido.py`), pasa de "pendiente de ok" a
"programado" y se reordena: mejor valoración primero, sin repetir streamer seguido. Si preferís aprobar a mano, no
corras este bucle y usá `plan_contenido.py --aprobar`.

### 10. Publicador — `publicador/publicar.bat` → `publicador.py pendientes`
Cada 5 min sube los Reels "programado" cuya hora ya llegó (horarios en `plan_contenido.py`: 1 por hora de 10 a 23 por cuenta).
Sube el video directo desde la PC (carga reanudable de Meta, sin hosting). Si pesa mucho, sube una copia más liviana.
**Reintentos:** si Instagram falla, reintenta con un contenedor nuevo; si sigue fallando, el horario no se pierde
(sale el siguiente de la cola y el que falló reintenta en el próximo turno, hasta 8 veces antes de quedar en "error").
Pausa por cuenta: creá el archivo vacío `calendario/pausa_<clave>` (ej. `pausa_todo`) y esa cuenta no publica.
Después de publicar corre `limpiar.py`, que libera disco borrando lo ya subido.

Otros comandos: `publicador.py verificar` (prueba los tokens, no publica) y
`publicador.py publicar --cuenta arg --video RUTA.mp4 --caption-file RUTA.txt` (uno a mano).

### 11. Calendario HTML — `publicador/ver_calendario.py --loop`
Genera `calendario.html` (en la raíz) cada 2 min: una columna por cuenta, con miniatura, hora, estado
(programado / publicado / error / reintentos). Abrilo en el navegador; se recarga solo.

### 12. Reporte diario — `reporte.bat` → `publicador/reporte_diario.py`
Resumen del día en `reportes/AAAA-MM-DD.md` y `estado-hoy.md`: publicados, errores, cola que queda, Reels que no pasan
la revisión, seguidores y métricas por Reel (vistas, alcance, likes, guardados, tiempo de visualización) que guarda en
`reportes/historial.csv`. Con `--sin-api` no consulta Instagram.

### Aprender
`ig-editor/aprender.py` analiza Reels/TikToks de referencia (vistas, likes, hojas de cuadros) sin bajar todo y arma
`referencias/aprender/resumen.md`. `aprendizajes.md` es el historial de correcciones de edición: cada vez que le
corregís algo a Claude, lo anota ahí y lo aplica de ahí en adelante.

### CapCut (opcional, no incluido)
`igeditor.py render --capcut` deja datos para un borrador editable de CapCut, pero el exportador
(`tools/capcut_export.py` + VectCutAPI) **no viene en este repo**. Sin eso, el resto funciona igual.

---

## Tokens de las cuentas (para poder subir los videos)

El publicador lee los tokens de **`publicador/tokens.env`**. Ahí va el token (y el id) de **cada cuenta de Instagram**
donde querés publicar. **Sin ese archivo el publicador no sube nada** (todo lo demás —clipear, editar, calendario—
anda igual).

El repo trae `publicador/tokens.env.example` con los nombres de las variables:

```
CLIPARDO_ARG_TOKEN=
CLIPARDO_ARG_ID=
CLIPARDO_TODO_TOKEN=
CLIPARDO_TODO_ID=
```

(`ARG` y `TODO` son las claves de las cuentas en `clipardo.config.json`; si agregás otra cuenta `xxx`, sumá
`CLIPARDO_XXX_TOKEN` y `CLIPARDO_XXX_ID`.)

### Cómo conseguir los tokens
1. Las cuentas de Instagram tienen que ser **profesionales** (Creador o Empresa): en la app de IG → Configuración →
   Tipo de cuenta.
2. Entrá a **[developers.facebook.com](https://developers.facebook.com/)** → *Mis apps* → **Crear app** (tu propia app;
   no se comparte la de nadie).
3. En la app: **Casos de uso → Personalizar** → **"API setup with Unified login"** (API de Instagram con inicio de sesión
   de Instagram).
4. **Agregá los permisos**:
   - `instagram_business_content_publish` → para publicar Reels.
   - `instagram_business_manage_insights` (o `instagram_manage_insights`, según cómo lo muestre Meta) → para las
     estadísticas del reporte diario. Opcional: sin él, el reporte ordena por likes.
   - `instagram_business_basic` viene por defecto.
5. En la sección de configuración de la API, agregá cada cuenta de Instagram (te pide iniciar sesión con esa cuenta)
   y tocá **"Generar token"** en cada una. Copiá el token (empieza con `IG...`) y el id de la cuenta.
6. Copiá `publicador/tokens.env.example` como `publicador/tokens.env` y pegá cada token e id en su línea.
7. Probalo (no publica nada, solo lee el usuario de cada cuenta):

   ```powershell
   .venv\Scripts\python.exe -I publicador\publicador.py verificar
   ```
   Tiene que decir `OK -> @tucuenta` para cada una.

Mientras la app de Meta esté en modo desarrollo, las cuentas tienen que estar agregadas como testers/roles de la app.
Los tokens de larga duración vencen a los ~60 días: si `verificar` da error de token, generá uno nuevo y reemplazalo.

> ⚠️ **`tokens.env` nunca se sube a GitHub**: está en `.gitignore`. No lo pegues en chats ni en issues. Si alguna vez
> se filtra, regenerá los tokens desde la app de Meta. Claude Code tiene la instrucción de no leerlo nunca.

---

## Uso diario

1. Prendés la PC → doble clic en **`arrancar-clipardo.bat`** (o programalo al iniciar sesión, ver INSTALAR.md).
2. Abrís Claude Code en la carpeta del repo y pedís: *"clipeá los streams nuevos"*.
3. Mirás `calendario.html`. Lo que pase la revisión se aprueba y se publica solo.
4. A la noche, `reporte.bat` deja el resumen en `estado-hoy.md`.

Correcciones: *"correcciones: clip 03 del job X, seg 12 el subtítulo tapa la cara"* → Claude lo arregla, lo anota en
`aprendizajes.md` y re-renderiza solo ese clip.

## Licencias y avisos
- **Remotion** tiene licencia propia: es **gratis para individuos y empresas/equipos chicos (hasta 3 personas)**; arriba de
  eso hace falta una *Company License*. Ver [remotion.dev/license](https://www.remotion.dev/license).
- Tipografías de `tools/fonts` y `remotion-clipardo/public`: SIL Open Font License (licencias incluidas).
- Los clips son de los streamers: respetá sus reglas y las de Instagram (crédito en el caption, nada de casino ni códigos).
