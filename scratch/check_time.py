import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv("backend/.env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

def get_latest_ingestion():
    # Query knowledge_sources for the latest record
    res = supabase.table("knowledge_sources").select("created_at").order("created_at", desc=True).limit(1).execute()
    
    if res.data:
        utc_time_str = res.data[0]['created_at']
        # Supabase returns ISO format, e.g., 2026-05-07T13:28:46+00:00
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        ist_dt = utc_dt.astimezone(ist)
        
        print(f"Latest Ingestion (UTC): {utc_dt}")
        print(f"Latest Ingestion (IST): {ist_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("No ingestions found.")

if __name__ == "__main__":
    get_latest_ingestion()
