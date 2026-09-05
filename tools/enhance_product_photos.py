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
"""
import json
import os
import uuid
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

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
                if "-cutout." in img["url"]:
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


def enhance(url, out_path):
    src_path = out_path + ".src"
    urllib.request.urlretrieve(url, src_path)
    im = Image.open(src_path).convert("RGB")

    # Nitidez y color suaves: valores altos aqui producen halos/ruido
    # (bandas blancas) sobre los detalles facetados de los frascos.
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=4))
    im = ImageEnhance.Contrast(im).enhance(1.06)
    im = ImageEnhance.Color(im).enhance(1.05)
    im = ImageEnhance.Brightness(im).enhance(1.015)

    arr = np.array(im).astype(np.float32)
    dist = np.sqrt(((arr - 255.0) ** 2).sum(axis=2))
    low, high = 8.0, 40.0
    alpha = np.clip((dist - low) / (high - low), 0, 1) * 255.0
    alpha = alpha.astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    cutout = Image.fromarray(rgba, "RGBA")
    a = cutout.split()[3].filter(ImageFilter.GaussianBlur(1.3))
    cutout.putalpha(a)

    alpha_arr = np.array(a)
    ys, xs = np.where(alpha_arr > 20)
    if len(ys) == 0:
        cutout.save(out_path)
        os.remove(src_path)
        return
    x0, x1 = float(xs.min()), float(xs.max())
    y1 = float(ys.max())
    bottle_w = x1 - x0
    cx = (x0 + x1) / 2

    shadow_layer = Image.new("RGBA", cutout.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    ell_w = bottle_w * 0.62
    ell_h = ell_w * 0.16
    ell_y = y1 - ell_h * 0.35
    sd.ellipse(
        [cx - ell_w / 2, ell_y - ell_h / 2, cx + ell_w / 2, ell_y + ell_h / 2],
        fill=(0, 0, 0, 130),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(float(ell_h) * 0.55))

    final = Image.alpha_composite(shadow_layer, cutout)
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
