# Entorno cloud (Claude Code)

Cómo dejar este repo funcionando en una sesión de Claude Code en la nube
(<https://claude.ai/code>), para pedir imágenes en lenguaje natural y que Claude ejecute el
CLI, itere los prompts y commitee los resultados.

## 1. Conectar el repo

En claude.ai/code, conecta la cuenta de GitHub y selecciona
`miguelpdv-lgtm/Claude-Image-Generation`. La sesión clona el repo en un contenedor Linux
efímero.

## 2. La API key como secreto

**No subas un `.env`.** En los ajustes del entorno de Claude Code, añade una variable:

| Nombre | Valor |
| --- | --- |
| `APIMART_API_KEY` | tu key de <https://apimart.ai/keys> (`sk-...`) |

Opcionales, sólo si quieres cambiar los defaults:

| Nombre | Default |
| --- | --- |
| `APIMART_BASE_URL` | `https://api.apimart.ai/v1` |
| `APIMART_MODEL` | `seedream-4.5` |
| `APIMART_OUTPUT_DIR` | `output` |

`loadEnv()` lee `.env` si existe pero **nunca pisa** una variable ya definida en el entorno,
así que la del entorno gana y el código funciona igual sin fichero.

Para copiar la key desde tu máquina sin que pase por el chat:

```powershell
Get-Content .env | Set-Clipboard
```

## 3. Salida de red

El sandbox de Claude Code filtra el tráfico saliente. Hay que permitir estos dominios o la
generación falla con un error de conexión, no de API:

- `api.apimart.ai` — crear la tarea y hacer polling
- el host de CDN desde el que APIMart sirve las imágenes terminadas (aparece en la URL que
  devuelve la tarea; si la descarga falla pero `npm run check` pasa, es esto)

## 4. Arrancar

```bash
bash scripts/setup.sh    # Node, hooks, API key, Python
npm run check            # conexión real con APIMart, sin gastar créditos
```

`setup.sh` reactiva `core.hooksPath`, que **no viaja en el clon** — sin ese paso el
pre-commit que bloquea imágenes con metadatos no se ejecuta.

Si vas a tocar los scripts de stickers, mockups o el pliego de impresión:

```bash
pip install -r requirements.txt
```

El CLI de generación no lo necesita.

## 5. Comprobar que todo encaja

```bash
npm run gen -- "un zorro origami sobre musgo, luz suave" --size 16:9 --resolution 2K
npm run strip -- --check output
```

La segunda orden debe decir `0 con metadatos`. Si dice lo contrario, la limpieza automática
de `downloadImages()` no se aplicó y hay que mirar por qué antes de seguir.

## Notas

- **`output/` está en `.gitignore`.** Las imágenes generadas en la sesión no se versionan
  solas; si quieres conservar alguna, muévela a `stickers/` o fuérzala con `git add -f`.
- **Generar cuesta dinero.** ~$0.026 por imagen 16:9 / 2K con `seedream-4.5`, y `--n 4`
  cobra cuatro veces. Las sesiones autónomas largas pueden acumular sin que lo veas.
- **El contenedor es efímero.** Lo que no se commitea se pierde al cerrar la sesión.
- **Las URLs de APIMart caducan (~24 h)**, así que no sirve guardar sólo el enlace.
