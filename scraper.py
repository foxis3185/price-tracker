# scrape.py
# pip requirements: requests pandas beautifulsoup4
import os
import csv
import time
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

OUT_CSV = "prices.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PriceBot/1.0; +mailto:ton.email@example.com)"
}


# Configure tes produits ici (id, type, identifier)
# type: keepa | backmarket | cdiscount | generic_scrape
PRODUCTS = [
    {"name":"Pixel 8a", "type":"keepa", "asin":"B0EXAMPLE"},
    {"name":"iPhone reconditionné (backmarket)", "type":"backmarket", "sku":"BACKMARKET_PRODUCT_ID_OR_SLUG"},
    {"name":"Pixel 8a", "type":"cdiscount", "url":"https://www.cdiscount.com/telephonie/telephone-mobile/smartphone-google-pixel-8a-5g-double-sim-128go-por/f-14404-goo1715718410917.html"},
]

def fetch_keepa(asin):
    key = os.getenv("KEEPA_KEY")
    if not key:
        raise RuntimeError("KEEPA_KEY missing")
    url = "https://api.keepa.com/product"
    params = {"key": key, "domain":"fr", "asin": asin}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    # Simplif: récupérer le dernier prix vendeur new (Keepa price values are in cents)
    try:
        price_history = data["products"][0]["buyBoxSellerIdHistory"]
    except Exception:
        # fallback: try lowest new price
        prod = data["products"][0]
        current_price = prod.get("buyBoxPrice") or prod.get("listPrice")
        if current_price:
            return current_price/100.0        
        raise
    # If no direct, try other fields
    prod = data["products"][0]
    price = prod.get("buyBoxPrice")
    if price:
        return price/100.0
    # fallback
    lp = prod.get("listPrice")
    if lp:
        return lp/100.0
    raise RuntimeError("Keepa: impossible d'extraire le prix")

def fetch_backmarket(sku):
    token = os.getenv("BACKMARKET_TOKEN")
    if not token:
        raise RuntimeError("BACKMARKET_TOKEN missing")
    api = f"https://api.backmarket.dev/offers/{sku}"
    headers = {"Authorization": f"Bearer {token}", "Accept":"application/json"}
    r = requests.get(api, headers=headers, timeout=15)
    r.raise_for_status()
    j = r.json()
    # adapter selon la doc BackMarket
    price = j.get("price", {}).get("raw") or j.get("price", {}).get("value")
    if price:
        return float(price)
    raise RuntimeError("BackMarket: prix introuvable dans la réponse")

def fetch_cdiscount(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # TU DOIS ADAPTER CE SELECTOR selon la page (exemple générique)
    el = soup.select_one(".price:last-child, .prdtBlocPrice .price")
    if not el:
        # essayer d'extraire un nombre dans la page
        m = re.search(r"([\d\.,]{2,})\s?€", r.text)
        if m:
            s = m.group(1).replace(".", "").replace(",", ".")
            return float(s)
        raise RuntimeError("Cdiscount: sélecteur prix introuvable")
    txt = el.get_text()
    m = re.search(r"[\d\.,]+", txt)
    if not m:
        raise RuntimeError("Cdiscount: impossible d'extraire nombre")
    s = m.group(0).replace(".", "").replace(",", ".")
    return float(s)

def append_csv(name, price):
    now = datetime.utcnow().isoformat()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([now, name, f"{price:.2f}"])
    print(now, name, price)

def main():
    for p in PRODUCTS:
        try:
            if p["type"] == "keepa":
                price = fetch_keepa(p["asin"])
            elif p["type"] == "backmarket":
                price = fetch_backmarket(p["sku"])
            elif p["type"] == "cdiscount":
                price = fetch_cdiscount(p["url"])
            else:
                raise RuntimeError("type inconnu")
            append_csv(p["name"], price)
        except Exception as e:
            print("Erreur pour", p.get("name"), ":", e)
        time.sleep(3)  # delay pour être propre
if __name__ == "__main__":
    main()
