"""Monta stickers sobre 4 frascos identicos. Varias escenas, un solo motor.

Metodo:
1. Se modela el fondo del render base B(x,y) (rampa horizontal por fila entre
   las franjas laterales limpias) y se trabaja con la diferencia  d = img - B.
   Sobre fondo casi negro la version multiplicativa (img/B) se dispara, porque
   B vale 3-25; la aditiva es estable y conserva reflejo y luces del vidrio.
2. El frasco se escala en horizontal hasta que el vidrio mide exactamente
   2.75 : 3.34 (las medidas reales del frasco).
3. Cada sticker se deforma como si estuviera pegado a un cilindro: la anchura
   se proyecta con x = R*sin(phi), se anade el pandeo vertical que produce la
   camara ligeramente elevada, y un sombreado lambertiano suave.
4. Se suma la diferencia sobre un fondo oscuro limpio, cuatro veces.

Modos de sticker:
  'opaque' -> papel: sustituye lo que hay detras y proyecta sombra de canto.
  'clear'  -> film transparente: solo la tinta se mezcla sobre la cera.
"""

from PIL import Image, ImageFilter
import numpy as np
import os

# --- medidas reales del frasco ----------------------------------------
JAR_D_IN = 2.75       # diametro exterior del vidrio
JAR_H_IN = 3.34       # altura del vidrio

INK_DIFF = 10.0       # nivel de la tinta negra en el espacio de diferencia

SCENES = [
    dict(name='mockup_4_frascos',
         base='work/jar_dark_01.jpg',
         stickers='stickers',
         mode='opaque',
         glass=dict(x0=648, x1=1396, y0=619, y1=1507),
         # flecha medida en el borde del vidrio: 21.5 px sobre 748 de ancho
         top_y=300, bot_y=1960, ellipse_half=21.5,
         # arco, un poco mas grande que la version ovalada (60 x 52 mm)
         label_w=2.44, label_h=2.57, label_top=0.40),
    dict(name='mockup_4_frascos_transparente',
         base='work/jar_dark_01.jpg',
         stickers='stickers_clear',
         mode='clear',
         glass=dict(x0=648, x1=1396, y0=619, y1=1507),
         top_y=300, bot_y=1960, ellipse_half=36.0,
         label_w=2.42, label_h=2.20, label_top=0.90),
    dict(name='mockup_4_frascos_tapa_6oz',
         base='work/jar_lid2_01.jpg',
         stickers='stickers_clear',
         mode='clear',
         glass=dict(x0=558, x1=1495, y0=422, y1=1605),
         top_y=200, bot_y=1900, ellipse_half=44.0,
         label_w=2.42, label_h=2.20, label_top=0.90),
    # Etiqueta rematando en la linea de 4 oz: encima queda la cera batida
    # hasta las 6 oz y la tapa. Al fijar el borde superior en 1.63" y tener
    # que dejar el vidrio de la base libre, el alto maximo cae a 1.45".
    dict(name='mockup_4_frascos_tapa_4oz',
         base='work/jar_lid2_01.jpg',
         stickers='stickers',
         mode='opaque',
         glass=dict(x0=558, x1=1495, y0=422, y1=1605),
         top_y=200, bot_y=1900, ellipse_half=28.0,
         label_w=1.57, label_h=1.45, label_top=1.63),
]

FILES = ['01_pumpkin_king.png', '02_lost_bride.png',
         '03_lonely_creature.png', '04_strange_man.png']


def background_model(a):
    """Rampa horizontal por fila entre las franjas laterales limpias."""
    H, W, _ = a.shape
    left = a[:, 10:200, :].mean(axis=1)
    right = a[:, W - 200:W - 10, :].mean(axis=1)
    # Suavizado vertical, para que el ruido del JPEG no entre en el modelo.
    k = 61
    pad = lambda v: np.pad(v, ((k // 2, k // 2), (0, 0)), mode='edge')
    box = lambda v: np.stack([np.convolve(pad(v)[:, c], np.ones(k) / k, 'valid')
                              for c in range(3)], axis=1)
    left, right = box(left), box(right)
    t = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
    return left[:, None, :] * (1 - t) + right[:, None, :] * t


def measure_lighting(a, gx0, gx1, y0, y1):
    """Ajusta la iluminacion del propio frasco: I(phi) = k + b*max(cos(phi-phiL), 0).

    Sin esto hay que adivinar de donde viene la luz, y adivinar mal es justo lo
    que hace que la etiqueta parezca pegada encima: en este render la clave
    entra por la DERECHA (la cera pasa de 0.32 a 1.31 de izquierda a derecha).
    """
    lum = a.mean(axis=2)[y0:y1].mean(axis=0)
    cx, R = (gx0 + gx1) / 2, (gx1 - gx0) / 2
    xs = np.arange(int(gx0 + 0.06 * 2 * R), int(gx1 - 0.06 * 2 * R))
    phi = np.arcsin(np.clip((xs - cx) / R, -1, 1))
    y = lum[xs]

    best = None
    for phiL in np.linspace(-1.3, 1.3, 261):
        c = np.maximum(np.cos(phi - phiL), 0)
        A = np.vstack([np.ones_like(c), c]).T
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        r = float(((A @ coef - y) ** 2).sum())
        if best is None or r < best[0]:
            best = (r, phiL, coef)
    _, phiL, (k, b) = best
    return float(phiL), float(k), float(b)


def cylinder_warp(sticker, out_w, out_h, theta, sag, light, damp=0.62, hi=1.12):
    """Proyecta el sticker plano sobre un cilindro visto de frente.

    theta: angulo total que abarca la etiqueta (rad).
    sag:   desplazamiento vertical de los bordes respecto al centro (px).
    light: (phiL, k, b) medidos en el frasco.
    damp:  el papel es opaco y no difunde como la cera, asi que se acerca su
           contraste hacia 1; hi limita el lado iluminado para no quemar el ivory.
    """
    src = np.asarray(sticker.convert('RGBA')).astype(np.float32)
    sh, sw = src.shape[:2]

    j = np.arange(out_w, dtype=np.float32)
    xn = (j - (out_w - 1) / 2) / ((out_w - 1) / 2)          # -1 .. 1
    half = theta / 2
    phi = np.arcsin(np.clip(xn * np.sin(half), -1, 1))       # angulo sobre el cilindro
    u = (phi / theta + 0.5) * (sw - 1)                       # columna en el original
    dy = sag * (1 - np.cos(phi))                             # bordes mas altos que el centro

    i = np.arange(out_h, dtype=np.float32)
    v = (i / (out_h - 1)) * (sh - 1)

    # El signo importa: la camara mira algo desde arriba, asi que una linea
    # horizontal pegada al frasco se ve con el centro MAS BAJO que los lados
    # (igual que el borde del vidrio). Restar dy la curvaba al reves y por eso
    # la etiqueta parecia sobrepuesta.
    U = np.clip(np.broadcast_to(u, (out_h, out_w)), 0, sw - 1.001)
    V = np.clip(v[:, None] + dy[None, :] * (sh - 1) / out_h, 0, sh - 1.001)

    x0 = np.floor(U).astype(int); x1 = x0 + 1
    y0 = np.floor(V).astype(int); y1 = y0 + 1
    ax = (U - x0)[..., None]; ay = (V - y0)[..., None]
    out = (src[y0, x0] * (1 - ax) * (1 - ay) + src[y0, x1] * ax * (1 - ay) +
           src[y1, x0] * (1 - ax) * ay + src[y1, x1] * ax * ay)

    # Sombreado con la luz medida en el frasco, normalizado a 1 en el centro.
    phiL, k, b = light
    I = k + b * np.maximum(np.cos(phi - phiL), 0)
    I0 = k + b * max(np.cos(phiL), 0)
    shade = 1.0 + (I / I0 - 1.0) * damp
    shade *= 1.0 - 0.13 * np.abs(xn) ** 5      # el canto ya gira fuera de vista
    shade = np.clip(shade, 0.05, hi)
    out[..., :3] *= shade[None, :, None]
    return out


def edge_shadow(alpha, pad, blur=14, dx=-6, dy=7):
    """Sombra que proyecta el canto del papel sobre el vidrio."""
    h, w = alpha.shape[:2]
    big = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    big[pad:pad + h, pad:pad + w] = alpha[..., 0]
    im = Image.fromarray((big * 255).astype(np.uint8), 'L')
    im = im.filter(ImageFilter.GaussianBlur(blur))
    sh = np.asarray(im).astype(np.float32) / 255.0
    sh = np.roll(np.roll(sh, dy, axis=0), dx, axis=1)
    return np.clip(sh - big, 0, 1)          # solo lo que sobresale del sticker


def resize_x(arr, new_w):
    """Reescala solo en horizontal, canal a canal y en float.

    El cast a float32 es obligatorio: el modo 'F' de PIL es float32, y pasarle
    un array float64 reinterpreta los bytes y devuelve NaN.
    """
    arr = arr.astype(np.float32, copy=False)
    H = arr.shape[0]
    return np.stack([
        np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., c]), 'F')
                   .resize((new_w, H), Image.LANCZOS))
        for c in range(arr.shape[2])
    ], axis=2)


def build(cfg):
    a = np.asarray(Image.open(cfg['base']).convert('RGB')).astype(np.float32)
    H, W, _ = a.shape
    diff = a - background_model(a)

    G = cfg['glass']
    gw, gh = G['x1'] - G['x0'], G['y1'] - G['y0']
    stretch = (JAR_D_IN / JAR_H_IN) / (gw / gh)
    new_W = int(round(W * stretch))
    diff = resize_x(diff, new_W)

    gx0, gx1 = G['x0'] * stretch, G['x1'] * stretch
    gy0, gy1 = G['y0'], G['y1']
    glass_w, glass_h = gx1 - gx0, gy1 - gy0
    ppi = glass_w / JAR_D_IN

    print(f"\n=== {cfg['name']} ({cfg['mode']}) ===")
    print(f'  vidrio base {gw}x{gh} (ratio {gw/gh:.4f}) -> factor horizontal {stretch:.4f}')
    print(f'  vidrio corregido {glass_w:.0f}x{glass_h:.0f} (ratio {glass_w/glass_h:.4f}), '
          f'{ppi:.1f} px/pulgada')

    # --- geometria de la etiqueta sobre el cilindro --------------------
    R = JAR_D_IN / 2
    theta = cfg['label_w'] / R
    chord = 2 * R * np.sin(theta / 2)
    lab_w, lab_h = int(round(chord * ppi)), int(round(cfg['label_h'] * ppi))
    lab_top = gy0 + cfg['label_top'] * ppi
    lab_x = (gx0 + gx1) / 2 - lab_w / 2
    bot = JAR_H_IN - cfg['label_top'] - cfg['label_h']
    print(f"  etiqueta {cfg['label_w']}x{cfg['label_h']}\" -> envuelve {np.degrees(theta):.1f} grados, "
          f'proyectada {chord:.2f}" = {chord/JAR_D_IN:.0%} del ancho, '
          f"{cfg['label_h']/JAR_H_IN:.0%} del alto")
    print(f"  margenes en el vidrio: {cfg['label_top']:.2f}\" arriba, {bot:.2f}\" abajo")

    light = measure_lighting(a, G['x0'], G['x1'],
                             int(gy0 + cfg['label_top'] * (gh / JAR_H_IN)),
                             int(gy0 + (cfg['label_top'] + cfg['label_h']) * (gh / JAR_H_IN)))
    print(f'  luz del frasco: phi_L = {np.degrees(light[0]):+.1f} grados '
          f'({"derecha" if light[0] > 0 else "izquierda"}), k={light[1]:.1f}, b={light[2]:.1f}')

    # --- ventana del frasco --------------------------------------------
    side = 0.16
    src_x0 = max(int(round(gx0 - glass_w * side)), 0)
    src_x1 = min(int(round(gx1 + glass_w * side)), new_W)
    src_y0, src_y1 = max(cfg['top_y'], 0), min(cfg['bot_y'], H)
    tile = diff[src_y0:src_y1, src_x0:src_x1]
    th, tw = tile.shape[:2]
    left_of_glass = gx0 - src_x0

    # --- lienzo --------------------------------------------------------
    pitch = glass_w * 1.24
    margin = left_of_glass + glass_w * 0.16
    cw = int(round(margin * 2 + 3 * pitch + glass_w))
    pad_top = 0.30
    jar_top = (gy0 - src_y0) + glass_h * pad_top
    ch = int(round(jar_top + (src_y1 - src_y0) - (gy0 - src_y0) + glass_h * 0.10))

    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    horizon = jar_top + glass_h
    ny = (yy - horizon) / glass_h
    nx = (xx / cw - 0.5) * 2
    mix = np.clip(ny * 2.2 + 0.5, 0, 1)[..., None]
    canvas = (np.array([19., 18., 21.], np.float32) * (1 - mix) +
              np.array([11., 11., 13.], np.float32) * mix)
    halo = np.exp(-(nx ** 2) / 0.55) * np.exp(-((yy / ch - 0.42) ** 2) / 0.20)
    canvas = canvas + halo[..., None] * np.array([13., 12., 14.], np.float32)
    canvas = np.clip(canvas - (nx ** 2)[..., None] * 4.0, 0, 255)

    # --- pegar los stickers sobre la diferencia -------------------------
    for k, fn in enumerate(FILES):
        t = tile.copy()
        warped = cylinder_warp(Image.open(os.path.join(cfg['stickers'], fn)),
                               lab_w, lab_h, theta, cfg['ellipse_half'], light)
        alpha = warped[..., 3:4] / 255.0
        px, py = int(round(lab_x - src_x0)), int(round(lab_top - src_y0))
        region = t[py:py + lab_h, px:px + lab_w]

        if cfg['mode'] == 'opaque':
            P = 46
            sh = edge_shadow(alpha, P)
            t[py - P:py - P + sh.shape[0], px - P:px - P + sh.shape[1]] -= sh[..., None] * 26.0
            region = t[py:py + lab_h, px:px + lab_w]
            paper = warped[..., :3] - 12.0
            t[py:py + lab_h, px:px + lab_w] = region * (1 - alpha) + paper * alpha
        else:
            # Film transparente: solo la tinta se mezcla sobre lo que hay detras.
            t[py:py + lab_h, px:px + lab_w] = region * (1 - alpha) + INK_DIFF * alpha

        ox = int(round(margin + k * pitch - left_of_glass))
        oy = int(round(jar_top - (gy0 - src_y0)))
        assert ox >= 0 and oy >= 0, 'el mosaico se saldria del lienzo'
        w, h = min(tw, cw - ox), min(th, ch - oy)
        f = np.ones((h, w), np.float32)
        r = 60
        ramp = np.linspace(0, 1, r, dtype=np.float32)
        f[:, :r] *= ramp[None, :]; f[:, -r:] *= ramp[::-1][None, :]
        f[:r, :] *= ramp[:, None]; f[-r:, :] *= ramp[::-1][:, None]
        canvas[oy:oy + h, ox:ox + w] += t[:h, :w] * f[..., None]

    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    path = f"output/{cfg['name']}.jpg"
    out.save(path, quality=95, subsampling=0)
    print(f'  -> {path}  {out.size[0]}x{out.size[1]}')


if __name__ == '__main__':
    os.makedirs('output', exist_ok=True)
    for cfg in SCENES:
        build(cfg)
