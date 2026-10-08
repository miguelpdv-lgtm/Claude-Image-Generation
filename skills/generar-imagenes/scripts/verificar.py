#!/usr/bin/env python3
"""Control de calidad de imagenes generadas.

Dos comprobaciones que atrapan los fallos tipicos de la edicion generativa:

  texto  - amplia una zona para poder leer la letra pequena. A tamano miniatura
           una errata en una etiqueta es invisible; ampliada, salta a la vista.
  forma  - mide la proporcion ancho/alto del sujeto y la compara con la foto
           original, que es la forma objetiva de detectar que lo han estirado.

Uso:
  python3 verificar.py texto  salida.jpg --caja 0.3,0.6,0.8,0.8 [--destino zoom.png]
  python3 verificar.py forma  salida.jpg --referencia foto_real.jpg

'forma' necesita rembg (pip install rembg onnxruntime); 'texto' solo necesita Pillow.
"""
import argparse
import os
import sys


def recortar(ruta, caja, destino, escala):
    from PIL import Image
    im = Image.open(ruta).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = caja
    c = im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))
    if c.width == 0 or c.height == 0:
        sys.exit("La caja recorta un area vacia; revisa los valores.")
    c = c.resize((c.width * escala, c.height * escala), Image.LANCZOS)
    c.save(destino)
    print(f"{destino}  ({c.width}x{c.height})  — abrelo y lee el texto letra por letra")


def proporcion(ruta, caja, sesion):
    from PIL import Image
    from rembg import remove
    im = Image.open(ruta).convert("RGB")
    if caja:
        w, h = im.size
        x0, y0, x1, y1 = caja
        im = im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))
    bb = remove(im, session=sesion).getbbox()
    if not bb:
        return None, None
    ancho, alto = bb[2] - bb[0], bb[3] - bb[1]
    toca_borde = bb[0] == 0 or bb[1] == 0 or bb[2] == im.size[0] or bb[3] == im.size[1]
    return ancho / alto, toca_borde


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["texto", "forma"])
    ap.add_argument("imagen")
    ap.add_argument("--caja", help="x0,y0,x1,y1 en fracciones de 0 a 1 (ej: 0.3,0.6,0.8,0.8)")
    ap.add_argument("--referencia", help="foto real del sujeto, para el modo forma")
    ap.add_argument("--destino", default="zoom.png")
    ap.add_argument("--escala", type=int, default=3)
    a = ap.parse_args()

    if not os.path.exists(a.imagen):
        sys.exit(f"No existe: {a.imagen}")
    caja = tuple(float(v) for v in a.caja.split(",")) if a.caja else None

    if a.modo == "texto":
        if not caja:
            sys.exit("El modo texto necesita --caja; empieza por la zona de la etiqueta.")
        recortar(a.imagen, caja, a.destino, a.escala)
        return

    try:
        from rembg import new_session
    except ImportError:
        sys.exit("El modo forma necesita rembg:  pip install rembg onnxruntime")
    sesion = new_session("isnet-general-use")

    r_sal, borde_sal = proporcion(a.imagen, caja, sesion)
    if r_sal is None:
        sys.exit("No se pudo aislar el sujeto en la imagen generada.")
    print(f"generada    ancho/alto = {r_sal:.3f}")
    if borde_sal:
        print("  aviso: el recorte toca el borde del encuadre, la medida puede no ser del sujeto solo")

    if not a.referencia:
        return
    r_ref, _ = proporcion(a.referencia, None, sesion)
    if r_ref is None:
        sys.exit("No se pudo aislar el sujeto en la referencia.")
    desvio = 100 * (r_sal / r_ref - 1)
    print(f"referencia  ancho/alto = {r_ref:.3f}")
    print(f"desvio      {desvio:+.1f} %   {'aceptable' if abs(desvio) < 5 else 'REVISAR: el sujeto esta deformado'}")


if __name__ == "__main__":
    main()
