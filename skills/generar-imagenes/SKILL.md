---
name: generar-imagenes
description: "Genera y edita imágenes con la API de APIMart (seedream, Nano Banana Pro, GPT-Image) a través del CLI del repo Claude-Image-Generation. Úsala siempre que se mencione generar, crear, hacer o diseñar una imagen, foto, ilustración, render, mockup o fondo; y también para editar una foto existente, cambiar el fondo, quitar el entorno, montar fotos de producto o de estudio, o probar variantes de un diseño. Dispara aunque no se nombre APIMart ni el repo; si lo que pide la persona es un archivo de imagen nuevo, esta skill es el camino. No la uses para diagramas, gráficas de datos ni capturas de pantalla."
---

# Generar y editar imágenes con APIMart

El trabajo pasa siempre por el CLI del repo `Claude-Image-Generation`. No escribas un cliente HTTP
nuevo: el CLI ya resuelve el polling asíncrono, la descarga y la limpieza de metadatos.

## Antes de la primera llamada

```bash
node src/cli.js --help      # o: npm run gen -- --help
node src/check.js           # verifica key y conexión, no gasta créditos
```

Si `check` dice que falta la key, la variable `APIMART_API_KEY` no está en el entorno. En sesiones
cloud se define en los ajustes del entorno de Claude Code; en local, en un `.env` que **nunca** se
commitea. Si el repo no está en la ruta actual, pregunta dónde está en vez de adivinar.

## Elegir modelo: es la decisión que más condiciona el resultado

| Quieres… | Modelo | Por qué |
| --- | --- | --- |
| Una imagen desde cero | `seedream-4-5` | Buena relación calidad/precio, ~0,026 USD |
| **Conservar un producto, persona o logo de una foto real** | `gemini-3-pro-image-preview` | Es un modelo de *edición*: respeta el sujeto y su texto. ~0,030 USD |
| Un borrador barato | `gemini-2.5-flash-image-preview` | ~0,0125 USD, pero destroza el texto pequeño |

La trampa que cuesta dinero: **seedream no edita, repinta el lienzo entero**. Si le pasas la foto de
un producto y le pides "cambia sólo el fondo", te devolverá el fondo nuevo y el producto redibujado,
con el texto de las etiquetas mal escrito. Para cualquier cosa que deba parecerse a algo real, usa
Nano Banana Pro (`gemini-3-pro-image-preview`).

Detalles de tamaños, resoluciones y límites por modelo: lee `references/modelos.md`.

## Generar desde cero

```bash
node src/cli.js "un zorro origami sobre musgo húmedo, luz suave" \
  --model seedream-4-5 --size 16:9 --resolution 2K --name zorro
```

## Editar conservando el sujeto

Pasa las fotos locales con `--ref-file` (acepta png/jpg/webp y las convierte a data URI; `--ref` es
sólo para URLs). **Pasa varias vistas del mismo objeto**: con una sola foto el modelo inventa los
lados que no ve, y ahí es donde deforma.

```bash
node src/cli.js "<prompt de edición>" \
  --model gemini-3-pro-image-preview --size 3:4 \
  --ref-file foto_frontal.jpg --ref-file foto_cenital.jpg --ref-file foto_lateral.jpg
```

Tres reglas que salieron de equivocarse mucho:

**Cuanto menos recompongas, más fiel sale.** Pedir "misma cámara, mismo encuadre, cambia sólo el
fondo" conserva la forma mucho mejor que pedir un encuadre nuevo ("ponlo en el tercio derecho,
formato banner"). Cada vez que el modelo tiene que recolocar el sujeto, lo redibuja. Si necesitas un
16:9 a partir de un 3:4, pídelo en dos pasos: primero la edición sin mover nada, después "amplía el
lienzo hacia la izquierda sin tocar el sujeto".

**Lo que no se ve en la referencia, se lo inventa.** Si la etiqueta está de espaldas en la foto, el
modelo dibujará una etiqueta plausible pero falsa, con otra tipografía. En esos encuadres dile
explícitamente que ahí no aparece ningún texto.

**Describe el texto letra por letra.** Transcribe en el prompt lo que debe poner, incluidos acentos y
eñes, y describe el logotipo por su forma ("cabeza de calabaza con rabito y collar de púas"), no por
su nombre. Aun así se le escapan caracteres: verifícalo.

## Verificar antes de entregar

A tamaño miniatura todo parece correcto; a tamaño real aparecen "PUMPKKIN", "HALLOWERN" o una eñe
perdida. Amplía siempre la zona de texto antes de dar una imagen por buena:

```bash
python3 scripts/verificar.py texto salida.jpg --caja 0.3,0.6,0.8,0.8
```

Para producto, el script también mide la proporción del sujeto frente a la foto original, que es la
forma objetiva de saber si lo ha estirado:

```bash
python3 scripts/verificar.py forma salida.jpg --referencia foto_real.jpg
```

Si una toma falla, repítela: hay varianza entre tiradas. Genera dos o tres candidatos de las
imágenes importantes y quédate con la mejor medida, en vez de pelearte con el prompt.

## Coste y buenas maneras

Cada imagen se cobra de verdad. Antes de lanzar una tanda de más de tres o cuatro, di cuánto va a
costar y espera confirmación. Una prueba suelta antes del lote entero evita pagar ocho veces un
prompt que no funcionaba.

## Lo que ya está resuelto, no lo repitas

- **Metadatos**: `downloadImages()` limpia C2PA/Exif/XMP al descargar. Verifica con
  `node src/strip.js --check <ruta>` si tienes dudas; no montes tu propia limpieza.
- **Asincronía**: el CLI hace el polling. No esperes la imagen en la respuesta del POST.
- **Las URLs de APIMart caducan en ~24 h.** Por eso el CLI descarga siempre; trabaja con los
  archivos locales.
- **`output/` está en `.gitignore`.** Si el resultado hay que conservarlo, muévelo a una carpeta
  versionada o avisa de que se perderá.
