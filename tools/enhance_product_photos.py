"""
Mejora las fotos de producto de la tienda (gratis, sin IA de pago):
nitidez suave, contraste/color mas ricos y una sombra de apoyo bajo
el frasco, manteniendo el fondo recortado (transparente).

Uso:
  SHOPIFY_ADMIN_TOKEN=shpat_... python3 tools/enhance_product_photos.py

Requiere un token de Admin API con permisos de lectura/escritura de
productos (mismo token usado por el resto del pipeline de la tienda).
Para cada producto activo:
  1. Descarga la foto original (no la ya recortada).
  2. Aplica nitidez/contraste/color suaves y genera el recorte con
     fondo transparente (distancia euclidiana al blanco puro).
  3. Agrega una sombra elíptica difuminada bajo el frasco.
  4. Sube la nueva imagen como "<id>-cutout.png", la reordena a la
     posición 0 y borra el/los recorte(s) anteriores del producto.

Nota: si Shopify ya tiene un archivo con ese mismo nombre (p. ej. de
una corrida anterior de este script), le agrega un sufijo aleatorio
a la URL final (ej. "<id>-cutout_ab12cd34-....png"). Por eso toda
detección de "es este el recorte" debe usar el substring suelto
"cutout", nunca "-cutout." (con el punto), que deja de coincidir en
cuanto aparece el sufijo. El mismo detalle aplica al Liquid de
sections/ps-producto.liquid.

Nota sobre el recorte de fondo: NO uses un umbral global de "que tan
blanco es este pixel" (distancia euclidiana a (255,255,255) sobre
toda la imagen) — falla en dos casos reales que ya se dieron en esta
tienda: (1) frascos plateados/con tapa espejada, donde los reflejos
brillantes DEL PRODUCTO quedan tan cerca del blanco puro como el
fondo y el algoritmo les hace agujeros; (2) fondos de estudio color
crema/hueso (no blanco puro), donde el fondo casi no se distingue del
producto y queda una neblina translúcida sin recortar bien ("se ve
borroso"). La función `cutout()` de abajo usa en su lugar un
flood-fill desde los bordes de la imagen (vía `scipy.ndimage.label`):
solo se hace transparente lo que es del color del fondo real Y está
conectado a un borde de la foto, así que un reflejo brillante rodeado
por el propio frasco nunca se borra, sin importar qué tan claro sea.
"""
import json
import os
import uuid
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from scipy import ndimage

STORE = "7eew11-ei.myshopify.com"
API_VERSION = "2025-01"
TOKEN = os.environ["SHOPIFY_ADMIN_TOKEN"]
OUT_DIR = "/tmp/enhance_product_photos"
os.makedirs(OUT_DIR, exist_ok=True)

PRODUCTS_QUERY = """
query($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      title
      media(first: 10) {
        nodes { id ... on MediaImage { image { url } } }
      }
    }
  }
}
"""

STAGED_MUTATION = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""

CREATE_MEDIA_MUTATION = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { ... on MediaImage { id } }
    mediaUserErrors { field message }
  }
}
"""

REORDER_MUTATION = """
mutation productReorderMedia($id: ID!, $moves: [MoveInput!]!) {
  productReorderMedia(id: $id, moves: $moves) {
    job { id }
    userErrors { field message }
  }
}
"""

DELETE_MUTATION = """
mutation productDeleteMedia($mediaIds: [ID!]!, $productId: ID!) {
  productDeleteMedia(mediaIds: $mediaIds, productId: $productId) {
    deletedMediaIds
    mediaUserErrors { field message }
  }
}
"""


def gql(query, variables):
    req = urllib.request.Request(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Shopify-Access-Token", TOKEN)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_products():
    products = []
    cursor = None
    while True:
        result = gql(PRODUCTS_QUERY, {"cursor": cursor})
        data = result["data"]["products"]
        for p in data["nodes"]:
            original_url = None
            cutout_ids = []
            for m in p["media"]["nodes"]:
                img = m.get("image")
                if not img:
                    continue
                if "cutout" in img["url"]:
                    cutout_ids.append(m["id"])
                elif original_url is None:
                    original_url = img["url"]
            products.append({
                "id": p["id"], "title": p["title"],
                "original_url": original_url, "cutout_ids": cutout_ids,
            })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return products


def upload_file(target, file_path):
    boundary = uuid.uuid4().hex
    body = bytearray()
    for p in target["parameters"]:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{p["name"]}"\r\n\r\n'.encode()
        body += f'{p["value"]}\r\n'.encode()
    filename = os.path.basename(file_path)
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += b"Content-Type: image/png\r\n\r\n"
    with open(file_path, "rb") as f:
        body += f.read()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(target["url"], data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        resp.read()


def cutout(im_rgb, tolerance=14, feather=1.3):
    """Quita el fondo por flood-fill desde los bordes de la imagen, no por
    un umbral global de blancura (ver nota al inicio del archivo)."""
    arr = np.array(im_rgb).astype(np.float32)
    border_px = np.concatenate([
        arr[0:6, :].reshape(-1, 3), arr[-6:, :].reshape(-1, 3),
        arr[:, 0:6].reshape(-1, 3), arr[:, -6:].reshape(-1, 3),
    ])
    bg_color = np.median(border_px, axis=0)
    dist = np.sqrt(((arr - bg_color) ** 2).sum(axis=2))
    candidate_bg = dist < tolerance
    labeled, _ = ndimage.label(candidate_bg)
    border_labels = set(labeled[0, :]) | set(labeled[-1, :]) | set(labeled[:, 0]) | set(labeled[:, -1])
    border_labels.discard(0)
    bg_mask = np.isin(labeled, list(border_labels)) if border_labels else np.zeros_like(candidate_bg)
    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    out = Image.fromarray(rgba, "RGBA")
    a = out.split()[3].filter(ImageFilter.GaussianBlur(feather))
    out.putalpha(a)
    return out


def source_has_real_alpha(im):
    """True si la foto de origen ya trae su propio canal de transparencia
    (p. ej. el proveedor ya la recortó). En ese caso hay que RESPETARLO en
    vez de recalcular el fondo desde cero: convertir a RGB primero descarta
    ese canal bueno y dejaba colores "fantasma" bajo las zonas ya
    transparentes, que nuestro propio recorte después reinterpretaba mal
    y producía rayas/artefactos (visto repetidamente en el Valentino Born
    in Roma, cuya foto de origen 481090.webp ya viene recortada)."""
    if im.mode not in ("RGBA", "LA") and "transparency" not in im.info:
        return False
    alpha = np.array(im.convert("RGBA"))[:, :, 3]
    return alpha.min() < 250 and alpha.max() > 5


def enhance(url, out_path):
    src_path = out_path + ".src"
    urllib.request.urlretrieve(url, src_path)
    src_im = Image.open(src_path)
    reuse_alpha = source_has_real_alpha(src_im)

    im = src_im.convert("RGB")
    # Nitidez y color suaves: valores altos aqui producen halos/ruido
    # (bandas blancas) sobre los detalles facetados de los frascos.
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=4))
    im = ImageEnhance.Contrast(im).enhance(1.06)
    im = ImageEnhance.Color(im).enhance(1.05)
    im = ImageEnhance.Brightness(im).enhance(1.015)

    if reuse_alpha:
        cutout_im = Image.merge("RGBA", (*im.split(), src_im.convert("RGBA").split()[3]))
    else:
        cutout_im = cutout(im)
    a = cutout_im.split()[3]

    alpha_arr = np.array(a)
    ys, xs = np.where(alpha_arr > 20)
    if len(ys) == 0:
        cutout_im.save(out_path)
        os.remove(src_path)
        return
    x0, x1 = float(xs.min()), float(xs.max())
    y1 = float(ys.max())
    bottle_w = x1 - x0
    cx = (x0 + x1) / 2

    shadow_layer = Image.new("RGBA", cutout_im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    ell_w = bottle_w * 0.62
    ell_h = ell_w * 0.16
    ell_y = y1 - ell_h * 0.35
    sd.ellipse(
        [cx - ell_w / 2, ell_y - ell_h / 2, cx + ell_w / 2, ell_y + ell_h / 2],
        fill=(0, 0, 0, 130),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(float(ell_h) * 0.55))

    final = Image.alpha_composite(shadow_layer, cutout_im)
    final.save(out_path)
    os.remove(src_path)


def main():
    products = list_products()
    print("Productos encontrados:", len(products))
    done = 0
    for p in products:
        pid = p["id"]
        numeric_id = pid.rsplit("/", 1)[-1]
        if not p["original_url"]:
            print(pid, p["title"], "SIN FOTO ORIGINAL, se omite")
            continue

        out_path = os.path.join(OUT_DIR, f"{numeric_id}-cutout.png")
        try:
            enhance(p["original_url"], out_path)
        except Exception as e:
            print(pid, p["title"], "ERROR AL PROCESAR:", e)
            continue

        staged = gql(STAGED_MUTATION, {"input": [{
            "filename": f"{numeric_id}-cutout.png",
            "mimeType": "image/png",
            "httpMethod": "POST",
            "resource": "FILE",
        }]})
        staged_data = staged["data"]["stagedUploadsCreate"]
        if staged_data["userErrors"]:
            print(pid, p["title"], "ERROR AL RESERVAR SUBIDA:", staged_data["userErrors"])
            continue
        target = staged_data["stagedTargets"][0]
        upload_file(target, out_path)

        created = gql(CREATE_MEDIA_MUTATION, {
            "productId": pid,
            "media": [{"originalSource": target["resourceUrl"], "mediaContentType": "IMAGE", "alt": ""}],
        })
        created_data = created["data"]["productCreateMedia"]
        if created_data["mediaUserErrors"]:
            print(pid, p["title"], "ERROR AL CREAR MEDIA:", created_data["mediaUserErrors"])
            continue
        new_media_id = created_data["media"][0]["id"]

        reorder = gql(REORDER_MUTATION, {"id": pid, "moves": [{"id": new_media_id, "newPosition": "0"}]})
        if reorder["data"]["productReorderMedia"]["userErrors"]:
            print(pid, p["title"], "ERROR AL REORDENAR:", reorder["data"]["productReorderMedia"]["userErrors"])

        if p["cutout_ids"]:
            deleted = gql(DELETE_MUTATION, {"mediaIds": p["cutout_ids"], "productId": pid})
            if deleted["data"]["productDeleteMedia"]["mediaUserErrors"]:
                print(pid, p["title"], "ERROR AL BORRAR ANTERIOR:", deleted["data"]["productDeleteMedia"]["mediaUserErrors"])

        print(pid, "|", p["title"][:45], "-> mejorada y publicada")
        done += 1

    print("\nTOTAL MEJORADAS:", done, "/", len(products))


if __name__ == "__main__":
    main()
