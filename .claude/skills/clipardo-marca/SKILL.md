---
name: clipardo-marca
description: Identidad de marca de Clipardo (@clipardo), la cuenta de clips de streamers argentinos. Usar SIEMPRE que se escriba o diseñe algo de la cuenta - hooks, captions, portadas, bio, respuestas a comentarios, posts, historias, mails a sponsors o streamers - y antes de que ig-editor renderice. También cuando el usuario pregunte "¿esto va con la marca?" o pida revisar textos de la cuenta.
---

# Clipardo: guía de marca

## Identidad

| Dato | Valor |
|---|---|
| Nombre | **Clipardo** (siempre con mayúscula inicial al escribirlo; el @ va en minúsculas) |
| Handle | **@clipardo** en Instagram; el mismo en TikTok y YouTube cuando se replique |
| Qué es | Los mejores momentos de humor de los streamers argentinos, editados para ver en el celu |
| Qué NO es | Una fan page de un streamer, una cuenta de chimentos ni de casino |
| Público | 18-34, Argentina, consume Kick/Twitch/YouTube, entiende el slang |

**Promesa:** "lo que te perdiste del vivo, en 30 segundos".

## Paleta

| Rol | Color | Uso |
|---|---|---|
| Acento de marca | **Verde #53FC18** | Texto del hook, palabras grandes de la portada, detalles de historias, logo |
| Texto principal | Blanco #FFFFFF | Subtítulos (siempre blancos, sin resaltar la palabra activa) |
| Fondo / contraste | Negro #000000 | Caja del hook (translúcida), bordes y sombras |

Reglas:
- El verde va **sobre negro o sobre la caja oscura**, nunca suelto sobre fondos claros (se lee mal).
- **Un solo color de acento**. No sumar amarillos, rojos ni degradés.
- El verde es parecido al de Kick pero la marca **no es de Kick**: no usar su logo, su tipografía ni decir "oficial".

## Tipografía

| Uso | Fuente |
|---|---|
| Hook, portada, crédito, subtítulos "limpio" | Montserrat ExtraBold |
| Subtítulos "bubble" (A/B) | Luckiest Guy |

Subtítulos y captions en **minúsculas**. Portada en **MAYÚSCULAS**. Los tamaños y posiciones viven en `ig-editor/config.json`: no los cambies desde acá.

## Voz: tres registros

La cuenta habla en **rioplatense**, con voseo, como alguien que te pasa un video por WhatsApp. Según el clip se usa uno de tres registros:

| Registro | Cuándo | Ejemplo de línea 1 del caption |
|---|---|---|
| **Amigo** (por defecto, ~70% de los Reels) | Frases icónicas, ataques de risa, fails, IRL | `le preguntaron a coscu qué haría con un millón de dólares 💀` |
| **Picante** (~20%) | Bardeos con el chat u otro streamer, situaciones donde el streamer queda expuesto | `goncho se creyó que nadie lo iba a clipear 😭` |
| **Neutral** (~10% y siempre que haya sponsor) | Reels patrocinados, temas sensibles, comunicados, mails | `davoo cuenta cómo arrancó a streamear` |

Límites del registro picante: se gasta **la situación**, no a la persona. Nunca insultos, nada sobre físico, familia, salud, orientación, religión ni nacionalidad. Si dudás, va en registro amigo.

### Palabras y recursos

- Sí: `bo`, `posta`, `una locura`, `no puede ser`, `cualquiera`, `ni en pedo`, `el chat`, `quedó`, `se pudrió`, `lo mandaron al frente`.
- Emojis: máximo 2 por caption. Preferidos 💀 😭 🤣 👇. Nada de 🔥🔥🔥 ni cadenas de emojis.
- No: "increíble momento", "no te lo podés perder", "épico", mayúsculas sostenidas, signos múltiples (`!!!`), clickbait que el clip no cumple.
- Nunca hablar en nombre del streamer ni inventar lo que dijo.

## Plantillas

### Hook (texto en pantalla, 0-2,2 s)
- 3 a 7 palabras, minúsculas, en verde sobre la caja negra.
- Abre una pregunta o adelanta el conflicto sin spoilear el remate: `le preguntaron cuánto gana y…`, `el chat no lo podía creer`, `nadie esperaba esta respuesta`.
- Alternar hooks **pregunta** y **afirmación** (test de la semana 2).

### Título fijo en pantalla (desde 2026-11-18)
- Arriba durante todo el Reel, como los clips virales de TikTok: **MAYÚSCULAS**, 3-6 palabras, "NOMBRE + qué pasó", blanco sobre caja oscura. Es la excepción a "nada de mayúsculas sostenidas" (que sigue valiendo para captions).

### Caption
```
<TÍTULO EN MAYÚSCULAS, el mismo titulo_pantalla>
<línea 2: contexto o remate en minúsculas, registro elegido, 0-1 emoji>
<CTA: una sola, pregunta o "mandáselo a…"> 👇

🎥 @<instagram del streamer> en vivo en <Kick|Twitch|YouTube>
#<streamer> #<tema, ej. gta6 #gtavi> #streamersargentinos #<plataforma> #fyp #parati [#topglobales #argentina] #clipardo
```
- Desde 2026-11-19 (pedido del usuario, copiando a @gonchotwm y @kickcl1pstv): **el título en MAYÚSCULAS va primero** (es lo que se ve en el feed) y van 7-10 hashtags. `#topglobales` solo para Coker, Goncho, Zeko y Joaco; `#argentina` en toda @clipardo.arg. `plan_contenido.py` lo arma solo (`formato_caption`) a partir del caption de siempre: en `selections.json` alcanza con línea + CTA + crédito + hashtags base.
- Siempre el crédito (decidido 2026-11-19): las campañas pagas de clipping lo exigen, al streamer le llega la notificación y puede repostear, y baja el riesgo de reclamos.
- El @ es el de **Instagram**, sacado de `instagram.json` (verificados). Si el streamer no está ahí, usar el @ de la plataforma y nunca adivinar uno de Instagram (etiquetaría a otra persona; ej. @danirep no es Dani Rep).
- `#clipardo` va siempre. En @clipardo.todo, `#streamers` en vez de `#streamersargentinos`.
- Con sponsor: agregar `Publicidad` / etiqueta de colaboración de Instagram y, si es juego, `+18 · jugá con responsabilidad`.

### Portada
- Cara del streamer más grande que el texto.
- 2 a 5 palabras en MAYÚSCULAS, en **verde** con borde negro (ig-editor lo hace solo), dentro del recorte 4:5 de la grilla.
- Sin logos de casinos ni de otras cuentas.

### Bio de Instagram
```
Clipardo 🎬
lo que te perdiste del vivo, en 30 segundos
streamers argentinos · todos los días
📩 colabs: <mail>
```

### Respuesta a comentarios
Registro amigo, corta, en minúsculas. Si el comentario es un pedido de baja de un streamer o un reclamo de derechos: **no responder en público**, avisar al usuario.

## Checklist antes de publicar

- [ ] Hook en verde, 3-7 palabras, no spoilea el remate
- [ ] Subtítulos blancos, minúsculas, sin errores de slang ni nombres
- [ ] Caption con un registro claro, una sola CTA, crédito y `#clipardo`
- [ ] Máximo 2 emojis, nada de mayúsculas sostenidas
- [ ] Sin insultos discriminatorios, sin logos ni códigos de casinos
- [ ] Portada: cara grande + texto en verde dentro del 4:5
- [ ] Si hay sponsor: registro neutral + etiqueta de publicidad (+18 si es juego)
