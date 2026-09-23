import json
import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests

# Konfiguration
MUNICIPALITY_ID = 167  # Hvidovre Kommune ID hos Boliga
DATA_FILE = "huse_hvidovre_historik.json"
TIMESERIES_FILE = "bolig_tidsserie.json"
HTML_OUTPUT = "index.html"

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
            "sort": "date-d",
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

        meta = data.get("meta", {})
        total_count = meta.get("totalCount", 0)
        if page * page_size >= total_count:
            break

        page += 1

    return huse


def generer_html_rapport(tidsserie_data):
    """Genererer en HTML-rapport med et Plotly Express-diagram og tabel over afgåede boliger."""
    # Build dataframe for plot
    rows = []
    for dato, data in tidsserie_data.items():
        rows.append(
            {
                "Dato": dato,
                "Boligudbud": data.get("total_udbud", 0),
                "Tilgang (Nye)": data.get("tilgang_antal", 0),
                "Afgang (Fjernet)": data.get("afgang_antal", 0),
            }
        )

    df = pd.DataFrame(rows)

    # Plot med Plotly Express
    fig = px.line(
        df,
        x="Dato",
        y=["Boligudbud", "Tilgang (Nye)", "Afgang (Fjernet)"],
        title="Boligudbud, tilgang og afgang over tid (Hvidovre Kommune)",
        labels={"value": "Antal boliger", "variable": "Måling", "Dato": "Dato"},
        markers=True,
    )

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Konverter graf til HTML snippet
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Byg HTML-tabel over afgåede boliger
    tabel_rows_html = ""
    # Sorter datoer nyeste først
    for dato in sorted(tidsserie_data.keys(), reverse=True):
        afgaaede = tidsserie_data[dato].get("afgaaet_huse", [])
        if afgaaede:
            for h in afgaaede:
                pris_formatted = f"{h['pris']:,} kr.".replace(",", ".") if h.get("pris") else "N/A"
                kvm_val = f"{h['kvm']} m²" if h.get("kvm") else "N/A"
                url_link = f"<a href='{h['url']}' target='_blank'>Se annonce</a>" if h.get("url") else "-"
                tabel_rows_html += f"""
                <tr>
                    <td><b>{dato}</b></td>
                    <td>{h['adresse']}</td>
                    <td>{kvm_val}</td>
                    <td>{pris_formatted}</td>
                    <td>{url_link}</td>
                </tr>
                """

    if not tabel_rows_html:
        tabel_rows_html = "<tr><td colspan='5'>Ingen afgåede boliger registreret endnu.</td></tr>"

    # Samlet HTML dokument
    html_content = f"""<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boligmarkedet i Hvidovre Kommune</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #333;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        h1, h2 {{
            color: #1a252f;
        }}
        .chart-box {{
            margin-bottom: 40px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }}
        th {{
            background-color: #f1f3f5;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 0.85em;
            color: #6c757d;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏡 Boligudbud & Historik i Hvidovre Kommune</h1>
        <p>Automatisk daglig opdatering af huse og rækkehuse til salg.</p>
        
        <div class="chart-box">
            {chart_html}
        </div>

        <h2>📋 Afgåede boliger (Solgt / Fjernet fra udbud)</h2>
        <table>
            <thead>
                <tr>
                    <th>Dato</th>
                    <th>Adresse</th>
                    <th>Kvadratmeter</th>
                    <th>Udbudspris</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {tabel_rows_html}
            </tbody>
        </table>

        <div class="footer">
            Sidst opdateret: {datetime.now().strftime("%d-%m-%Y kl. %H:%M")}
        </div>
    </div>
</body>
</html>
"""

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML-rapport opdateret: '{HTML_OUTPUT}'")


def sammenlign_og_opdater():
    """Hovedfunktion for samkørsel, historikopdatering og HTML-generering."""
    dagens_huse = hent_aktuelle_huse()

    if not dagens_huse:
        print("Fejl: Ingen huse fundet.")
        return

    tidligere_huse = {}
    første_kørsel = not os.path.exists(DATA_FILE)

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            tidligere_huse = json.load(f)

    dagens_ids = set(dagens_huse.keys())
    tidligere_ids = set(tidligere_huse.keys())

    nye_ids = dagens_ids - tidligere_ids
    fjernede_ids = tidligere_ids - dagens_ids if not første_kørsel else set()

    # Indlæs eller opret tidsserie-historik
    tidsserie_data = {}
    if os.path.exists(TIMESERIES_FILE):
        with open(TIMESERIES_FILE, "r", encoding="utf-8") as f:
            tidsserie_data = json.load(f)

    idag_str = datetime.now().strftime("%Y-%m-%d")

    # Gem dagens tal og afgåede boliger
    afgaaet_liste = [
        {
            "adresse": tidligere_huse[hid]["adresse"],
            "kvm": tidligere_huse[hid]["kvm"],
            "pris": tidligere_huse[hid]["pris"],
            "url": tidligere_huse[hid]["url"],
        }
        for hid in fjernede_ids
    ]

    tidsserie_data[idag_str] = {
        "total_udbud": len(dagens_huse),
        "tilgang_antal": len(nye_ids) if not første_kørsel else 0,
        "afgang_antal": len(fjernede_ids),
        "afgaaet_huse": afgaaet_liste,
    }

    # Gem filer
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dagens_huse, f, ensure_ascii=False, indent=2)

    with open(TIMESERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(tidsserie_data, f, ensure_ascii=False, indent=2)

    # Generer HTML rapporten
    generer_html_rapport(tidsserie_data)


if __name__ == "__main__":
    sammenlign_og_opdater()
