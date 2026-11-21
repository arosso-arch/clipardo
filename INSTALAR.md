# Instalar Clipardo paso a paso (Windows 10/11)

Todo queda dentro de la carpeta del repo (`CLIPARDO_HOME`). **Elegí un disco con lugar** (mínimo ~30 GB libres:
modelos de Whisper, ffmpeg, streams y clips). En los comandos, `D:\clipardo` es un ejemplo: usá tu carpeta.

## 0. Bajar el repo
```powershell
git clone https://github.com/<usuario>/<repo>.git D:\clipardo
cd D:\clipardo
```

## 1. Git for Windows (trae Git Bash)
Los bucles de `scripts/*.sh` corren con Git Bash. Instalalo desde [git-scm.com](https://git-scm.com/download/win)
con las opciones por defecto. Si no quedó en `C:\Program Files\Git\bin\bash.exe`, definí la variable `GIT_BASH`
con la ruta a tu `bash.exe`.

## 2. Python 3.12 (64 bits)
Instalalo desde [python.org](https://www.python.org/downloads/) (3.12.x). Después, en la carpeta del repo:
```powershell
py -3.12 -m venv .venv
```
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Todo se corre siempre con ese Python y con `-I` (modo aislado): `.venv\Scripts\python.exe -I ...`.
`yt-dlp` queda instalado en `.venv\Scripts\yt-dlp.exe`, que es donde lo buscan el vigilante y `comunidad.py`.
Actualizalo seguido (Kick/Twitch cambian): `.venv\Scripts\python.exe -m pip install -U yt-dlp`.

## 3. ffmpeg
Bajá un build "full" de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) y descomprimilo en `tools\ffmpeg\`, de forma que
quede `tools\ffmpeg\<versión>\bin\ffmpeg.exe`. (Si ya tenés ffmpeg en el PATH, también lo encuentra.)
El publicador usa `ffmpeg` del PATH para la copia liviana: agregá esa carpeta `bin` al PATH o ponelo ahí también.

## 4. Whisper con GPU (opcional pero muy recomendado)
- Placa NVIDIA con driver actualizado (probado en una GTX 1650 de 4 GB con `int8_float16`).
- Las librerías CUDA vienen por pip (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12` en `requirements.txt`); no hace falta
  instalar el CUDA Toolkit.
- Para que el modelo se baje dentro del proyecto y no al disco C:
  ```powershell
  setx HF_HOME "D:\clipardo\tools\hf"
  ```
- Probá la GPU (baja el modelo large-v3-turbo la primera vez, ~1,6 GB):
  ```powershell
  .venv\Scripts\python.exe -I scripts\gpu_test.py
  ```
- Sin GPU funciona en CPU (más lento). Modelo y precisión se cambian en `.claude/skills/clip-finder/config.json` → `whisper`.

## 5. Node.js + Remotion
Instalá Node.js 22 LTS desde [nodejs.org](https://nodejs.org/). Después:
```powershell
cd remotion-clipardo
```
```powershell
npm ci
```
Para ver/editar las composiciones: `npm run dev` (abre Remotion Studio).
**Licencia de Remotion:** gratis para individuos y equipos chicos (hasta 3 personas); empresas más grandes
necesitan licencia ([remotion.dev/license](https://www.remotion.dev/license)).

## 6. Tipografías
Las tipografías ya vienen en `tools\fonts` (Poppins, Luckiest Guy, Montserrat; OFL). Las usa ffmpeg para los
subtítulos; no hace falta instalarlas en Windows.

## 7. Claude Code y las skills
- Instalá [Claude Code](https://claude.com/claude-code) y abrilo **en la carpeta del repo**. Las skills ya están en
  `.claude\skills\` (clip-finder, ig-editor, clipardo-marca, capcut-editor) y `CLAUDE.md` tiene las instrucciones.
- ¿Preferís las skills en otro proyecto? Copiá las 4 carpetas a `<tu proyecto>\.claude\skills\` y definí:
  ```powershell
  setx CLIPARDO_HOME "D:\clipardo"
  ```
  (así los scripts saben dónde están los datos aunque las skills vivan en otro lado).

## 8. Configurar tus cuentas
1. `clipardo.config.json`: poné tus cuentas en `usuario` y tus streamers locales en `streamers_cuenta_local`.
2. `.claude\skills\ig-editor\config.json`: `marca_agua.texto` y `seguir.usuario` con tu @.
3. `.claude\skills\clipardo-marca\SKILL.md`: la voz de la marca (adaptala a tu cuenta).
4. `.claude\skills\clip-finder\vigilar.py`: la lista `CANALES` con los streamers que querés vigilar.
5. Logos: `remotion-clipardo\src\Logos*.tsx` y `Seguir.tsx`.

## 9. Tokens de Instagram
Seguí el apartado **"Tokens de las cuentas (para poder subir los videos)"** del [README](README.md#tokens-de-las-cuentas-para-poder-subir-los-videos):
copiar `publicador\tokens.env.example` como `publicador\tokens.env`, pegar los tokens y probar con
```powershell
.venv\Scripts\python.exe -I publicador\publicador.py verificar
```

## 10. Primera prueba
1. Pegá el link de un VOD en `inbox\links.txt` (una línea por link).
2. Doble clic en `clipardo.bat` (prepara, y si ya elegiste clips, corta y edita), o en Claude Code pedí
   *"clipeá este VOD: <link>"*.
3. Los Reels terminados quedan en `clips\final\<job>\`.

## 11. Tareas de Windows (opcional)
Para que arranque solo, en el **Programador de tareas** (`taskschd.msc`) → *Crear tarea básica*:
- **"Clipardo"** — Desencadenador: *Al iniciar sesión* → Acción: iniciar programa `D:\clipardo\arrancar-clipardo.bat`.
- **"Reporte Clipardo"** — Desencadenador: *Diariamente 23:45* → Acción: `D:\clipardo\reporte.bat`.

O por consola:
```powershell
schtasks /Create /TN "Clipardo" /SC ONLOGON /TR "D:\clipardo\arrancar-clipardo.bat"
```
```powershell
schtasks /Create /TN "Reporte Clipardo" /SC DAILY /ST 23:45 /TR "D:\clipardo\reporte.bat"
```

## Opcionales
- **Chat de Twitch** para puntuar mejor: [TwitchDownloaderCLI](https://github.com/lay295/TwitchDownloader) en
  `tools\twitchdl\TwitchDownloaderCLI.exe`. Sin eso, se puntúa solo por audio y texto.
- **CapCut**: el exportador de borradores no viene en este repo (ver README).

## Problemas comunes
- *"No encuentro ffmpeg"* → revisá el paso 3.
- *Whisper en CPU aunque tengas GPU* → corré `scripts\gpu_test.py` y fijate el error de CUDA/driver.
- *El publicador dice "Falta publicador/tokens.env"* → paso 9.
- *yt-dlp no baja de Kick/Twitch* → `pip install -U yt-dlp`.
