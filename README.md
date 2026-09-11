# Image Generation — APIMart

Generación de imágenes por línea de comandos usando la API de [APIMart](https://apimart.ai).
Sin dependencias externas: solo Node.js ≥ 20 (aquí: v22.20.0) y `fetch` nativo.

## 1. Configurar la API key

Consigue la key en <https://apimart.ai/keys> y pégala en el archivo `.env`:

```
APIMART_API_KEY=sk-tu-key-aqui
```

`.env` está en `.gitignore`; `.env.example` es la plantilla compartible.

Verifica que todo funcione (no gasta créditos):

```bash
npm run check
```

## 2. Generar imágenes

```bash
npm run gen -- "un zorro origami sobre musgo, luz suave de amanecer" --size 16:9 --resolution 4K
```

Las imágenes se descargan en `output/` y también se imprimen las URLs.

### Opciones

| Opción | Descripción |
| --- | --- |
| `-m, --model <id>` | `seedream-4-5` (default), `seedream-5-0-pro`, `gpt-image-2`, `nano-banana-pro`, `nano-banana`, `flux-2-pro`, `qwen-image-3.0`, `z-image-turbo` — ver `npm run models` |
| `-s, --size <ratio>` | `1:1`, `16:9`, `9:16`, `4:3`, `21:9`, `auto`… (o píxeles tipo `1881x836` en `gpt-image-2`) |
| `-r, --resolution <t>` | `1K` / `2K` / `4K` según el modelo |
| `--n <num>` | Número de imágenes (1 en gpt-image-2, hasta 15 en seedream) |
| `--ref <url>` | Imagen de referencia, repetible → activa image-to-image |
| `-o, --out <dir>` | Carpeta de salida (default `output/`) |
| `--name <slug>` | Prefijo del archivo (default: derivado del prompt) |
| `--no-download` | Solo imprime URLs |
| `--nsfw` | Activa moderación de contenido |
| `--watermark` | Marca de agua (solo seedream) |
| `--json` | Salida JSON para scripting |
| `--list-models` | Lista el catálogo local |

### Ejemplos

```bash
npm run gen -- "logo minimalista de una montaña, línea única" --model gpt-image-2 --resolution 2k
```

```bash
npm run gen -- "conviértelo en acuarela suave" --model nano-banana --ref https://ejemplo.com/foto.jpg
```

```bash
npm run gen -- "4 variantes de un icono de brújula" --n 4 --size 1:1 --json
```

## 3. Usarlo como librería

```js
import { ApimartClient, downloadImages, loadEnv } from './src/apimart.js';

loadEnv();
const client = new ApimartClient();

const { urls } = await client.generateImage({
  prompt: 'una ciudad flotante al atardecer',
  model: 'seedream-4-5',
  size: '16:9',
  resolution: '4K',
  onProgress: ({ status, progress }) => console.log(status, progress),
});

await downloadImages(urls, { outDir: 'output', prefix: 'ciudad' });
```

## Estructura

```
.env               tu API key (ignorado por git)
.env.example       plantilla
src/apimart.js     cliente HTTP: crear tarea, polling, descarga
src/models.js      catálogo de modelos y sus límites
src/cli.js         interfaz de línea de comandos
src/check.js       diagnóstico de configuración
docs/apimart.md    resumen de la API (endpoints, parámetros, errores)
output/            imágenes generadas
```

## Verificado

Probado end-to-end el 2026-09-08 con la key de la cuenta: la API responde con 360 modelos,
y una generación 16:9 / 2K con `seedream-4-5` tardó **10.8 s** y costó **$0.026** (0.26 créditos).
El resultado quedó en `output/test_01.jpg`.

## Notas

- La API es **asíncrona**: `POST /v1/images/generations` devuelve un `task_id`, y el cliente hace polling a `GET /v1/tasks/{task_id}` cada 3 s hasta `completed`.
- Las URLs que devuelve APIMart **caducan (~24 h)**; por eso el CLI descarga los archivos por defecto.
- Errores comunes: `401` key inválida, `402` saldo insuficiente, `429` rate limit.
- Para ver el cuerpo completo de un error: `APIMART_DEBUG=1 npm run gen -- "..."`.
