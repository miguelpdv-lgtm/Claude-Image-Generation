// Cliente minimo para la API de imagenes de APIMart.
// Sin dependencias: usa fetch nativo de Node >= 20.
import fs from 'node:fs';
import path from 'node:path';
import { resolveModel } from './models.js';

const DEFAULT_BASE_URL = 'https://api.apimart.ai/v1';

export class ApimartError extends Error {
  constructor(message, { status, code, body } = {}) {
    super(message);
    this.name = 'ApimartError';
    this.status = status;
    this.code = code;
    this.body = body;
  }
}

// .env minimalista (evita dependencias). No sobrescribe variables ya definidas.
export function loadEnv(file = '.env') {
  const p = path.resolve(process.cwd(), file);
  if (!fs.existsSync(p)) return;
  for (const raw of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (value !== '' && process.env[key] === undefined) process.env[key] = value;
  }
}

const HTTP_HINTS = {
  400: 'Parametros invalidos (revisa model / size / resolution).',
  401: 'API key invalida o ausente.',
  402: 'Saldo insuficiente en la cuenta de APIMart.',
  403: 'Acceso denegado a ese modelo.',
  429: 'Rate limit alcanzado, reintenta mas tarde.',
  500: 'Error del servidor de APIMart.',
  502: 'Bad gateway en APIMart.',
  503: 'Servicio no disponible temporalmente.',
};

export class ApimartClient {
  constructor({
    apiKey = process.env.APIMART_API_KEY,
    baseUrl = process.env.APIMART_BASE_URL || DEFAULT_BASE_URL,
    timeoutMs = 120000,
  } = {}) {
    if (!apiKey) {
      throw new ApimartError('Falta APIMART_API_KEY. Ponla en el archivo .env (ver .env.example).');
    }
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.timeoutMs = timeoutMs;
  }

  async request(pathname, { method = 'GET', body } = {}) {
    const url = this.baseUrl + pathname;
    const res = await fetch(url, {
      method,
      headers: {
        Authorization: 'Bearer ' + this.apiKey,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    const text = await res.text();
    let json;
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      json = { raw: text };
    }

    if (!res.ok) {
      const msg = json?.error?.message || json?.message || json?.raw || res.statusText;
      const hint = HTTP_HINTS[res.status] ? ' ' + HTTP_HINTS[res.status] : '';
      throw new ApimartError(`HTTP ${res.status} en ${method} ${pathname}: ${msg}.${hint}`, {
        status: res.status,
        code: json?.error?.code ?? json?.code,
        body: json,
      });
    }
    // APIMart devuelve 200 HTTP con un "code" propio dentro del cuerpo.
    if (json?.code !== undefined && Number(json.code) !== 200) {
      throw new ApimartError(
        `APIMart code ${json.code}: ${json?.message || json?.error?.message || 'error desconocido'}`,
        { status: res.status, code: json.code, body: json },
      );
    }
    return json;
  }

  /** POST /images/generations -> devuelve { taskId } (procesamiento asincrono). */
  async createImageTask(opts) {
    const model = resolveModel(opts.model);
    const payload = { model: model.id, prompt: opts.prompt };

    const size = opts.size ?? model.defaults?.size;
    if (size) payload.size = size;

    const resolution = opts.resolution ?? model.defaults?.resolution;
    if (resolution) payload.resolution = resolution;

    payload.n = opts.n ?? 1;

    if (opts.imageUrls?.length) payload.image_urls = opts.imageUrls;
    if (opts.nsfwCheck !== undefined) payload.nsfw_check = opts.nsfwCheck;
    if (opts.watermark !== undefined && model.supports?.includes('watermark')) {
      payload.watermark = opts.watermark;
    }
    if (opts.officialFallback !== undefined && model.supports?.includes('official_fallback')) {
      payload.official_fallback = opts.officialFallback;
    }
    if (opts.extra) Object.assign(payload, opts.extra);

    const json = await this.request('/images/generations', { method: 'POST', body: payload });
    const entry = Array.isArray(json.data) ? json.data[0] : json.data;
    const taskId = entry?.task_id ?? entry?.id;

    // Por si algun modelo responde sincronamente al estilo OpenAI.
    if (!taskId) {
      const urls = extractImageUrls(json);
      if (urls.length) return { taskId: null, urls, raw: json };
      throw new ApimartError('La respuesta no trae task_id ni URLs de imagen.', { body: json });
    }
    return { taskId, urls: [], raw: json };
  }

  /** GET /tasks/{id} */
  async getTask(taskId) {
    const json = await this.request('/tasks/' + encodeURIComponent(taskId));
    return json.data ?? json;
  }

  /** Poll hasta completed / failed. */
  async waitForTask(taskId, { pollMs = 3000, timeoutMs = 600000, onProgress } = {}) {
    const deadline = Date.now() + timeoutMs;
    let last = -1;
    for (;;) {
      const task = await this.getTask(taskId);
      const status = String(task.status ?? '').toLowerCase();
      const progress = Number(task.progress ?? 0);
      if (onProgress && progress !== last) {
        onProgress({ status, progress, task });
        last = progress;
      }
      if (status === 'completed' || status === 'success' || status === 'succeeded') return task;
      if (status === 'failed' || status === 'cancelled' || status === 'canceled') {
        const err = task.error ?? {};
        throw new ApimartError(`Tarea ${taskId} ${status}: ${err.message || 'sin detalle'}`, {
          code: err.code,
          body: task,
        });
      }
      if (Date.now() > deadline) {
        throw new ApimartError(`Timeout esperando la tarea ${taskId} (ultimo estado: ${status}).`, {
          body: task,
        });
      }
      await new Promise((r) => setTimeout(r, pollMs));
    }
  }

  /** Flujo completo: crear tarea -> esperar -> devolver URLs. */
  async generateImage(opts) {
    const created = await this.createImageTask(opts);
    if (!created.taskId) return { taskId: null, urls: created.urls, task: null };
    const task = await this.waitForTask(created.taskId, opts);
    const urls = extractImageUrls(task);
    if (!urls.length) throw new ApimartError('La tarea termino sin URLs de imagen.', { body: task });
    return { taskId: created.taskId, urls, task };
  }
}

/** result.images[].url puede ser string o array de strings. */
export function extractImageUrls(payload) {
  const out = [];
  const push = (v) => {
    if (typeof v === 'string' && /^https?:\/\//.test(v)) out.push(v);
    else if (Array.isArray(v)) v.forEach(push);
  };
  const images = payload?.result?.images ?? payload?.data?.result?.images ?? payload?.data ?? [];
  for (const img of Array.isArray(images) ? images : [images]) {
    if (!img) continue;
    if (typeof img === 'string') push(img);
    else push(img.url ?? img.urls ?? img.image_url);
  }
  return [...new Set(out)];
}

export async function downloadImages(urls, { outDir = 'output', prefix = 'image' } = {}) {
  fs.mkdirSync(outDir, { recursive: true });
  const saved = [];
  for (const [i, url] of urls.entries()) {
    const res = await fetch(url);
    if (!res.ok) {
      throw new ApimartError(`No se pudo descargar ${url} (HTTP ${res.status}).`, { status: res.status });
    }
    const ext = (new URL(url).pathname.match(/\.(png|jpe?g|webp)$/i)?.[1] ?? 'png').toLowerCase();
    const file = path.join(outDir, `${prefix}_${String(i + 1).padStart(2, '0')}.${ext}`);
    fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
    saved.push(file);
  }
  return saved;
}

export function slugify(text, max = 40) {
  const s = (text || 'image')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, max);
  return s || 'image';
}
