"""Hoja de impresion A4 con los 4 stickers ovalados a tamano real.

Cada sticker lleva 2 mm de sangrado (el crema se extiende mas alla del corte)
y una linea de corte punteada en el contorno exacto del ovalo. La barra de
100 mm sirve para comprobar que la impresora no reescalo la pagina.
"""

from PIL import Image, ImageDraw, ImageFont
import os

DPI = 300
MM = DPI / 25.4                      # pixeles por milimetro
A4 = (int(round(210 * MM)), int(round(297 * MM)))

LABEL_W_MM, LABEL_H_MM = 60.0, 52.0  # tamano final del sticker
BLEED_MM = 2.0
GAP_MM = 14.0
PAPER = (243, 234, 216)

FILES = [('01_pumpkin_king.png', 'THE PUMPKIN KING', '01 / 04'),
         ('02_lost_bride.png', 'THE LOST BRIDE', '02 / 04'),
         ('03_lonely_creature.png', 'THE LONELY CREATURE', '03 / 04'),
         ('04_strange_man.png', 'THE STRANGE MAN', '04 / 04')]


def font(size, bold=False):
    for name in (['arialbd.ttf', 'segoeuib.ttf'] if bold else ['arial.ttf', 'segoeui.ttf']):
        try:
            return ImageFont.truetype(f'C:/Windows/Fonts/{name}', size)
        except OSError:
            continue
    return ImageFont.load_default()


def dashed_ellipse(d, box, dash=14, gap=10, fill=(178, 178, 178), width=2):
    """Contorno punteado, dibujado como arcos cortos."""
    import math
    x0, y0, x1, y1 = box
    a, b = (x1 - x0) / 2, (y1 - y0) / 2
    per = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
    n = max(int(per / (dash + gap)), 8)
    step = 360.0 / n
    on = 360.0 / n * dash / (dash + gap)
    for i in range(n):
        s = i * step
        d.arc(box, s, s + on, fill=fill, width=width)


def main():
    sheet = Image.new('RGB', A4, (255, 255, 255))
    d = ImageDraw.Draw(sheet)

    lw, lh = int(round(LABEL_W_MM * MM)), int(round(LABEL_H_MM * MM))
    bw = int(round((LABEL_W_MM + 2 * BLEED_MM) * MM))
    bh = int(round((LABEL_H_MM + 2 * BLEED_MM) * MM))
    gap = int(round(GAP_MM * MM))

    block_w = 2 * bw + gap
    block_h = 2 * bh + gap + int(round(10 * MM))     # sitio para el pie de cada uno
    ox = (A4[0] - block_w) // 2
    oy = int(round(84 * MM))   # bloque centrado entre cabecera y barra de control

    # --- cabecera ------------------------------------------------------
    d.text((ox, int(28 * MM)), 'LUMINNI  ·  HALLOWEEN 2026', font=font(46, True), fill=(20, 20, 20))
    d.text((ox, int(38 * MM)),
           f'4 stickers ovalados · {LABEL_W_MM:.0f} × {LABEL_H_MM:.0f} mm '
           f'({LABEL_W_MM/25.4:.2f}" × {LABEL_H_MM/25.4:.2f}") · sangrado {BLEED_MM:.0f} mm · '
           f'troquel = linea punteada',
           font=font(30), fill=(90, 90, 90))
    d.text((ox, int(45 * MM)), 'Imprimir al 100 %, sin ajustar a pagina.',
           font=font(30), fill=(90, 90, 90))

    # --- los cuatro ----------------------------------------------------
    for i, (fn, title, num) in enumerate(FILES):
        st = Image.open(os.path.join('stickers', fn)).convert('RGBA').resize((lw, lh), Image.LANCZOS)
        cx = ox + (i % 2) * (bw + gap)
        cy = oy + (i // 2) * (bh + gap + int(round(10 * MM)))

        # sangrado: el mismo crema, 2 mm mas grande en todo el contorno
        bleed = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        ImageDraw.Draw(bleed).ellipse([0, 0, bw - 1, bh - 1], fill=PAPER + (255,))
        sheet.paste(bleed, (cx, cy), bleed)
        sheet.paste(st, (cx + (bw - lw) // 2, cy + (bh - lh) // 2), st)

        box = [cx + (bw - lw) // 2, cy + (bh - lh) // 2,
               cx + (bw - lw) // 2 + lw - 1, cy + (bh - lh) // 2 + lh - 1]
        dashed_ellipse(d, box)

        cap = f'{num}   {title}'
        w = d.textlength(cap, font=font(26))
        d.text((cx + (bw - w) / 2, cy + bh + int(2.5 * MM)), cap,
               font=font(26), fill=(120, 120, 120))

    # --- barra de control de escala ------------------------------------
    by = A4[1] - int(24 * MM)
    bx = ox
    d.line([(bx, by), (bx + int(100 * MM), by)], fill=(20, 20, 20), width=3)
    for t in (0, 50, 100):
        x = bx + int(t * MM)
        d.line([(x, by - int(2 * MM)), (x, by + int(2 * MM))], fill=(20, 20, 20), width=3)
    d.text((bx, by + int(3.5 * MM)),
           'Barra de control: debe medir exactamente 100 mm impresa.',
           font=font(26), fill=(90, 90, 90))

    os.makedirs('output', exist_ok=True)
    png = 'output/hoja_stickers_A4.png'
    sheet.save(png, dpi=(DPI, DPI))
    sheet.save('output/hoja_stickers_A4.pdf', resolution=DPI)
    print(f'{png}  {sheet.size[0]}x{sheet.size[1]} px @ {DPI} dpi  (A4 210x297 mm)')
    print(f'  sticker {LABEL_W_MM}x{LABEL_H_MM} mm = {lw}x{lh} px, con sangrado {bw}x{bh} px')


if __name__ == '__main__':
    main()
