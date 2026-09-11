"""Version alterna: sticker transparente con motivos sueltos (estilo Bath & Body Works).

- El bloque central (LUMINNI + silueta + titulo) se reutiliza del diseno original,
  pero extraido con alfa: la tinta negra se conserva y el fondo crema desaparece.
- Los motivos se recortan de las laminas generadas por IA con etiquetado de
  componentes conexas, y se dispersan alrededor del bloque central sin solaparlo.
- Todo se imprime en un solo negro sobre film transparente: los motivos
  secundarios se rebajan a gris, no hacen falta tintas especiales.
"""

from PIL import Image
from scipy import ndimage
import numpy as np
import glob
import os
import json

OUT_DIR = 'stickers_clear'
CANVAS_W = 3000
RATIO = 1.10                       # 2.75" x 2.50"
CANVAS_H = int(round(CANVAS_W / RATIO))
CONTENT_W = 0.62                   # ancho del titulo mas largo, sobre el lienzo
CONTENT_TOP = 0.135                # borde superior del bloque central
SEED = 7

NAMES = {
    '01M1WEZM6FY4DA5MTNSH215VHE': ('01_pumpkin_king', 'm1_pumpkin'),
    '01M1WF04XX51F39KAV21K0ZT0V': ('02_lost_bride', 'm2_bride'),
    '01M1WF160ZG7WW4SNS5QBAJMV1': ('03_lonely_creature', 'm3_scissors'),
    '01M1WF0K751RVMJ91R5J49WE34': ('04_strange_man', 'm4_beetle'),
}

# Motivos a descartar, por indice tras la extraccion (ordenados por area):
# la lamina de la novia trajo una cinta que se lee como una letra "S", y la de
# Scissorhands un arbusto recortado que parece una oveja.
BLACKLIST = {'m2_bride': {1}, 'm3_scissors': {7}}

GRID_COLS, GRID_ROWS = 6, 6
N_MOTIFS = 20


# ---------------------------------------------------------------- motivos
def extract_motifs(path, min_frac=6e-4, gap=26):
    """Recorta los iconos de una lamina: negro sobre blanco -> RGBA con alfa.

    Un icono puede venir en varios trozos (patas, petalos, la tela de arana).
    En vez de fusionar cajas a pares -- cubico y lentisimo -- se dilata la
    mascara `gap` pixeles y se etiqueta eso: los trozos cercanos caen en la
    misma componente de una sola pasada.
    """
    g = np.asarray(Image.open(path).convert('L')).astype(np.float32)
    H, W = g.shape
    ink = g < 150
    grown = ndimage.binary_dilation(ink, ndimage.generate_binary_structure(2, 2),
                                    iterations=gap)
    lab, n = ndimage.label(grown)
    objs = ndimage.find_objects(lab)

    motifs = []
    for i, sl in enumerate(objs, start=1):
        ys, xs = sl
        y0, y1 = max(ys.start + gap, 0), min(ys.stop - gap, H)
        x0, x1 = max(xs.start + gap, 0), min(xs.stop - gap, W)
        if y1 - y0 < 12 or x1 - x0 < 12:
            continue
        if (y1 - y0) * (x1 - x0) < min_frac * H * W:
            continue
        if y0 < 6 or x0 < 6 or y1 > H - 6 or x1 > W - 6:
            continue
        sub = g[y0:y1, x0:x1]
        alpha = np.clip((245.0 - sub) / 245.0, 0, 1)     # antialiasing conservado
        if alpha.max() < 0.75:                           # descarta grises (el humo)
            continue
        if alpha.mean() < 0.06:
            continue
        rgba = np.zeros((*alpha.shape, 4), np.uint8)
        rgba[..., 3] = (alpha * 255).astype(np.uint8)
        motifs.append(Image.fromarray(rgba, 'RGBA'))
    motifs.sort(key=lambda m: -m.size[0] * m.size[1])
    return motifs


# ------------------------------------------------- bloque central con alfa
def extract_content(path):
    """Saca la tinta negra del diseno original dejando el crema transparente."""
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    H, W, _ = a.shape
    bg = np.median(a[int(H * .45):int(H * .55), int(W * .13):int(W * .20)]
                   .reshape(-1, 3), axis=0)
    lum = a.mean(axis=2)
    bg_l = bg.mean()
    alpha = np.clip((bg_l - lum) / bg_l, 0, 1)

    # Marco y ornamentos de esquina fuera.
    alpha[:int(H * .06), :] = 0
    alpha[int(H * .93):, :] = 0
    alpha[:, :int(W * .06)] = 0
    alpha[:, int(W * .94):] = 0
    cw, ch = int(W * .17), int(H * .22)
    for sy, sx in [(np.s_[:ch], np.s_[:cw]), (np.s_[:ch], np.s_[-cw:]),
                   (np.s_[-ch:], np.s_[:cw]), (np.s_[-ch:], np.s_[-cw:])]:
        alpha[sy, sx] = 0
    # Las lineas del marco cubren casi toda la fila; el texto nunca pasa de ~0.25.
    frac = (alpha[:, int(W * .20):int(W * .80)] > 0.25).mean(axis=1)
    alpha[frac >= 0.60, :] = 0

    ys, xs = np.where(alpha > 0.25)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA').crop(box)


# ------------------------------------------------------------- composicion
def scatter(canvas, occupancy, motifs, rng):
    """Reparte motivos por celdas de una rejilla, evitando el bloque central.

    Antes se sorteaba la posicion libremente y todo se apelotonaba abajo; con
    una celda por motivo la cobertura queda pareja en todo el lienzo.
    """
    W, H = canvas.size
    cw, ch = W / GRID_COLS, H / GRID_ROWS
    cells = [(c, r) for r in range(GRID_ROWS) for c in range(GRID_COLS)]
    rng.shuffle(cells)

    tiers = [(1.00, 255), (0.86, 255), (0.78, 132), (0.70, 132),
             (0.62, 76), (0.55, 76)]
    bag = []
    placed = 0
    for c, r in cells:
        if placed >= N_MOTIFS:
            break
        if not bag:                          # se agota la baraja antes de repetir
            bag = list(range(len(motifs)))
            rng.shuffle(bag)
        size_f, op = tiers[placed % len(tiers)]
        m = motifs[bag[-1]]

        s = size_f * min(cw, ch) * 0.82 * rng.uniform(0.9, 1.1)
        k = s / max(m.size)
        mw, mh = max(int(m.size[0] * k), 10), max(int(m.size[1] * k), 10)
        mi = m.resize((mw, mh), Image.LANCZOS).rotate(
            rng.uniform(-22, 22), expand=True, resample=Image.BICUBIC)
        mw, mh = mi.size

        ok = False
        for _ in range(12):                  # unos cuantos intentos dentro de la celda
            x = int(c * cw + rng.uniform(0, max(cw - mw, 1)))
            y = int(r * ch + rng.uniform(0, max(ch - mh, 1)))
            x = min(max(x, 4), W - mw - 4)
            y = min(max(y, 4), H - mh - 4)
            pad = int(0.012 * W)
            y0, y1 = max(y - pad, 0), min(y + mh + pad, H)
            x0, x1 = max(x - pad, 0), min(x + mw + pad, W)
            if not occupancy[y0:y1, x0:x1].any():
                ok = True
                break
        if not ok:
            continue

        al = np.asarray(mi)[..., 3].astype(np.float32) * (op / 255.0)
        buf = np.zeros((mh, mw, 4), np.uint8)
        buf[..., 3] = al.astype(np.uint8)
        canvas.alpha_composite(Image.fromarray(buf, 'RGBA'), (x, y))
        occupancy[y0:y1, x0:x1] = True
        bag.pop()
        placed += 1
    return placed


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob('*image_task_*.png'))
    contents = {}
    for f in files:
        key = next(k for k in NAMES if k in f)
        contents[key] = extract_content(f)

    widest = max(c.size[0] for c in contents.values())
    scale = CONTENT_W * CANVAS_W / widest
    print(f'lienzo {CANVAS_W}x{CANVAS_H} (ratio {RATIO})  escala del bloque {scale:.4f}')

    report = {'canvas': [CANVAS_W, CANVAS_H], 'ratio': RATIO, 'items': []}
    for key, (name, sheet) in NAMES.items():
        content = contents[key]
        cw = int(round(content.size[0] * scale))
        chh = int(round(content.size[1] * scale))
        content = content.resize((cw, chh), Image.LANCZOS)

        canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        px = (CANVAS_W - cw) // 2
        py = int(round(CANVAS_H * CONTENT_TOP))
        canvas.alpha_composite(content, (px, py))

        occupancy = np.zeros((CANVAS_H, CANVAS_W), bool)
        pad = int(0.035 * CANVAS_W)
        occupancy[max(py - pad, 0):min(py + chh + pad, CANVAS_H),
                  max(px - pad, 0):min(px + cw + pad, CANVAS_W)] = True

        motifs = extract_motifs(f'work/motifs/{sheet}_01.jpg')
        drop = BLACKLIST.get(sheet, set())
        motifs = [m for i, m in enumerate(motifs) if i not in drop]
        rng = np.random.default_rng(SEED)
        n = scatter(canvas, occupancy, motifs, rng)

        path = os.path.join(OUT_DIR, f'{name}.png')
        canvas.save(path)
        cover = (np.asarray(canvas)[..., 3] > 20).mean()
        print(f'{name:22s} {len(motifs):2d} motivos disponibles, {n} colocados, '
              f'tinta {cover:.1%} del area  ->  {path}')
        report['items'].append({'name': name, 'motifs_placed': n,
                                'ink_coverage': round(float(cover), 4)})

    with open(os.path.join(OUT_DIR, 'build.json'), 'w') as fh:
        json.dump(report, fh, indent=2)


if __name__ == '__main__':
    main()
