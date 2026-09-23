import json
import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests

# Konfiguration af kommuner (Boliga Kommune ID'er)
KOMMUNER = {
    "hvidovre": {
        "navn": "Hvidovre Kommune",
        "id": 167,
        "historik_fil": "huse_hvidovre_historik.json",
    },
    "kobenhavn": {
        "navn": "Københavns Kommune",
        "id": 101,
        "historik_fil": "huse_kobenhavn_historik.json",
    },
}

TIMESERIES_FILE = "bolig_tidsserie.json"
HTML_OUTPUT = "index.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


def hent_aktuelle_huse(mup_id):
    """Henter alle huse/rækkehuse til salg for en specifik kommune fra Boliga."""
    huse = {}
    page = 1
    page_size = 50

    while True:
        url = "https://api.boliga.dk/api/v2/search/results"
        params = {
            "municipality": mup_id,
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
            print(f"Fejl ved hentning af data for kommune ID {mup_id} (side {page}): {e}")
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


def generer_fane_indhold(key, kommune_navn, tidsserie_data):
    """Bygger HTML og Plotly-graf for én specifik kommune."""
    kom_data = tidsserie_data.get(key, {})

    # 1. Byg Dataframe til diagram
    rows = []
    for dato, data in kom_data.items():
        rows.append(
            {
                "Dato": dato,
                "Boligudbud": data.get("total_udbud", 0),
                "Tilgang (Nye)": data.get("tilgang_antal", 0),
                "Afgang (Fjernet)": data.get("afgang_antal", 0),
                "Prisnedsættelser": data.get("prisnedsaettelse_antal", 0),
            }
        )

    if rows:
        df = pd.DataFrame(rows)
        fig = px.line(
            df,
            x="Dato",
            y=["Boligudbud", "Tilgang (Nye)", "Afgang (Fjernet)", "Prisnedsættelser"],
            title=f"Boligmarkedet i {kommune_navn} (Udbud, ændringer & prisændringer)",
            labels={"value": "Antal boliger", "variable": "Måling", "Dato": "Dato"},
            markers=True,
        )
        fig.update_layout(
            template="plotly_white",
            hovermode="x unified",
            legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    else:
        chart_html = "<p>Ingen historiske data tilgængelige endnu.</p>"

    # 2. Tabel over PRISNEDSÆTTELSER
    pris_rows_html = ""
    for dato in sorted(kom_data.keys(), reverse=True):
        nedsaettelser = kom_data[dato].get("prisnedsaettelser_huse", [])
        if nedsaettelser:
            for h in nedsaettelser:
                pris_for = f"{h['pris_for']:,} kr.".replace(",", ".") if h.get("pris_for") else "N/A"
                pris_efter = f"{h['pris_efter']:,} kr.".replace(",", ".") if h.get("pris_efter") else "N/A"
                besparelse = (
                    f"-{h['besparelse']:,} kr. ({h.get('procent', 0)}%)".replace(",", ".")
                    if h.get("besparelse")
                    else "N/A"
                )
                url_link = f"<a href='{h['url']}' target='_blank'>Se annonce</a>" if h.get("url") else "-"
                pris_rows_html += f"""
                <tr>
                    <td><b>{dato}</b></td>
                    <td>{h['adresse']}</td>
                    <td><s style='color: #888;'>{pris_for}</s></td>
                    <td><b style='color: #d9534f;'>{pris_efter}</b></td>
                    <td><span style='color: #28a745; font-weight: bold;'>{besparelse}</span></td>
                    <td>{url_link}</td>
                </tr>
                """

    if not pris_rows_html:
        pris_rows_html = "<tr><td colspan='6'>Ingen prisnedsættelser registreret endnu.</td></tr>"

    # 3. Tabel over AFGÅEDE BOLIGER
    afgang_rows_html = ""
    for dato in sorted(kom_data.keys(), reverse=True):
        afgaaede = kom_data[dato].get("afgaaet_huse", [])
        if afgaaede:
            for h in afgaaede:
                pris_formatted = f"{h['pris']:,} kr.".replace(",", ".") if h.get("pris") else "N/A"
                kvm_val = f"{h['kvm']} m²" if h.get("kvm") else "N/A"
                url_link = f"<a href='{h['url']}' target='_blank'>Se annonce</a>" if h.get("url") else "-"
                afgang_rows_html += f"""
                <tr>
                    <td><b>{dato}</b></td>
                    <td>{h['adresse']}</td>
                    <td>{kvm_val}</td>
                    <td>{pris_formatted}</td>
                    <td>{url_link}</td>
                </tr>
                """

    if not afgang_rows_html:
        afgang_rows_html = "<tr><td colspan='5'>Ingen afgåede boliger registreret endnu.</td></tr>"

    return f"""
        <div class="chart-box">
            {chart_html}
        </div>

        <h2>📉 Historiske prisnedsættelser ({kommune_navn})</h2>
        <table>
            <thead>
                <tr>
                    <th>Dato</th>
                    <th>Adresse</th>
                    <th>Før pris</th>
                    <th>Efter pris</th>
                    <th>Nedsætning</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {pris_rows_html}
            </tbody>
        </table>

        <h2>📋 Afgåede boliger ({kommune_navn})</h2>
        <table>
            <thead>
                <tr>
                    <th>Dato</th>
                    <th>Adresse</th>
                    <th>Kvadratmeter</th>
                    <th>Sidste udbudspris</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {afgang_rows_html}
            </tbody>
        </table>
    """


def generer_samlet_html(tidsserie_data):
    """Genererer en samlet HTML-fil med faner for hver kommune."""
    nu_tid = datetime.now().strftime("%d-%m-%Y kl. %H:%M")

    hvidovre_html = generer_fane_indhold("hvidovre", KOMMUNER["hvidovre"]["navn"], tidsserie_data)
    kobenhavn_html = generer_fane_indhold("kobenhavn", KOMMUNER["kobenhavn"]["navn"], tidsserie_data)

    html_content = f"""<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boligmarkedet - Hvidovre & København</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
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
        
        /* Faneblade (Tabs) CSS */
        .tab-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            border-bottom: 2px solid #e9ecef;
        }}
        .tab-btn {{
            padding: 12px 24px;
            border: none;
            background: none;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            color: #6c757d;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s ease;
        }}
        .tab-btn:hover {{
            color: #0066cc;
        }}
        .tab-btn.active {{
            color: #0066cc;
            border-bottom-color: #0066cc;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}

        .chart-box {{
            margin-bottom: 40px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 30px;
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
        <h1>🏡 Boligudbud & Historik</h1>
        <p>Automatisk daglig opdatering af huse og rækkehuse til salg.</p>

        <!-- Fane-knapper -->
        <div class="tab-buttons">
            <button class="tab-btn active" onclick="openTab(event, 'tab-hvidovre')">Hvidovre Kommune</button>
            <button class="tab-btn" onclick="openTab(event, 'tab-kobenhavn')">Københavns Kommune</button>
        </div>

        <!-- Fane 1: Hvidovre -->
        <div id="tab-hvidovre" class="tab-content active">
            {hvidovre_html}
        </div>

        <!-- Fane 2: København -->
        <div id="tab-kobenhavn" class="tab-content">
            {kobenhavn_html}
        </div>

        <div class="footer">
            Sidst opdateret: {nu_tid}
        </div>
    </div>

    <script>
        function openTab(evt, tabName) {{
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {{
                tabcontent[i].classList.remove("active");
            }}
            tablinks = document.getElementsByClassName("tab-btn");
            for (i = 0; i < tablinks.length; i++) {{
                tablinks[i].classList.remove("active");
            }}
            document.getElementById(tabName).classList.add("active");
            evt.currentTarget.classList.add("active");
            
            // Tving Plotly til at tilpasse grafstørrelsen ved fane-skift
            window.dispatchEvent(new Event('resize'));
        }}
    </script>
</body>
</html>
"""

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML-rapport opdateret med faner: '{HTML_OUTPUT}'")


def sammenlign_og_opdater():
    """Behandler data for hver kommune og gemmer historik."""
    # Indlæs samlet tidsserie-historik (eller konverter gammelt format)
    tidsserie_data = {}
    if os.path.exists(TIMESERIES_FILE):
        with open(TIMESERIES_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

            # Konverter gammel tidsserie-struktur ifald den fandtes i roden
            if raw_data and not ("hvidovre" in raw_data or "kobenhavn" in raw_data):
                tidsserie_data = {"hvidovre": raw_data, "kobenhavn": {}}
            else:
                tidsserie_data = raw_data

    idag_str = datetime.now().strftime("%Y-%m-%d")

    # Gennemgå hver kommune
    for key, info in KOMMUNER.items():
        print(f"Henter og behandler data for {info['navn']}...")
        dagens_huse = hent_aktuelle_huse(info["id"])

        if not dagens_huse:
            print(f"Advarsel: Ingen huse fundet for {info['navn']}.")
            continue

        tidligere_huse = {}
        historik_fil = info["historik_fil"]
        første_kørsel = not os.path.exists(historik_fil)

        if os.path.exists(historik_fil):
            with open(historik_fil, "r", encoding="utf-8") as f:
                tidligere_huse = json.load(f)

        dagens_ids = set(dagens_huse.keys())
        tidligere_ids = set(tidligere_huse.keys())

        nye_ids = dagens_ids - tidligere_ids
        fjernede_ids = tidligere_ids - dagens_ids if not første_kørsel else set()
        eksisterende_ids = dagens_ids.intersection(tidligere_ids) if not første_kørsel else set()

        # Registrer prisnedsættelser
        prisnedsaettelser_liste = []
        for hid in eksisterende_ids:
            gammel_pris = tidligere_huse[hid].get("pris")
            ny_pris = dagens_huse[hid].get("pris")

            if gammel_pris and ny_pris and ny_pris < gammel_pris:
                forskellig = gammel_pris - ny_pris
                pct = round((forskellig / gammel_pris) * 100, 1)
                prisnedsaettelser_liste.append(
                    {
                        "adresse": dagens_huse[hid]["adresse"],
                        "pris_for": gammel_pris,
                        "pris_efter": ny_pris,
                        "besparelse": forskellig,
                        "procent": pct,
                        "url": dagens_huse[hid]["url"],
                    }
                )

        # Gem afgåede huse
        afgaaet_liste = [
            {
                "adresse": tidligere_huse[hid]["adresse"],
                "kvm": tidligere_huse[hid]["kvm"],
                "pris": tidligere_huse[hid]["pris"],
                "url": tidligere_huse[hid]["url"],
            }
            for hid in fjernede_ids
        ]

        # Sørg for at struktur findes for kommune
        if key not in tidsserie_data:
            tidsserie_data[key] = {}

        tidsserie_data[key][idag_str] = {
            "total_udbud": len(dagens_huse),
            "tilgang_antal": len(nye_ids) if not første_kørsel else 0,
            "afgang_antal": len(fjernede_ids),
            "prisnedsaettelse_antal": len(prisnedsaettelser_liste),
            "afgaaet_huse": afgaaet_liste,
            "prisnedsaettelser_huse": prisnedsaettelser_liste,
        }

        # Gem kommunens egen historikfil for huse
        with open(historik_fil, "w", encoding="utf-8") as f:
            json.dump(dagens_huse, f, ensure_ascii=False, indent=2)

    # Gem samlet tidsserie
    with open(TIMESERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(tidsserie_data, f, ensure_ascii=False, indent=2)

    # Byg samlet HTML med faner
    generer_samlet_html(tidsserie_data)


if __name__ == "__main__":
    sammenlign_og_opdater()
