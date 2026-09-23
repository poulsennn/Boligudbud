import json
import os
from datetime import datetime
import requests

# Konfiguration
MUNICIPALITY_ID = 167  # Hvidovre Kommune ID hos Boliga
DATA_FILE = "huse_hvidovre_historik.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


def hent_aktuelle_huse():
    """Henter alle huse/rækkehuse til salg i Hvidovre Kommune fra Boliga."""
    huse = {}
    page = 1
    page_size = 50

    while True:
        url = "https://api.boliga.dk/api/v2/search/results"
        params = {
            "municipality": MUNICIPALITY_ID,
            "propertyType": "1,2",  # 1 = Villa, 2 = Rækkehus
            "pageSize": page_size,
            "page": page,
            "sort": "date-d",  # Nyeste oprettet først
        }

        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Fejl ved hentning af data (side {page}): {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        for item in results:
            house_id = str(item.get("id"))
            street = item.get("street", "")
            zip_code = item.get("zipCode", "")
            city = item.get("city", "")
            adresse = f"{street}, {zip_code} {city}".strip()

            huse[house_id] = {
                "id": house_id,
                "adresse": adresse,
                "pris": item.get("price"),
                "kvm": item.get("sqm"),
                "vaerelser": item.get("rooms"),
                "byggeaar": item.get("buildYear"),
                "url": f"https://www.boliga.dk/bolig/{house_id}",
            }

        # Tjek om vi har hentet alle sider
        meta = data.get("meta", {})
        total_count = meta.get("totalCount", 0)
        if page * page_size >= total_count:
            break

        page += 1

    return huse


def sammenlign_og_opdater():
    """Sammenligner dagens liste med tidligere gemte historik og opdaterer filen."""
    dagens_huse = hent_aktuelle_huse()

    if not dagens_huse:
        print("Ingen huse blev fundet. Tjek din netværksforbindelse.")
        return

    # Indlæs tidligere kørsel, hvis den findes
    tidligere_huse = {}
    første_kørsel = False

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            tidligere_huse = json.load(f)
    else:
        første_kørsel = True

    dagens_ids = set(dagens_huse.keys())
    tidligere_ids = set(tidligere_huse.keys())

    nye_ids = dagens_ids - tidligere_ids
    fjernede_ids = tidligere_ids - dagens_ids

    # Udskriv rapport
    i_dag_dato = datetime.now().strftime("%d-%m-%Y %H:%M")
    print("=" * 65)
    print(f"BOLIGOPDATERING - HVIDOVRE KOMMUNE ({i_dag_dato})")
    print("=" * 65)
    print(f"Aktuelt antal huse til salg i dag: {len(dagens_huse)}")
    print("-" * 65)

    if første_kørsel:
        print(
            "ℹ️ Dette er første gang scriptet kører. Alle fundne huse er gemt som baseline."
        )
    else:
        # 1. Nye huse
        print(f"\n🆕 NYE HUSE TIL SALG SIKDEN SIDSTE KØRSEL ({len(nye_ids)}):")
        if nye_ids:
            for hid in nye_ids:
                h = dagens_huse[hid]
                pris = f"{h['pris']:,} kr.".replace(",", ".") if h["pris"] else "N/A"
                print(f" • {h['adresse']}")
                print(
                    f"   Pris: {pris} | Areal: {h['kvm']} m² | Værelser: {h['vaerelser']}"
                )
                print(f"   Link: {h['url']}\n")
        else:
            print("   Ingen nye huse tilføjet på listen.")

        # 2. Fjernede huse
        print(f"\n❌ FJERNET FRA LISTEN / MULIGVIS SOLGT ({len(fjernede_ids)}):")
        if fjernede_ids:
            for hid in fjernede_ids:
                h = tidligere_huse[hid]
                pris = f"{h['pris']:,} kr.".replace(",", ".") if h["pris"] else "N/A"
                print(f" • {h['adresse']} (Sidst udbudt til {pris})")
                print(f"   Link: {h['url']}\n")
        else:
            print("   Ingen huse er fjernet fra listen.")

    # Gem dagens data til næste kørsel
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dagens_huse, f, ensure_ascii=False, indent=2)

    print("-" * 65)
    print(f"Data gemt i '{DATA_FILE}'. Kør scriptet igen i morgen for ny status.")


if __name__ == "__main__":
    sammenlign_og_opdater()
