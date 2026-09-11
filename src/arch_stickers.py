"""Convierte los 4 stickers rectangulares con marco en stickers arqueados.

- Quita el marco y los ornamentos de esquina.
- Recorta el bloque de contenido y lo reescala con un factor COMUN a los 4,
  para que la tipografia mida exactamente igual en todos.
- Lo compone sobre un lienzo de proporcion identica (1.25 : 1, mas ancho que alto).
- Recorta con una mascara de arco de cupula elipticia (rise = 30% del ancho),
  mucho mas baja que el arco semicircular de la referencia.
- Exporta PNG con alfa (fuera del arco = transparente).
"""

from PIL import Image, ImageDraw
import numpy as np
import glob
import os
import json

OUT_DIR = 'stickers'
CANVAS_W = 3000
RATIO = 0.95                 # ancho / alto: como la etiqueta de la referencia (0.82),
                             # un punto menos alta. Antes 1.25 y 1.08, demasiado chatas.
CANVAS_H = int(round(CANVAS_W / RATIO))
RISE = 0.30                  # altura de la cupula, como fraccion del ancho
BOTTOM_R = 0.035             # radio de las esquinas inferiores, fraccion del ancho
SIDE_MARGIN = 0.10           # margen lateral minimo para el titulo mas ancho
BOTTOM_MARGIN = 0.130        # aire bajo la ultima linea (fraccion de la altura)
SS = 4                       # supersampling de la mascara

# Color de fondo unico para las cuatro etiquetas. Los originales venian con
# cuatro cremas distintos (#FCE4CD, #FAE2CE, #FCE2C8, #FBE3CC) y demasiado
# melocoton; este ivory calido es mas de papel y aguanta mejor sobre vidrio.
PAPER = (243, 234, 216)

NAMES = {
    '01M1WEZM6FY4DA5MTNSH215VHE': '01_pumpkin_king',
    '01M1WF04XX51F39KAV21K0ZT0V': '02_lost_bride',
    '01M1WF160ZG7WW4SNS5QBAJMV1': '03_lonely_creature',
    '01M1WF0K751RVMJ91R5J49WE34': '04_strange_man',
}


def out_name(path):
    for key, name in NAMES.items():
        if key in path:
            return name
    return os.path.splitext(os.path.basename(path))[0][:20]


def bg_color(a, H, W):
    """Color de fondo, tomado de una zona vacia del lateral izquierdo."""
    patch = a[int(H * 0.45):int(H * 0.55), int(W * 0.13):int(W * 0.20)]
    return np.median(patch.reshape(-1, 3), axis=0)


def ink_mask(a, bg, H, W):
    """Pixeles de tinta, excluyendo marco y ornamentos de esquina."""
    m = np.abs(a - bg).sum(axis=2) > 60
    m[:int(H * 0.055), :] = False
    m[int(H * 0.935):, :] = False
    m[:, :int(W * 0.055)] = False
    m[:, int(W * 0.945):] = False
    cw, ch = int(W * 0.17), int(H * 0.22)
    m[:ch, :cw] = False
    m[:ch, -cw:] = False
    m[-ch:, :cw] = False
    m[-ch:, -cw:] = False
    return m


def arch_mask(w, h):
    """Arco: lados rectos, cupula eliptica baja, esquinas inferiores redondeadas."""
    W4, H4 = w * SS, h * SS
    img = Image.new('L', (W4, H4), 0)
    d = ImageDraw.Draw(img)

    rise = RISE * W4
    br = BOTTOM_R * W4

    # Cuerpo recto entre la linea de arranque del arco y las esquinas inferiores.
    d.rectangle([0, rise, W4, H4 - br], fill=255)
    # Cupula eliptica, tangente a los lados verticales.
    d.ellipse([0, 0, W4, 2 * rise], fill=255)
    # Esquinas inferiores redondeadas.
    d.rectangle([br, H4 - br, W4 - br, H4], fill=255)
    d.pieslice([0, H4 - 2 * br, 2 * br, H4], 90, 180, fill=255)
    d.pieslice([W4 - 2 * br, H4 - 2 * br, W4, H4], 0, 90, fill=255)

    return img.resize((w, h), Image.LANCZOS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob('*image_task_*.png'))
    assert len(files) == 4, f'esperaba 4 stickers, encontre {len(files)}'

    # --- pasada 1: medir los cuatro -------------------------------------
    meas = []
    for f in files:
        im = Image.open(f).convert('RGB')
        a = np.asarray(im).astype(int)
        H, W, _ = a.shape
        bg = bg_color(a, H, W)
        m = ink_mask(a, bg, H, W)
        ys, xs = np.where(m)
        # Extension vertical medida en la columna central. Las lineas del marco
        # cubren casi toda la fila (frac ~1.0); el texto nunca pasa de ~0.25.
        cen = np.abs(a - bg).sum(axis=2)[:, int(W * 0.20):int(W * 0.80)] > 60
        frac = cen.mean(axis=1)
        rules = np.where(frac >= 0.60)[0]
        top_rules = rules[rules < H * 0.30]
        bot_rules = rules[rules > H * 0.70]
        rule_above = int(top_rules.max()) if top_rules.size else 0
        rule_below = int(bot_rules.min()) if bot_rules.size else H
        # El contenido real vive entre las dos lineas del marco.
        band = np.zeros(H, bool)
        band[rule_above + 8:rule_below - 8] = True
        rows = np.where((frac > 0.01) & band)[0]
        cy0, cy1 = int(rows.min()), int(rows.max())
        meas.append({
            'file': f, 'im': im, 'bg': bg, 'W': W, 'H': H,
            'x0': int(xs.min()), 'x1': int(xs.max()),
            'y0': cy0, 'y1': cy1,
            'lim_top': int(rule_above) + 6, 'lim_bot': int(rule_below) - 6,
        })

    # Rango vertical comun -> la tipografia queda alineada entre stickers.
    y0 = min(m['y0'] for m in meas)
    y1 = max(m['y1'] for m in meas)
    src_h = y1 - y0
    widest = max(m['x1'] - m['x0'] for m in meas)

    # Factor de escala unico: lo fija el titulo mas ancho.
    max_content_w = CANVAS_W * (1 - 2 * SIDE_MARGIN)
    scale = max_content_w / widest
    content_h = src_h * scale
    top = CANVAS_H * (1 - BOTTOM_MARGIN) - content_h

    print(f'lienzo {CANVAS_W}x{CANVAS_H} (ratio {RATIO})')
    print(f'contenido fuente: alto {src_h}px, mas ancho {widest}px, escala {scale:.4f}')
    print(f'contenido final: alto {content_h:.0f}px ({content_h/CANVAS_H:.1%} del lienzo), '
          f'top {top:.0f}px, fondo {CANVAS_H-top-content_h:.0f}px\n')

    mask = arch_mask(CANVAS_W, CANVAS_H)
    report = {'canvas': [CANVAS_W, CANVAS_H], 'ratio': RATIO, 'rise_frac_w': RISE, 'items': []}

    # --- pasada 2: componer ---------------------------------------------
    for mm in meas:
        name = out_name(mm['file'])
        pad = int(mm['W'] * 0.012)          # respiro alrededor del bloque de texto
        # El recorte nunca cruza las lineas del marco.
        top_px = max(y0 - pad, mm['lim_top'])
        bot_px = min(y1 + pad, mm['lim_bot'])
        box = (max(mm['x0'] - pad, 0), top_px,
               min(mm['x1'] + pad, mm['W']), bot_px)
        crop = mm['im'].crop(box)
        new_w = int(round(crop.width * scale))
        new_h = int(round(crop.height * scale))
        crop = crop.resize((new_w, new_h), Image.LANCZOS)

        # Igualar el fondo al color comun. Correccion multiplicativa por canal:
        # el crema pasa a PAPER y el negro sigue siendo negro.
        k = np.array(PAPER, np.float32) / np.maximum(mm['bg'].astype(np.float32), 1)
        arr = np.clip(np.asarray(crop, np.float32) * k, 0, 255).astype(np.uint8)
        crop = Image.fromarray(arr)

        canvas = Image.new('RGB', (CANVAS_W, CANVAS_H), PAPER)
        px = (CANVAS_W - new_w) // 2
        # El recorte puede haber empezado mas abajo por el recorte del marco:
        # se compensa para que la linea y0 comun caiga siempre en `top`.
        py = int(round(top - (y0 - top_px) * scale))
        canvas.paste(crop, (px, py))

        out = canvas.convert('RGBA')
        out.putalpha(mask)
        path = os.path.join(OUT_DIR, f'{name}.png')
        out.save(path)

        content_w = (mm['x1'] - mm['x0']) * scale
        print(f'{name:22s} fondo {tuple(mm["bg"].astype(int))} -> {PAPER}   '
              f'contenido {content_w:5.0f}px ({content_w/CANVAS_W:.1%})  ->  {path}')
        report['items'].append({'name': name, 'source': mm['file'],
                                'content_w_px': round(content_w)})

    with open(os.path.join(OUT_DIR, 'build.json'), 'w') as fh:
        json.dump(report, fh, indent=2)


if __name__ == '__main__':
    main()
