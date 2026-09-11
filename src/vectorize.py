"""Convierte los stickers a vector y los escribe como PDF/AI para imprenta.

El arte original es raster (viene de un generador de imagenes), asi que esto es
un CALCO: se umbraliza la tinta, se extraen los contornos con OpenCV y se
escriben como trazados reales en el PDF. Las letras quedan como curvas, no como
texto vivo -- que es justo lo que pide una imprenta.

Salida por sticker:
  - fondo crema (trazado del arco) con 2 mm de sangrado
  - tinta negra en K100, relleno par-impar para que los huecos de las letras
    (O, P, R, A) queden calados
  - trazado de troquel en tinta plana 'CutContour', el estandar de die-cut
El .ai es el mismo archivo: Illustrator abre PDF de forma nativa.
"""

import cv2
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import CMYKColor, CMYKColorSep
import os
import shutil

SRC_DIR = 'stickers'
OUT_DIR = 'print'
NAMES = ['01_pumpkin_king', '02_lost_bride', '03_lonely_creature', '04_strange_man']

LABEL_W_MM = 62.0            # ancho final del sticker
BLEED_MM = 2.0
UPSCALE = 2                  # se calca al doble y se divide: menos escalonado
EPS_PX = 1.2                 # simplificacion de poligonos, en px del calco

MM2PT = 72.0 / 25.4
PAPER_CMYK = (0.00, 0.037, 0.111, 0.047)   # equivalente de #F3EAD8
CUT = CMYKColorSep(0, 1, 0, 0, spotName='CutContour', density=1)


def contours_of(mask, eps_px):
    """Contornos exteriores y huecos, simplificados, en coordenadas del lienzo."""
    big = cv2.resize(mask.astype(np.uint8) * 255, None, fx=UPSCALE, fy=UPSCALE,
                     interpolation=cv2.INTER_LINEAR)
    _, big = cv2.threshold(big, 128, 255, cv2.THRESH_BINARY)
    cs, _ = cv2.findContours(big, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        c = cv2.approxPolyDP(c, eps_px, True)
        if len(c) < 3:
            continue
        out.append(c.reshape(-1, 2).astype(np.float64) / UPSCALE)
    return out


def draw(c, polys, W, H, sx, sy, ox, oy, color, even_odd=True, stroke=False):
    """Vuelca poligonos del lienzo (y hacia abajo) al PDF (y hacia arriba)."""
    p = c.beginPath()
    for poly in polys:
        for i, (x, y) in enumerate(poly):
            X = ox + x * sx
            Y = oy + (H - y) * sy
            p.moveTo(X, Y) if i == 0 else p.lineTo(X, Y)
        p.close()
    if stroke:
        c.setStrokeColor(color)
        c.setLineWidth(0.25)
        c.drawPath(p, stroke=1, fill=0)
    else:
        c.setFillColor(color)
        try:
            from reportlab.pdfgen.canvas import FILL_EVEN_ODD
            c.drawPath(p, stroke=0, fill=1, fillMode=FILL_EVEN_ODD if even_odd else None)
        except ImportError:
            c.drawPath(p, stroke=0, fill=1)


def build(name):
    im = Image.open(os.path.join(SRC_DIR, f'{name}.png')).convert('RGBA')
    a = np.asarray(im)
    W, H = im.size
    label_h_mm = LABEL_W_MM * H / W

    shape = a[..., 3] > 128                                  # contorno del sticker
    ink = shape & (a[..., :3].mean(axis=2) < 140)            # tinta negra

    shape_polys = contours_of(shape, EPS_PX)
    ink_polys = contours_of(ink, EPS_PX)

    pw = (LABEL_W_MM + 2 * BLEED_MM) * MM2PT
    ph = (label_h_mm + 2 * BLEED_MM) * MM2PT
    c = rl_canvas.Canvas(os.path.join(OUT_DIR, f'{name}.pdf'), pagesize=(pw, ph))
    c.setTitle(f'LUMINNI {name} {LABEL_W_MM:.0f}x{label_h_mm:.1f}mm')

    sx = LABEL_W_MM * MM2PT / W
    sy = label_h_mm * MM2PT / H
    ox = BLEED_MM * MM2PT
    oy = BLEED_MM * MM2PT

    # Sangrado: el mismo contorno, escalado desde el centro para sobresalir 2 mm.
    kx = (LABEL_W_MM + 2 * BLEED_MM) / LABEL_W_MM
    ky = (label_h_mm + 2 * BLEED_MM) / label_h_mm
    bleed_polys = [np.column_stack([(p[:, 0] - W / 2) * kx + W / 2,
                                    (p[:, 1] - H / 2) * ky + H / 2]) for p in shape_polys]
    draw(c, bleed_polys, W, H, sx, sy, ox, oy, CMYKColor(*PAPER_CMYK))
    draw(c, ink_polys, W, H, sx, sy, ox, oy, CMYKColor(0, 0, 0, 1))
    draw(c, shape_polys, W, H, sx, sy, ox, oy, CUT, stroke=True)

    c.showPage()
    c.save()
    pdf = os.path.join(OUT_DIR, f'{name}.pdf')
    ai = os.path.join(OUT_DIR, f'{name}.ai')
    shutil.copyfile(pdf, ai)

    pts = sum(len(p) for p in ink_polys) + sum(len(p) for p in shape_polys)
    print(f'{name:22s} {LABEL_W_MM:.0f} x {label_h_mm:.1f} mm  '
          f'{len(ink_polys):4d} trazados de tinta, {pts:6d} nodos  '
          f'-> {os.path.getsize(ai)/1024:.0f} KB')
    return label_h_mm


# --------------------------------------------------------------- hoja A4
A4_MM = (210.0, 297.0)
GAP_MM = 12.0


def build_sheet():
    """Los cuatro en una A4, a tamano real, con sangrado y troquel vectorial."""
    from reportlab.pdfbase import pdfmetrics
    pw, ph = A4_MM[0] * MM2PT, A4_MM[1] * MM2PT
    c = rl_canvas.Canvas(os.path.join(OUT_DIR, 'hoja_stickers_A4.pdf'), pagesize=(pw, ph))
    c.setTitle('LUMINNI Halloween 2026 - hoja de 4 stickers')

    data = []
    for name in NAMES:
        im = Image.open(os.path.join(SRC_DIR, f'{name}.png')).convert('RGBA')
        a = np.asarray(im)
        W, H = im.size
        shape = a[..., 3] > 128
        ink = shape & (a[..., :3].mean(axis=2) < 140)
        data.append((name, W, H, contours_of(shape, EPS_PX), contours_of(ink, EPS_PX)))

    lh_mm = LABEL_W_MM * data[0][2] / data[0][1]
    cell_w = (LABEL_W_MM + 2 * BLEED_MM) * MM2PT
    cell_h = (lh_mm + 2 * BLEED_MM) * MM2PT
    block_w = 2 * cell_w + GAP_MM * MM2PT
    block_h = 2 * cell_h + GAP_MM * MM2PT
    x0 = (pw - block_w) / 2
    y0 = (ph - block_h) / 2 - 8 * MM2PT

    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.drawString(x0, ph - 26 * MM2PT, 'LUMINNI  \u00b7  HALLOWEEN 2026')
    c.setFont('Helvetica', 8.5)
    c.drawString(x0, ph - 32 * MM2PT,
                 f'4 stickers arqueados \u00b7 {LABEL_W_MM:.0f} \u00d7 {lh_mm:.1f} mm \u00b7 '
                 f'sangrado {BLEED_MM:.0f} mm \u00b7 troquel = tinta plana CutContour')
    c.drawString(x0, ph - 37 * MM2PT,
                 'Vectorial. Textos trazados a curvas. Crema CMYK 0/3.7/11.1/4.7 \u00b7 tinta K100.')

    for i, (name, W, H, shape_polys, ink_polys) in enumerate(data):
        cx = x0 + (i % 2) * (cell_w + GAP_MM * MM2PT)
        cy = y0 + (1 - i // 2) * (cell_h + GAP_MM * MM2PT)
        sx = LABEL_W_MM * MM2PT / W
        sy = lh_mm * MM2PT / H
        ox = cx + BLEED_MM * MM2PT
        oy = cy + BLEED_MM * MM2PT

        kx = (LABEL_W_MM + 2 * BLEED_MM) / LABEL_W_MM
        ky = (lh_mm + 2 * BLEED_MM) / lh_mm
        bleed = [np.column_stack([(p[:, 0] - W / 2) * kx + W / 2,
                                  (p[:, 1] - H / 2) * ky + H / 2]) for p in shape_polys]
        draw(c, bleed, W, H, sx, sy, ox, oy, CMYKColor(*PAPER_CMYK))
        draw(c, ink_polys, W, H, sx, sy, ox, oy, CMYKColor(0, 0, 0, 1))
        draw(c, shape_polys, W, H, sx, sy, ox, oy, CUT, stroke=True)

    # barra de control de escala
    bx, by = x0, 18 * MM2PT
    c.setStrokeColor(CMYKColor(0, 0, 0, 1))
    c.setLineWidth(1)
    c.line(bx, by, bx + 100 * MM2PT, by)
    for t in (0, 50, 100):
        c.line(bx + t * MM2PT, by - 2 * MM2PT, bx + t * MM2PT, by + 2 * MM2PT)
    c.setFont('Helvetica', 8)
    c.drawString(bx, by - 6 * MM2PT,
                 'Barra de control: 100 mm exactos. Imprimir al 100 %, sin ajustar a p\u00e1gina.')

    c.showPage()
    c.save()
    shutil.copyfile(os.path.join(OUT_DIR, 'hoja_stickers_A4.pdf'),
                    os.path.join(OUT_DIR, 'hoja_stickers_A4.ai'))
    print(f'hoja A4 vectorial -> {OUT_DIR}/hoja_stickers_A4.ai '
          f'({os.path.getsize(os.path.join(OUT_DIR, "hoja_stickers_A4.ai"))/1024:.0f} KB)')


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    for n in NAMES:
        build(n)
    build_sheet()
    print(f'\nsangrado {BLEED_MM} mm por lado, troquel en tinta plana CutContour')
    print(f'crema = CMYK {tuple(round(v*100,1) for v in PAPER_CMYK)}, tinta = K100')
