# APIMart — referencia de la API de imágenes

Resumen extraído de <https://docs.apimart.ai> (leído 2026-09-08).

- **Base URL:** `https://api.apimart.ai/v1`
- **Auth:** header `Authorization: Bearer <API_KEY>` — keys en <https://apimart.ai/keys>
- **Protocolo:** compatible con el formato OpenAI Images, pero **asíncrono**.

## Flujo

1. `POST /v1/images/generations` → `{ "code": 200, "data": [{ "status": "submitted", "task_id": "..." }] }`
2. Polling `GET /v1/tasks/{task_id}` hasta `status: "completed"`
3. Las URLs salen en `data.result.images[].url` (puede ser string o array). Caducan (`expires_at`, ~24 h).

## POST /v1/images/generations

| Campo | Tipo | Notas |
| --- | --- | --- |
| `model` | string | requerido |
| `prompt` | string | requerido |
| `n` | int | según modelo |
| `size` | string | aspect ratio (`1:1`, `16:9`, …), `auto`, o píxeles (`1881x836`) en gpt-image-2 |
| `resolution` | string | `1k` / `2k` / `4k` (case según modelo) |
| `image_urls` | array | referencias, URL http(s) o data URI base64 → image-to-image |
| `nsfw_check` | bool | moderación con `omni-moderation-latest`, default `false` |
| `official_fallback` | bool | fallback al canal oficial (gpt-image-2, nano-banana) |
| `watermark` | bool | seedream |
| `sequential_image_generation` | string | `disabled` / `auto` (seedream) |
| `optimize_prompt_options.mode` | string | `standard` / `fast` (seedream) |

## GET /v1/tasks/{task_id}

Estados: `pending`, `processing`, `completed`, `failed`, `cancelled`.

```json
{
  "code": 200,
  "data": {
    "id": "task_01KA040M0HP1GJWBJYZMKX1XS1",
    "status": "completed",
    "cost": 0.15,
    "credits_cost": 1.5,
    "progress": 100,
    "result": { "images": [{ "url": ["https://.../image.png"], "expires_at": 1763174708 }] },
    "created": 1763088289,
    "completed": 1763088308,
    "estimated_time": 60,
    "actual_time": 19
  }
}
```

## Modelos de imagen

IDs verificados contra `GET /v1/models` de la cuenta (2026-09-08). Ojo: el id real usa
guiones (`seedream-4-5`), no puntos.

| Modelo | size | resolution | n máx | refs máx |
| --- | --- | --- | --- | --- |
| `seedream-4-5` | 12 ratios comunes | 2K, 4K | 15 | 10 |
| `seedream-5-0-pro` | ratios comunes o píxeles | 1K, 1.5K, 2K | 1 | 10 |
| `gpt-image-2` | 16 ratios + píxeles | 1k, 2k, 4k | 1 | 15 |
| `gemini-3-pro-image-preview` (Nano Banana Pro) | libre | libre | 1 | 14 |
| `gemini-2.5-flash-image-preview` (Nano Banana) | 11 ratios | 1K | 4 | 14 |
| `flux-2-pro` | libre | libre | 1 | — |
| `qwen-image-3.0` | libre | 1K, 2K | 6 | 3 |
| `z-image-turbo` | libre | 1K, 2K | 1 | — |

La cuenta expone 45 modelos de imagen en total (`dall-e-3`, `midjourney`, `imagen-4.0-apimart`,
`grok-imagine-image`, `wan2.7-image`…). Cualquier id no catalogado se envía tal cual sin
validación local.

## Códigos de error

`400` parámetros inválidos · `401` auth · `402` saldo insuficiente · `403` acceso denegado ·
`429` rate limit · `500` / `502` / `503` servidor.

## Fuentes

- [GPT-Image-2 Image Generation](https://docs.apimart.ai/en/api-reference/images/gpt-image-2/generation)
- [Seedream-4.5 Image Generation](https://docs.apimart.ai/en/api-reference/images/seedream-4.5/generation)
- [Nano Banana Image Generation](https://docs.apimart.ai/en/api-reference/images/nano-banana/generation)
- [Get Task Status](https://apicore.mintlify.app/en/api-reference/tasks/status)
- [Quickstart](https://docs.apimart.ai/en/quickstart.md)
