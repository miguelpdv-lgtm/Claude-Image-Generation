// Limpieza de metadatos de imagen, sin dependencias (Node >= 20).
//
// Elimina los contenedores donde viaja la procedencia C2PA / Content Credentials:
//   JPEG -> marcador APP11 (JUMBF), APP1 (Exif/XMP), APP13 (Photoshop/IPTC), COM
//   PNG  -> chunk caBX (C2PA), mas eXIf / tEXt / zTXt / iTXt
//   WebP -> chunks C2PA, EXIF y "XMP "
//
// Conserva a proposito lo que afecta al render y a la impresion:
// perfil ICC, densidad/DPI, transparencia, gamma y flags de color.

const JPEG_SOI = 0xd8;
const JPEG_EOI = 0xd9;
const JPEG_SOS = 0xda;

// Chunks PNG que se conservan: criticos + los que afectan color/render/DPI.
const PNG_KEEP = new Set([
  'IHDR', 'PLTE', 'IDAT', 'IEND',          // criticos
  'tRNS', 'gAMA', 'cHRM', 'sRGB', 'iCCP',  // color
  'sBIT', 'bKGD', 'pHYs', 'sPLT', 'hIST',  // render / DPI
  'acTL', 'fcTL', 'fdAT',                  // APNG
]);

// Chunks WebP que se conservan.
const WEBP_KEEP = new Set(['VP8 ', 'VP8L', 'VP8X', 'ALPH', 'ICCP', 'ANIM', 'ANMF']);

// Bits de flags dentro del chunk VP8X (primer byte del payload).
const VP8X_FLAG_EXIF = 0x08;
const VP8X_FLAG_XMP = 0x04;

export function detectFormat(buf) {
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return 'jpeg';
  if (buf.length >= 8 && buf.readUInt32BE(0) === 0x89504e47 && buf.readUInt32BE(4) === 0x0d0a1a0a) {
    return 'png';
  }
  if (buf.length >= 12 && buf.toString('ascii', 0, 4) === 'RIFF' && buf.toString('ascii', 8, 12) === 'WEBP') {
    return 'webp';
  }
  // AVIF / HEIC: contenedor ISOBMFF. Se detecta pero NO se limpia (ver stripMetadata).
  if (buf.length >= 12 && buf.toString('ascii', 4, 8) === 'ftyp') {
    const brand = buf.toString('ascii', 8, 12);
    if (['avif', 'avis', 'heic', 'heix', 'mif1'].includes(brand)) return 'isobmff';
  }
  return null;
}

/**
 * Quita metadatos de un buffer de imagen.
 * @returns {{ buffer: Buffer, format: string|null, removed: Array<{name: string, bytes: number}> }}
 *          Si el formato no se reconoce devuelve el buffer intacto y format = null.
 */
export function stripMetadata(input) {
  const buf = Buffer.isBuffer(input) ? input : Buffer.from(input);
  const format = detectFormat(buf);
  if (format === 'jpeg') return stripJpeg(buf);
  if (format === 'png') return stripPng(buf);
  if (format === 'webp') return stripWebp(buf);
  // ISOBMFF (AVIF/HEIC): no se toca. Reescribir las cajas meta/iloc mal puede
  // romper el archivo, asi que se devuelve intacto y findProvenance() avisa.
  return { buffer: buf, format: format === 'isobmff' ? 'isobmff' : null, removed: [] };
}

// --- JPEG -------------------------------------------------------------------

function jpegSegmentName(marker, payload) {
  if (marker === 0xfe) return 'COM';
  const app = marker - 0xe0;
  const id = payload.toString('latin1', 0, Math.min(payload.length, 20)).split('\0')[0];
  return `APP${app}${id ? ` (${id})` : ''}`;
}

// APP0 (JFIF), APP2 con ICC_PROFILE y APP14 (Adobe) se conservan: densidad y color.
function jpegKeepsSegment(marker, payload) {
  if (marker === 0xe0) return true;                                     // JFIF
  if (marker === 0xe2) return payload.toString('latin1', 0, 11) === 'ICC_PROFILE'; // solo ICC
  if (marker === 0xee) return true;                                     // Adobe color transform
  if (marker >= 0xe0 && marker <= 0xef) return false;                   // resto de APPn (incl. APP11/C2PA)
  if (marker === 0xfe) return false;                                    // comentarios
  return true;
}

function stripJpeg(buf) {
  const out = [buf.subarray(0, 2)]; // SOI
  const removed = [];
  let i = 2;

  while (i < buf.length) {
    if (buf[i] !== 0xff) break; // desincronizado: copiamos el resto tal cual
    let marker = buf[i + 1];
    while (marker === 0xff) marker = buf[++i + 1]; // relleno de 0xFF

    // Marcadores sin payload.
    if (marker === JPEG_SOI || marker === JPEG_EOI || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      out.push(buf.subarray(i, i + 2));
      i += 2;
      continue;
    }
    if (i + 4 > buf.length) break;

    const len = buf.readUInt16BE(i + 2);
    const end = i + 2 + len;
    if (len < 2 || end > buf.length) break;

    if (marker === JPEG_SOS) {
      out.push(buf.subarray(i)); // cabecera SOS + datos comprimidos hasta EOI
      i = buf.length;
      break;
    }

    const payload = buf.subarray(i + 4, end);
    if (jpegKeepsSegment(marker, payload)) {
      out.push(buf.subarray(i, end));
    } else {
      removed.push({ name: jpegSegmentName(marker, payload), bytes: len + 2 });
    }
    i = end;
  }

  if (i < buf.length) out.push(buf.subarray(i));
  return { buffer: Buffer.concat(out), format: 'jpeg', removed };
}

// --- PNG --------------------------------------------------------------------

function stripPng(buf) {
  const out = [buf.subarray(0, 8)]; // firma
  const removed = [];
  let i = 8;

  while (i + 8 <= buf.length) {
    const len = buf.readUInt32BE(i);
    const name = buf.toString('latin1', i + 4, i + 8);
    const end = i + 12 + len; // len + type + data + crc
    if (end > buf.length) break;

    if (PNG_KEEP.has(name)) out.push(buf.subarray(i, end));
    else removed.push({ name, bytes: len + 12 });

    i = end;
    if (name === 'IEND') break;
  }

  return { buffer: Buffer.concat(out), format: 'png', removed };
}

// --- WebP -------------------------------------------------------------------

function stripWebp(buf) {
  const chunks = [];
  const removed = [];
  let i = 12; // RIFF + size + WEBP

  while (i + 8 <= buf.length) {
    const name = buf.toString('ascii', i, i + 4);
    const size = buf.readUInt32LE(i + 4);
    const padded = size + (size % 2); // los chunks RIFF se alinean a par
    const end = i + 8 + padded;
    if (end > buf.length) break;

    if (WEBP_KEEP.has(name)) chunks.push(Buffer.from(buf.subarray(i, end)));
    else removed.push({ name: name.trim(), bytes: padded + 8 });

    i = end;
  }

  // Si quitamos EXIF/XMP hay que bajar sus bits en los flags de VP8X.
  const vp8x = chunks.find((c) => c.toString('ascii', 0, 4) === 'VP8X');
  if (vp8x && vp8x.length >= 9) {
    const names = removed.map((r) => r.name);
    if (names.includes('EXIF')) vp8x[8] &= ~VP8X_FLAG_EXIF;
    if (names.includes('XMP')) vp8x[8] &= ~VP8X_FLAG_XMP;
  }

  const body = Buffer.concat(chunks);
  const header = Buffer.alloc(12);
  header.write('RIFF', 0, 'ascii');
  header.writeUInt32LE(body.length + 4, 4); // tamano = "WEBP" + chunks
  header.write('WEBP', 8, 'ascii');

  return { buffer: Buffer.concat([header, body]), format: 'webp', removed };
}

// --- Verificacion -----------------------------------------------------------

/**
 * Busca rastros de C2PA / metadatos en un buffer ya procesado.
 * @returns {string[]} lista de hallazgos (vacia = limpio)
 */
export function findProvenance(input) {
  const buf = Buffer.isBuffer(input) ? input : Buffer.from(input);
  const found = [];
  const format = detectFormat(buf);

  if (format === 'png') {
    let i = 8;
    while (i + 8 <= buf.length) {
      const len = buf.readUInt32BE(i);
      const name = buf.toString('latin1', i + 4, i + 8);
      if (!PNG_KEEP.has(name)) found.push(`chunk PNG ${name}`);
      i += 12 + len;
      if (name === 'IEND' || len > buf.length) break;
    }
  } else if (format === 'webp') {
    let i = 12;
    while (i + 8 <= buf.length) {
      const name = buf.toString('ascii', i, i + 4);
      const size = buf.readUInt32LE(i + 4);
      if (!WEBP_KEEP.has(name)) found.push(`chunk WebP ${name.trim()}`);
      i += 8 + size + (size % 2);
    }
  } else if (format === 'jpeg') {
    let i = 2;
    while (i + 4 <= buf.length && buf[i] === 0xff) {
      const marker = buf[i + 1];
      if (marker === JPEG_SOS) break;
      if (marker === JPEG_EOI || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
        i += 2;
        continue;
      }
      const len = buf.readUInt16BE(i + 2);
      if (len < 2) break;
      const payload = buf.subarray(i + 4, i + 2 + len);
      if (!jpegKeepsSegment(marker, payload)) found.push(`marcador JPEG ${jpegSegmentName(marker, payload)}`);
      i += 2 + len;
    }
  }

  if (format === 'isobmff') {
    found.push('contenedor AVIF/HEIC: no soportado por el limpiador, revisa a mano');
  }

  // Red de seguridad: firmas textuales de C2PA en cualquier formato.
  for (const needle of ['c2pa', 'jumbf', 'contentcredentials', 'urn:uuid:c2pa']) {
    if (buf.includes(Buffer.from(needle, 'latin1'))) found.push(`cadena "${needle}"`);
    else if (buf.includes(Buffer.from(needle.toUpperCase(), 'latin1'))) found.push(`cadena "${needle.toUpperCase()}"`);
  }

  return [...new Set(found)];
}
