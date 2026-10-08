# Skill: generar-imagenes

Fuente versionada de la skill. Está en `skills/` y no en `.claude/skills/` a propósito:
aquí se guarda y se revisa, pero no se activa sola al abrir el repo.

## Instalar

**Como skill personal** (disponible en todas tus sesiones): instálala desde el archivo
`generar-imagenes.skill` con el botón *Guardar skill*, o copia la carpeta:

```bash
cp -r skills/generar-imagenes ~/.claude/skills/
```

**Como skill de proyecto** (se activa sólo al trabajar en este repo, y la tiene cualquiera
que lo clone):

```bash
mkdir -p .claude/skills && cp -r skills/generar-imagenes .claude/skills/
```

## Qué contiene

| Archivo | Qué es |
| --- | --- |
| `SKILL.md` | Flujo de trabajo: elegir modelo, generar, editar conservando el sujeto, verificar |
| `references/modelos.md` | Tabla de modelos con tamaños, límites, costes y errores de la API |
| `scripts/verificar.py` | Control de calidad: amplía el texto para leerlo y mide si el sujeto salió deformado |

`verificar.py` en modo `forma` necesita `pip install rembg onnxruntime`; en modo `texto` sólo Pillow.
