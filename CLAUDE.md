# Claude-Image-Generation

Generación de imágenes por CLI contra la API de [APIMart](https://apimart.ai), más un
pipeline de post-proceso en Python para convertirlas en stickers troquelados, mockups de
frasco y pliegos de impresión A4.

## Arranque en un entorno nuevo

```bash
bash scripts/setup.sh    # verifica Node >= 20, activa los hooks, comprueba la API key
npm run check            # valida la conexión con APIMart (no gasta créditos)
```

`APIMART_API_KEY` llega como **variable de entorno** en cloud (no crees un `.env`;
`loadEnv()` no pisa lo que ya esté definido). Ver `docs/cloud.md`.

Las dependencias Python (`pip install -r requirements.txt`) sólo hacen falta para los
scripts de stickers/impresión. El CLI de generación no necesita ninguna.

## Reglas del proyecto

**Ninguna imagen sale con metadatos.** Los manifiestos C2PA / Content Credentials se
eliminan siempre. Ya está automatizado en tres capas — no hace falta hacerlo a mano, pero
tampoco lo desactives sin que te lo pidan:

- `downloadImages()` en `src/apimart.js` limpia por defecto al descargar
- `npm run strip -- <ruta>` limpia archivos existentes; `--check` verifica sin escribir
- `.githooks/pre-commit` rechaza commits con imágenes sucias

Si añades una ruta nueva que escriba imágenes a disco, pásala por
`stripMetadata()` de `src/metadata.js`.

**Nunca escribas la API key en el código, en un commit ni en la conversación.** `.env` está
en `.gitignore` y debe seguir estándolo.

**Sin dependencias npm.** El lado JS es Node puro a propósito (`fetch` nativo,
`node:util/parseArgs`). No hay `node_modules` ni `package-lock.json`; mantenlo así salvo
que se pida lo contrario.

## Comandos

```bash
npm run gen -- "<prompt>" [opciones]   # generar (ver README para el listado completo)
npm run models                          # catálogo local de modelos
npm run check                           # diagnóstico de configuración
npm run strip -- <ruta>                 # limpiar metadatos in-place
npm run strip -- --check .              # verificar, exit 1 si hay metadatos
```

Opciones que más se usan: `--model`, `--size`, `--resolution`, `--n`, `--ref <url>`
(image-to-image), `--out`, `--name`, `--json`.

## Estructura

| Ruta | Qué es |
| --- | --- |
| `src/apimart.js` | Cliente HTTP: crea tarea, hace polling, descarga, limpia metadatos |
| `src/cli.js` | CLI de generación |
| `src/models.js` | Catálogo de modelos con sus límites (tamaños, resoluciones, max N) |
| `src/metadata.js` | Limpieza de C2PA/Exif/XMP sin recomprimir |
| `src/strip.js` | CLI de limpieza y verificación |
| `src/check.js` | Diagnóstico de configuración |
| `src/*_stickers.py` | Recorte y troquelado de los motivos a sticker |
| `src/vectorize.py` | Trazado a vector (OpenCV) |
| `src/jar_mockup.py` | Composición del mockup de frascos |
| `src/print_sheet.py` | Pliego A4 en PDF con marcas de corte (reportlab, CMYK) |
| `stickers/`, `stickers_clear/` | Stickers generados, con su `build.json` |
| `print/` | PDF y AI listos para imprenta |
| `work/` | Material intermedio: crops, previews, rejillas de referencia |
| `output/` | Salida del CLI — **en `.gitignore`**, no se versiona |
| `docs/apimart.md` | Resumen de la API: endpoints, parámetros, errores |

## Detalles que muerden

- **La API es asíncrona.** `POST /v1/images/generations` devuelve un `task_id`; el cliente
  hace polling a `GET /v1/tasks/{id}` cada 3 s. No esperes la imagen en la primera respuesta.
- **Las URLs de APIMart caducan (~24 h).** Por eso el CLI descarga siempre por defecto.
- **`frasco.png` es en realidad un AVIF**, pese a la extensión. El limpiador de metadatos no
  soporta contenedores ISOBMFF y lo marca como no soportado en vez de darlo por limpio.
- **`.gitattributes` tiene `* -text`.** El repo mezcla código y binarios, y `core.autocrlf`
  corrompería los `.pdf` y `.ai` de `print/`. No lo quites.
- **Errores de APIMart:** `401` key inválida, `402` saldo insuficiente, `429` rate limit.
  Para ver el cuerpo completo: `APIMART_DEBUG=1 npm run gen -- "..."`.
- **Generar cuesta dinero real.** Una imagen 16:9 / 2K con `seedream-4.5` ronda los $0.026.
  Con `--n 4` son cuatro cobros. Pregunta antes de lanzar tandas grandes.
