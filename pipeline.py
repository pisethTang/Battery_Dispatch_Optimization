import requests
from datetime import datetime, timedelta, timezone


import os
# from os.path import join, dirname
from dotenv import load_dotenv


# 
import pandas as pd 


# dotenv_path = join(dirname(__file__), '.env')
# loads the .env file, the sdk will automatically look for OPENELECTRICITY_API_KEY
load_dotenv()



# open electricity python sdk  
from openelectricity import OEClient
from openelectricity.types import MarketMetric

# OPEN_API_KEY = os.getenv("OPEN_ELE_API_KEY")
# if OPEN_API_KEY is None or OPEN_API_KEY == "":
#     raise ValueError(f"Open Electricity API key was not imported {OPEN_API_KEY}")
# print(OPEN_API_KEY)
# input()



def run_pipeline():
    print("1. Fetching real SA1 spot prices using the OpenElectricity Python SDK...")    
    
    
    # The public OpenElectricity/OpenNEM endpoint for SA1 prices
    # url = "https://api.opennem.org.au/stats/price/SA1"
    # base_url = "https://api.openelectricity.org.au/v4"

    # headers = {
    #     "Authorization": f"Bearer {OPEN_API_KEY}",
    #     "Content-Type": "application/json"
    # }
    
    try:

        # initialize the sdk client 
        with OEClient() as client: 
            # fetch the last 24 hours of 30-minute price data for all NEM regions 
            response = client.get_market(
                network_code="NEM",
                metrics=[MarketMetric.PRICE],
                interval="5m",
                # region="SA1",
                network_region="SA1",
                date_start=datetime.now() - timedelta(days=1),
                primary_grouping="network_region"
            )

            # convert response to pandas 
            # df = response.to_pandas()


            # debugging 
            # print("\n--- DATAFRAME COLUMNS ---")
            # print(df.columns.to_list())
            # return 
        

            # filter the dataframe for South Australia (SA1)
            # sa_data = df[df["network_region"] == "SA1"].copy()
            sa_data = response.to_pandas()


            print("\n--- FIRST 15 ROWS ---")
            print(sa_data.head(15))
            # return 

            # Convert intervals to datetime, set as index, and resample into 30-minute averages
            sa_data["interval"] = pd.to_datetime(sa_data["interval"])
            sa_data = sa_data.set_index("interval")
            sa_data = sa_data.resample("30min").mean().reset_index()

            # ensure chronological order and grab the latest 48 intervals (24 hours-data)
            sa_data = sa_data.sort_values("interval").tail(48)
            print(f"✅ Successfully fetched and filtered {len(sa_data)} intervals for SA1 using Pandas.")

        
    except Exception as e:
        print(f"❌ Failed to fetch external data via SDK. Error: {e}")
        print("Note: If the public API is rate-limiting, you may need to register for a free API key at platform.openelectricity.org.au")
        return

    print("2. Formatting the data to match your FastAPI Pydantic contract...")
    
    # We create fake timestamps starting 24 hours ago, matching the real prices
    # start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    market_data = []
    # loop through the data frame and build the payload
    for _, row in sa_data.iterrows():
        market_data.append({
            "timestamp": row["interval"].isoformat(), # convert pandas timestamp to ISO string 
            
            # Extract the price, defaulting to 0.0 if the grid data is missing for that block
            "price_aud_mwh": float(row['price']) if pd.notna(row['price']) else 0.0        
        })
        
    # Build the exact JSON payload your FastAPI server requires
    payload = {
        "battery": {
            "capacity_mwh": 5.0,
            "max_mw": 2.5,
            "efficiency": 0.9
        },
        "market_data": market_data
    }
    
    print("3. Sending real data payload to your local Battery Dispatch API...")
    
    # Hit the Docker container running on your machine
    api_url = "http://127.0.0.1:8000/api/v1/optimize"
    
    api_response = requests.post(api_url, 
                                 json=payload)
    
    if api_response.status_code == 200:
        result = api_response.json()
        profit = result['data']['total_profit_aud']
        print(f"\n🎉 SUCCESS! Your API optimized the battery against real SA1 prices.")
        print(f"💰 Projected 24-Hour Profit: ${profit}")
        print("\nFirst 3 scheduled actions:")
        for action in result['data']['schedule'][:3]:
            print(f"  {action['timestamp']} | Price: ${action['price_aud_mwh']} | Charge: {action['charge_mw']}MW | Discharge: {action['discharge_mw']}MW")
        

        print("\nActive scheduled actions (Charging or Discharging):")
        for action in result['data']['schedule']:
            if action['charge_mw'] > 0 or action['discharge_mw'] > 0:
                print(f"  {action['timestamp'][11:16]} | Price: ${round(action['price_aud_mwh'], 2)} | Charge: {action['charge_mw']}MW | Discharge: {action['discharge_mw']}MW | SoC: {action['soc_mwh']}MWh")
    else:
        print(f"❌ Your API returned an error: {api_response.text}")

if __name__ == "__main__":
    run_pipeline()

# https://gemini.google.com/app/d42f0dfeac9b254a?is_sa=1&is_sa=1&android-min-version=301356232&ios-min-version=322.0&campaign_id=bkws&utm_source=sem&utm_medium=paid-media&utm_campaign=bkws&pt=9008&mt=8&ct=p-growth-sem-bkws&gclsrc=aw.ds&gad_source=1&gad_campaignid=22437964261&gbraid=0AAAAApk5BhlTX3MkpF7nIacpTUb7etnbN&gclid=Cj0KCQiAnJHMBhDAARIsABr7b84shuWqfx0UvOhc3MwNnDRCJJO5jpV4lSTTbBx42jMRPPgo7ersQ84aAgB9EALw_wcB