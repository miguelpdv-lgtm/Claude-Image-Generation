# Modelos de imagen de APIMart

Verificado contra `GET /v1/models` y contra uso real. Para la lista viva del catálogo local:
`node src/cli.js --list-models`.

## Tabla de decisión

| Modelo | Para qué | size | resolution | n máx | refs máx | Coste aprox. |
| --- | --- | --- | --- | --- | --- | --- |
| `seedream-4-5` | Generar desde cero | 12 ratios comunes | 2K, 4K | 15 | 10 | $0.026 |
| `gemini-3-pro-image-preview` | **Editar conservando el sujeto** | libre | libre | 1 | 14 | $0.030 |
| `gpt-image-2` | Alternativa de edición | 16 ratios + píxeles | 1k/2k/4k | 1 | 15 | $0.014 |
| `gemini-2.5-flash-image-preview` | Borradores baratos | 11 ratios | 1K | 4 | 14 | $0.013 |
| `seedream-5-0-pro` | Cinematográfico, mejor texto | ratios comunes | 1K/1.5K/2K | 1 | 10 | — |

Alias aceptados: `seedream-4.5`, `nano-banana-pro`, `nano-banana`, `gpt-image`. El id real usa
guiones, no puntos (`seedream-4-5`).

## Comparativa medida en edición de foto de producto

Misma foto, mismo prompt, tres modelos:

| Modelo | Etiqueta del producto | Aspecto | Coste |
| --- | --- | --- | --- |
| `gemini-3-pro-image-preview` | correcta letra por letra | fotográfico, neutro | $0.030 |
| `gpt-image-2` | correcta | muy anaranjado, aire de render 3D | $0.014 |
| `gemini-2.5-flash-image-preview` | ilegible, logo cambiado | baja resolución | $0.013 |

## Suelo de fidelidad

Incluso con el mejor modelo y el prompt más restrictivo, la edición generativa **no clava la
geometría**. Midiendo la proporción ancho/alto de un producto frente a su foto real, a lo largo de
unas quince generaciones:

- Edición mínima sin recomponer: entre −0,3 % y −9 % de desviación.
- Pidiendo un encuadre nuevo: hasta −20 %.

No es un fallo del prompt, es varianza del modelo: tiradas idénticas dan resultados distintos. Si la
fidelidad tiene que ser exacta (catálogo, imprenta), genera varios candidatos y mide, o recorta el
sujeto real y móntalo sobre un fondo generado.

## Ratios que no existen

`seedream-4-5` **no acepta 4:5**: la petición no falla, devuelve un cuadrado 1:1 silenciosamente.
Los ratios válidos son `auto, 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3, 2:1, 1:2, 21:9, 9:21`. El CLI
valida esto antes de gastar créditos; si llamas al cliente directamente, valida tú.

## Errores de la API

| Código | Significado |
| --- | --- |
| 401 | Key inválida — revísala en https://apimart.ai/keys |
| 402 | Saldo insuficiente |
| 429 | Rate limit — espera y reintenta |

Para ver el cuerpo completo de la respuesta: `APIMART_DEBUG=1 node src/cli.js "..."`.
