import requests
from app.config.settings import settings

url = settings.SUPABASE_URL
key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY

if url and key:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(f"{url}/rest/v1/?apikey={key}", headers=headers)
    if r.status_code == 200:
        spec = r.json()
        print("TABLES:")
        for tbl, detail in spec.get("definitions", {}).items():
            print(f"\nTable: {tbl}")
            properties = detail.get("properties", {})
            for col, col_detail in properties.items():
                print(f"  Column: {col} (type: {col_detail.get('type')})")
    else:
        print(f"Error fetching OpenAPI spec: {r.status_code} {r.text}")
else:
    print("Supabase credentials not found in settings.")
