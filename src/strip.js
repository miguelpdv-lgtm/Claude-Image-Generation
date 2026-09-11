#!/usr/bin/env node
// Limpia metadatos de imagenes ya existentes en disco (in-place).
//   npm run strip -- output stickers
//   npm run strip -- --check output      (solo informa, no escribe)
import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { stripMetadata, findProvenance, detectFormat } from './metadata.js';

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    check: { type: 'boolean', default: false },
    help: { type: 'boolean', short: 'h', default: false },
  },
});

if (values.help || !positionals.length) {
  console.log(`
Limpieza de metadatos (C2PA / Content Credentials, Exif, XMP)

Uso:
  npm run strip -- <archivo|carpeta> [...]     limpia in-place
  npm run strip -- --check <archivo|carpeta>   solo verifica, no escribe

Conserva perfil ICC, DPI, transparencia y gamma. Formatos: PNG, JPEG, WebP.
`);
  process.exit(values.help ? 0 : 1);
}

const EXT = /\.(png|jpe?g|webp)$/i;

function collect(target) {
  const stat = fs.statSync(target);
  if (stat.isFile()) return EXT.test(target) ? [target] : [];
  return fs
    .readdirSync(target, { withFileTypes: true })
    .flatMap((e) => collect(path.join(target, e.name)));
}

const files = positionals.flatMap(collect);
if (!files.length) {
  console.log('No se encontraron imagenes (png/jpg/webp) en: ' + positionals.join(', '));
  process.exit(0);
}

let touched = 0;
let dirty = 0;

for (const file of files) {
  const before = fs.readFileSync(file);

  if (values.check) {
    const found = findProvenance(before);
    if (found.length) {
      dirty++;
      console.log(`  SUCIO  ${file}`);
      for (const f of found) console.log(`           ${f}`);
    }
    continue;
  }

  const { buffer, format, removed } = stripMetadata(before);
  if (!format) {
    console.log(`  OMITIDO ${file} (formato no reconocido)`);
    continue;
  }
  if (!removed.length) continue;

  fs.writeFileSync(file, buffer);
  touched++;
  const saved = before.length - buffer.length;
  console.log(`  LIMPIO ${file}  (-${saved} B: ${removed.map((r) => r.name).join(', ')})`);

  const rest = findProvenance(buffer);
  if (rest.length) console.log(`           AVISO, queda: ${rest.join(', ')}`);
}

if (values.check) {
  console.log(`\n${files.length} archivo(s) revisado(s), ${dirty} con metadatos.`);
  process.exit(dirty ? 1 : 0);
}
console.log(`\n${files.length} archivo(s) revisado(s), ${touched} modificado(s).`);
