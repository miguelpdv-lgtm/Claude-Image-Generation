"""Version ovalada de los 4 stickers, al estilo de la etiqueta redonda de referencia.

A diferencia del arco, una elipse recorta las esquinas, asi que el tamano no lo
fija el ancho del titulo sino la elipse minima que contiene toda la tinta. Se
calcula para los cuatro disenos y se toma la mayor, de modo que los cuatro salen
con el MISMO contorno y la MISMA escala tipografica.
"""

from PIL import Image, ImageDraw
import numpy as np
import glob
import os
import json

OUT_DIR = 'stickers'
CANVAS_W = 3000
RATIO = 1.15                 # ancho / alto de la elipse
MARGIN = 0.11                # aire entre la tinta y el borde del ovalo
SS = 4                       # supersampling de la mascara

# Color de fondo unico para las cuatro etiquetas (los originales venian con
# cuatro cremas distintos y demasiado melocoton).
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


def extract_content(path):
    """Recorta el bloque de arte del diseno original y devuelve (imagen, alfa, bg).

    Se quitan marco y ornamentos de esquina; el alfa sirve para medir la tinta.
    """
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.float32)
    H, W, _ = a.shape
    bg = np.median(a[int(H * .45):int(H * .55), int(W * .13):int(W * .20)]
                   .reshape(-1, 3), axis=0)
    alpha = np.clip((bg.mean() - a.mean(axis=2)) / bg.mean(), 0, 1)

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

    ys, xs = np.where(alpha > 0.15)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return im.crop(box), alpha[box[1]:box[3], box[0]:box[2]], bg


def ellipse_fit(alpha, ratio):
    """Semieje menor de la elipse minima (aspecto `ratio`) que contiene la tinta.

    Devuelve b tal que la elipse a = ratio*b, b cubre todos los pixeles con tinta,
    medidos desde el centro del bloque.
    """
    ys, xs = np.where(alpha > 0.15)
    h, w = alpha.shape
    x = xs - (w - 1) / 2.0
    y = ys - (h - 1) / 2.0
    return float(np.sqrt((x / ratio) ** 2 + y ** 2).max())


def oval_mask(w, h):
    img = Image.new('L', (w * SS, h * SS), 0)
    ImageDraw.Draw(img).ellipse([0, 0, w * SS - 1, h * SS - 1], fill=255)
    return img.resize((w, h), Image.LANCZOS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob('*image_task_*.png'))
    assert len(files) == 4, f'esperaba 4 stickers, encontre {len(files)}'

    items = []
    for f in files:
        crop, alpha, bg = extract_content(f)
        items.append(dict(file=f, name=out_name(f), crop=crop, alpha=alpha, bg=bg,
                          b=ellipse_fit(alpha, RATIO)))

    # El diseno mas exigente fija la elipse comun.
    worst = max(items, key=lambda d: d['b'])
    b = worst['b'] * (1 + MARGIN)
    canvas_h_src = 2 * b
    scale = CANVAS_W / (2 * b * RATIO)
    CANVAS_H = int(round(canvas_h_src * scale))

    print(f'elipse fijada por {worst["name"]} (semieje {worst["b"]:.0f}px + {MARGIN:.0%})')
    print(f'lienzo {CANVAS_W}x{CANVAS_H}  (ratio {CANVAS_W/CANVAS_H:.3f})  escala {scale:.4f}')

    mask = oval_mask(CANVAS_W, CANVAS_H)
    report = {'canvas': [CANVAS_W, CANVAS_H], 'ratio': RATIO, 'shape': 'oval', 'items': []}

    for d in items:
        cw = int(round(d['crop'].width * scale))
        ch = int(round(d['crop'].height * scale))
        crop = d['crop'].resize((cw, ch), Image.LANCZOS)

        # Igualar el fondo al color comun: correccion multiplicativa por canal,
        # el crema pasa a PAPER y el negro sigue siendo negro.
        k = np.array(PAPER, np.float32) / np.maximum(d['bg'], 1)
        crop = Image.fromarray(np.clip(np.asarray(crop, np.float32) * k, 0, 255).astype(np.uint8))

        canvas = Image.new('RGB', (CANVAS_W, CANVAS_H), PAPER)
        canvas.paste(crop, ((CANVAS_W - cw) // 2, (CANVAS_H - ch) // 2))
        out = canvas.convert('RGBA')
        out.putalpha(mask)
        path = os.path.join(OUT_DIR, f'{d["name"]}.png')
        out.save(path)

        print(f'{d["name"]:22s} arte {cw}x{ch}px ({cw/CANVAS_W:.0%} x {ch/CANVAS_H:.0%} '
              f'del ovalo)  ->  {path}')
        report['items'].append({'name': d['name'], 'art_px': [cw, ch]})

    with open(os.path.join(OUT_DIR, 'build.json'), 'w') as fh:
        json.dump(report, fh, indent=2)


if __name__ == '__main__':
    main()
