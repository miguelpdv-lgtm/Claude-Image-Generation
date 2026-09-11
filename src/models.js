// Catalogo de modelos de imagen de APIMart.
// Todos usan el mismo endpoint: POST /v1/images/generations (asincrono -> task_id).
// Los IDs son los que expone GET /v1/models en la cuenta (verificado 2026-09-08).
// Docs: https://docs.apimart.ai/en/api-reference/images/<modelo>/generation
//
// sizes/resolutions === null  ->  sin validacion local, el parametro se envia tal cual.

const RATIOS_COMMON = ['auto', '1:1', '4:3', '3:4', '16:9', '9:16', '3:2', '2:3', '2:1', '1:2', '21:9', '9:21'];

const RATIOS_FULL = [
  'auto', '1:1', '3:2', '2:3', '4:3', '3:4', '5:4', '4:5',
  '16:9', '9:16', '2:1', '1:2', '3:1', '1:3', '21:9', '9:21',
];

export const MODELS = {
  'seedream-4-5': {
    id: 'seedream-4-5',
    label: 'Seedream 4.5 (ByteDance) - mejor relacion calidad/precio, buen texto',
    sizes: RATIOS_COMMON,
    resolutions: ['2K', '4K'],
    defaults: { size: '1:1', resolution: '2K' },
    maxN: 15,
    maxRefs: 10,
    supports: ['watermark', 'nsfw_check', 'sequential_image_generation', 'optimize_prompt_options'],
    aliases: ['seedream-4.5', 'seedream'],
    variants: ['seedream-4-0'],
  },
  'seedream-5-0-pro': {
    id: 'seedream-5-0-pro',
    label: 'Seedream 5.0 Pro - cinematografico, el mejor render de texto',
    sizes: RATIOS_COMMON,
    resolutions: ['1K', '1.5K', '2K'],
    defaults: { size: '1:1', resolution: '2K' },
    maxN: 1,
    maxRefs: 10,
    supports: ['watermark', 'nsfw_check'],
    aliases: ['seedream-5', 'seedream-5.0-pro', 'seedream-5-pro'],
    variants: ['seedream-5-0-lite'],
  },
  'gpt-image-2': {
    id: 'gpt-image-2',
    label: 'GPT-Image-2 (OpenAI) - maxima fidelidad al prompt',
    sizes: RATIOS_FULL,
    resolutions: ['1k', '2k', '4k'],
    defaults: { size: '1:1', resolution: '1k' },
    maxN: 1,
    maxRefs: 15,
    supports: ['nsfw_check', 'official_fallback'],
    aliases: ['gpt-image', 'gpt-image-2-ext'],
    variants: ['gpt-image-2-official', 'gpt-image-1.5', 'gpt-image-1', 'gpt-image-1-mini'],
  },
  'gemini-3-pro-image-preview': {
    id: 'gemini-3-pro-image-preview',
    label: 'Nano Banana Pro (Gemini 3 Pro Image) - razonamiento visual, texto nitido',
    sizes: null,
    resolutions: null,
    defaults: { size: '1:1', resolution: '2K' },
    maxN: 1,
    maxRefs: 14,
    supports: ['nsfw_check', 'official_fallback'],
    aliases: ['nano-banana-pro', 'nanobanana-pro'],
    variants: ['gemini-3-pro-image-preview-official', 'gemini-3.1-flash-image-preview'],
  },
  'gemini-2.5-flash-image-preview': {
    id: 'gemini-2.5-flash-image-preview',
    label: 'Nano Banana (Gemini 2.5 Flash Image) - rapido y barato, edicion multi-turno',
    sizes: ['auto', '1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'],
    resolutions: ['1K'],
    defaults: { size: '1:1', resolution: '1K' },
    maxN: 4,
    maxRefs: 14,
    supports: ['nsfw_check', 'official_fallback'],
    aliases: ['nano-banana', 'nanobanana', 'nano-banana-ext'],
    variants: ['gemini-2.5-flash-image-preview-official', 'gemini-3.1-flash-lite-image'],
  },
  'flux-2-pro': {
    id: 'flux-2-pro',
    label: 'FLUX 2 Pro (Black Forest Labs) - estilo fotografico y artistico',
    sizes: null,
    resolutions: null,
    defaults: {},
    maxN: 1,
    maxRefs: null,
    supports: ['nsfw_check'],
    aliases: ['flux', 'flux-2'],
    variants: ['flux-2-max', 'flux-2-flex', 'flux-kontext-pro', 'flux-kontext-max'],
  },
  'qwen-image-3.0': {
    id: 'qwen-image-3.0',
    label: 'Qwen Image 3.0 (Alibaba) - economico, buen chino/ingles',
    sizes: null,
    resolutions: ['1K', '2K'],
    defaults: { resolution: '2K' },
    maxN: 6,
    maxRefs: 3,
    supports: ['nsfw_check'],
    aliases: ['qwen-image', 'qwen'],
    variants: ['qwen-image-3.0-pro', 'qwen-image-2.0', 'qwen-image-2.0-pro'],
  },
  'z-image-turbo': {
    id: 'z-image-turbo',
    label: 'Z-Image Turbo - el mas rapido y barato, para iterar',
    sizes: null,
    resolutions: ['1K', '2K'],
    defaults: { resolution: '1K' },
    maxN: 1,
    maxRefs: null,
    supports: ['nsfw_check'],
  },
};

export const DEFAULT_MODEL = 'seedream-4-5';

export function resolveModel(name) {
  if (!name) return MODELS[DEFAULT_MODEL];
  const key = String(name).trim();
  if (MODELS[key]) return MODELS[key];
  const lower = key.toLowerCase();
  for (const m of Object.values(MODELS)) {
    if (m.id.toLowerCase() === lower) return m;
    // Alias amigable -> se traduce al id canonico que acepta la API.
    if (m.aliases?.some((a) => a.toLowerCase() === lower)) return m;
    // Variante: id real de la API que comparte limites, conserva su propio id.
    if (m.variants?.some((v) => v.toLowerCase() === lower)) return { ...m, id: key };
  }
  // Modelo no catalogado: se pasa tal cual, sin validaciones locales.
  return {
    id: key,
    label: '(no catalogado)',
    sizes: null,
    resolutions: null,
    defaults: {},
    maxN: null,
    maxRefs: null,
    supports: ['nsfw_check'],
  };
}
