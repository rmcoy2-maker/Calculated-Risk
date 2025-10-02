def fetch_oddsshark_spreads(api_key, season_start=2017, season_end=2024):
    import requests, pandas as pd
    rows = []
    for yr in range(season_start, season_end+1):
        # Fill with your real endpoint pattern
        url = f"https://api.oddsshark.com/v1/nfl/spreads?season={yr}"
        r = requests.get(url, headers={"Authorization": f"Bearer {109093b594be16dcc337624f7202c318}"}, timeout=30)
        r.raise_for_status()
        js = r.json()
        # Normalize into columns: season, home_team, away_team, home_spread, date
        # (Adjust mapping to your API’s exact schema)
        for g in js["games"]:
            rows.append({
                "season": yr,
                "home_team": g["home_team"],
                "away_team": g["away_team"],
                "home_spread": g["home_spread"],  # or line signed to home
                "date": g.get("date")
            })
    return pd.DataFrame(rows)
