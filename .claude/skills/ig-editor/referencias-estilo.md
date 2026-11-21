# Estilo de referencia (Reels que le gustan al usuario)

Análisis de los 20 videos de `<CLIPARDO_HOME>\referencias\` (2026-11-16; uno estaba repetido). Es el estilo a recrear con identidad Clipardo (verde #53FC18).

## De qué tratan

Charlas entre streamers argentinos: preguntas sacadas ("¿vendiste medias?", "¿tenés un hijo?"), anécdotas (helicóptero de Duki, la Kawasaki robada, el clip de Canal 26), bardeo entre amigos, debates ("Robleis es el 1 de Argentina"), gaming con amigos (FC / Top Globales) y lore de la comunidad ("cokismo", retos, canciones). El remate casi siempre es **la reacción**: risas, tapar la cara, tirarse al piso.

## Números

| Dato | Valor |
|---|---|
| Duración | 8 a 110 s, mediana ~30 s (la mayoría entre 20 y 50) |
| Ritmo en charlas | un cambio de plano cada **1,5 a 3 s** (Joaco 1,5 s; Duki 2,1 s; Perdón 2,4 s) |
| Silencios | cortados al ras (jump cuts), sin aire entre frases |
| Resolución | 1080x1920 o 576x1024 (los de TikTok) |

## Reglas de edición que se repiten

1. **Sin título grande arriba** en la mayoría: arrancan directo con la frase. Solo 2 de 20 tienen texto fijo arriba (King: 2 líneas, blanco + verde; Gardel: título tipo meme).
2. **Subtítulos de 1 a 3 palabras**, tamaño medio, blanco con borde/sombra negra, **centrados a media altura** (pecho/cara, ~55-70 % de la pantalla), sin caja de fondo.
3. **Color de subtítulo por persona**: el que habla principal en blanco, el otro en amarillo, verde, rosa o celeste. Así se entiende quién dice qué sin ver la boca.
4. **Pantalla completa de quien habla** (primer plano, cámara de su stream) y se corta a la otra persona en cada intervención.
5. **Pantalla dividida (2 o 3 paneles apilados)** cuando importa la reacción de los otros: risas, alguien que escucha la pregunta sacada. Se alterna completa ↔ dividida.
6. **Inserto de imagen cuando se nombra algo**: foto chiquita de la persona mencionada (Spreen, Robleis), de la moto cuando dicen "Kawasaki", del personaje cuando dicen "el loco Flint". Aparece unos 1-2 s, abajo o al costado, sin tapar la cara.
7. **Remate en blanco y negro** (y a veces cámara lenta) sobre la risa final.
8. **Golpe de zoom con desenfoque** en el momento fuerte (Gardel 6 s).
9. **Censura con símbolos** en el subtítulo para palabras fuertes ("g#rd0").
10. Marca de agua chica del canal arriba a la izquierda (viene del stream: "K/coker") y, en algunas cuentas, logo de la cuenta + "SEGUIME" aparece un instante.
11. **Gaming**: gameplay de fondo con la webcam chica arriba y una **cara recortada (sticker)** del que habla con el subtítulo debajo.

## Qué ya hace ig-editor y qué falta

| Regla | Estado |
|---|---|
| Primer plano de quien habla, corte por turnos | Hecho. En Discord: zoom al recuadro de quien habla (corrección del 2026-11-17) |
| Silencios cortados | Hecho (cortes de silencio) |
| Subtítulos 1-3 palabras a media altura | Hecho (`max_palabras` 2, hasta 3 si son cortas; `y_frac` 0,62) |
| Color de subtítulo por persona | Hecho: blanco, rosa, azul, naranja. En Discord por el anillo verde; con una sola cámara, por la voz (`voice_speakers`) |
| Pantalla dividida en reacciones | Hecho en Discord (2 paneles cuando hablan/se ríen dos a la vez). Falta para dos en una cámara |
| Hook arriba | Hecho: apagado por defecto (`hook.mostrar` false); se sigue usando en portada y caption |
| Remate en blanco y negro | Hecho: últimos 1,8 s en B/N si el final es risa (audio alto y ≤3 palabras) (`cierre_bn`) |
| Golpe de zoom | Parcial (punch-in); falta el desenfoque radial |
| Insertos de imagen al nombrar algo | Falta: necesita las imágenes (las elige el usuario o se buscan a mano) |
| Tipografía | Hecho: Poppins ExtraBold 88 con animación pop, borde + sombra negra sólida |
| Marca de agua | Hecho: `@clipardo` arriba a la izquierda |
| Censura con símbolos | Hecho (`subtitulos.censura`, ej. mierda → m13rd@) |
| Sticker de cara en gaming | Más adelante |

## Aprendido de TikTok (2026-11-18)

Ver <CLIPARDO_HOME>\referencias\aprender\lo-que-funciona.md: los virales (1-10 M) casi no tienen edición; gana el momento (IRL, absurdo, personajes conocidos) + título fijo arriba en mayúsculas. Herramienta: aprender.py (modo lista / links) y perfiles vistos en el navegador con sesión del usuario.
