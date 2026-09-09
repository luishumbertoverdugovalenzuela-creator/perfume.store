import json, os, random, urllib.request

STORE = "7eew11-ei.myshopify.com"
TOKEN = os.environ["SHOPIFY_ADMIN_TOKEN"]
API_VERSION = "2025-01"

with open("/tmp/claude-0/-home-user-perfume-store/6247ebf5-f1a8-520d-a77e-683cf1d36a6a/scratchpad/all_prices.json") as f:
    PRODUCTS = json.load(f)

MUTATION = """
mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price compareAtPrice }
    userErrors { field message }
  }
}
"""


def gql(query, variables):
    req = urllib.request.Request(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"), method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Shopify-Access-Token", TOKEN)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


random.seed(42)
done = 0
for p in PRODUCTS:
    variants_input = []
    for v in p["variants"]["nodes"]:
        price = float(v["price"])
        pct_off = random.uniform(0.15, 0.30)
        compare_at = price / (1 - pct_off)
        compare_at = round(compare_at / 10) * 10  # redondear a múltiplo de 10 (se ve más real)
        if compare_at <= price:
            compare_at = price + 100
        variants_input.append({
            "id": v["id"],
            "compareAtPrice": f"{compare_at:.2f}",
        })
    result = gql(MUTATION, {"productId": p["id"], "variants": variants_input})
    data = result["data"]["productVariantsBulkUpdate"]
    if data["userErrors"]:
        print(p["id"], p["title"][:40], "ERROR:", data["userErrors"])
    else:
        done += 1
        for pv in data["productVariants"]:
            print(p["title"][:40], "-> antes:", pv["compareAtPrice"], "| ahora:", pv["price"])

print("\nTOTAL ACTUALIZADOS:", done, "/", len(PRODUCTS))
