#!/usr/bin/env node
// CLI de generacion de imagenes con APIMart.
//   npm run gen -- "un panda astronauta" --model seedream-4.5 --size 16:9
import { parseArgs } from 'node:util';
import path from 'node:path';
import { ApimartClient, ApimartError, downloadImages, loadEnv, slugify } from './apimart.js';
import { MODELS, DEFAULT_MODEL, resolveModel } from './models.js';

loadEnv();

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    model: { type: 'string', short: 'm' },
    size: { type: 'string', short: 's' },
    resolution: { type: 'string', short: 'r' },
    n: { type: 'string' },
    ref: { type: 'string', multiple: true },
    out: { type: 'string', short: 'o' },
    name: { type: 'string' },
    'no-download': { type: 'boolean', default: false },
    nsfw: { type: 'boolean', default: false },
    watermark: { type: 'boolean', default: false },
    json: { type: 'boolean', default: false },
    'list-models': { type: 'boolean', default: false },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

function printModels() {
  console.log('\nModelos disponibles:\n');
  for (const m of Object.values(MODELS)) {
    const def = m.id === DEFAULT_MODEL ? '  (por defecto)' : '';
    console.log(`  ${m.id}${def}`);
    console.log(`    ${m.label}`);
    console.log(`    size:       ${m.sizes ? m.sizes.join(', ') : 'libre (sin validacion local)'}`);
    const res = m.resolutions ? m.resolutions.join(', ') : 'libre';
    console.log(`    resolution: ${res}   n max: ${m.maxN ?? '-'}   refs max: ${m.maxRefs ?? '-'}`);
    const otros = [...(m.aliases ?? []), ...(m.variants ?? [])];
    if (otros.length) console.log(`    tambien:    ${otros.join(', ')}`);
    console.log('');
  }
}

function printHelp() {
  console.log(`
Generacion de imagenes con APIMart

Uso:
  npm run gen -- "<prompt>" [opciones]

Opciones:
  -m, --model <id>        Modelo (default: ${process.env.APIMART_MODEL || DEFAULT_MODEL})
  -s, --size <ratio>      Aspect ratio: 1:1, 16:9, 9:16, 4:3... o pixeles (1881x836 en gpt-image-2)
  -r, --resolution <t>    Nivel de salida: 1K / 2K / 4K segun el modelo
      --n <num>           Cuantas imagenes generar (segun limite del modelo)
      --ref <url>         Imagen de referencia (repetible) -> modo image-to-image
  -o, --out <dir>         Carpeta de salida (default: ${process.env.APIMART_OUTPUT_DIR || 'output'})
      --name <slug>       Prefijo del archivo (default: derivado del prompt)
      --no-download       Solo imprime las URLs, no descarga
      --nsfw              Activa moderacion de contenido (nsfw_check)
      --watermark         Marca de agua (solo modelos que lo soportan)
      --json              Salida en JSON (para scripting)
      --list-models       Lista los modelos del catalogo
  -h, --help              Esta ayuda

Ejemplos:
  npm run gen -- "un zorro origami sobre musgo, luz suave" --size 16:9 --resolution 4K
  npm run gen -- "convierte esto en acuarela" --model nano-banana --ref https://ejemplo.com/foto.jpg
  npm run gen -- "logo minimalista de una montana" --model gpt-image-2 --resolution 2k
`);
}

if (values.help || (!positionals.length && !values['list-models'])) {
  printHelp();
  process.exit(values.help ? 0 : 1);
}

if (values['list-models']) {
  printModels();
  process.exit(0);
}

const prompt = positionals.join(' ').trim();
const modelName = values.model || process.env.APIMART_MODEL || DEFAULT_MODEL;
const model = resolveModel(modelName);
const outDir = values.out || process.env.APIMART_OUTPUT_DIR || 'output';
const n = values.n ? Number(values.n) : 1;

// Validaciones locales, para fallar antes de gastar creditos.
const problems = [];
if (model.sizes && values.size && !model.sizes.includes(values.size) && !/^\d+x\d+$/.test(values.size)) {
  problems.push(`size "${values.size}" no valido para ${model.id}. Validos: ${model.sizes.join(', ')}`);
}
if (model.resolutions && values.resolution && !model.resolutions.includes(values.resolution)) {
  problems.push(`resolution "${values.resolution}" no valido para ${model.id}. Validos: ${model.resolutions.join(', ')}`);
}
if (model.maxN && (!Number.isInteger(n) || n < 1 || n > model.maxN)) {
  problems.push(`n debe estar entre 1 y ${model.maxN} para ${model.id}.`);
}
if (model.maxRefs && values.ref && values.ref.length > model.maxRefs) {
  problems.push(`maximo ${model.maxRefs} imagenes de referencia para ${model.id}.`);
}
if (problems.length) {
  for (const p of problems) console.error('Error: ' + p);
  process.exit(1);
}

const log = values.json ? () => {} : (...a) => console.log(...a);

try {
  const client = new ApimartClient();

  log(`\nModelo:  ${model.id}`);
  log(`Prompt:  ${prompt}`);
  log(`Ajustes: size=${values.size ?? model.defaults?.size ?? 'auto'} resolution=${values.resolution ?? model.defaults?.resolution ?? '-'} n=${n}`);
  if (values.ref?.length) log(`Refs:    ${values.ref.length} imagen(es)`);
  log('');

  const started = Date.now();
  const result = await client.generateImage({
    prompt,
    model: model.id,
    size: values.size,
    resolution: values.resolution,
    n,
    imageUrls: values.ref,
    nsfwCheck: values.nsfw ? true : undefined,
    watermark: values.watermark ? true : undefined,
    onProgress: ({ status, progress }) => log(`  ... ${status} ${progress}%`),
  });

  const secs = ((Date.now() - started) / 1000).toFixed(1);

  let files = [];
  if (!values['no-download']) {
    const prefix = values.name || slugify(prompt);
    files = await downloadImages(result.urls, { outDir, prefix });
  }

  if (values.json) {
    console.log(JSON.stringify({ taskId: result.taskId, urls: result.urls, files, seconds: Number(secs) }, null, 2));
  } else {
    log(`\nListo en ${secs}s (task ${result.taskId ?? 'sync'})`);
    for (const u of result.urls) log(`  URL:     ${u}`);
    for (const f of files) log(`  Guardado: ${path.resolve(f)}`);
    if (result.task?.cost !== undefined) log(`  Costo:   $${result.task.cost} (${result.task.credits_cost} creditos)`);
    log('\nNota: las URLs de APIMart caducan (~24 h). Los archivos locales no.\n');
  }
} catch (err) {
  if (err instanceof ApimartError) {
    console.error('\nError de APIMart: ' + err.message);
    if (err.body && process.env.APIMART_DEBUG) console.error(JSON.stringify(err.body, null, 2));
  } else {
    console.error('\nError: ' + (err?.message ?? err));
  }
  process.exit(1);
}
