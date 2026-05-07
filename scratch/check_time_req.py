import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Manually load .env to be absolutely sure
with open("backend/.env", "r") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

url = os.getenv("SUPABASE_URL")
print(f"DEBUG: URL found in script is: {url}")
key = os.getenv("SUPABASE_ANON_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}"
}

# REST API endpoint for knowledge_sources
endpoint = f"{url}/rest/v1/knowledge_sources?select=created_at&order=created_at.desc&limit=1"

try:
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    if data:
        utc_time_str = data[0]['created_at']
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        
        ist = pytz.timezone('Asia/Kolkata')
        ist_dt = utc_dt.astimezone(ist)
        
        print(f"Latest Ingestion (UTC): {utc_dt}")
        print(f"Latest Ingestion (IST): {ist_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("No ingestions found.")
except Exception as e:
    print(f"Error: {e}")
