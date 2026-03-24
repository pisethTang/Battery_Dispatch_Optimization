import csv 
from datetime import datetime, timedelta



def create_synthetic_prices():
    # start at midnight 
    start_time = datetime(2026, 3, 20, 0, 0)

    with open("market_data.csv", mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "price_aud"])

        for i in range(48):
            current_time = start_time + timedelta(minutes=30 * i)
            hour = current_time.hour 

            # price logic 
            if 10 <= hour <= 14:
                price = 10.0 # extremely cheap midday (solar)
            elif 17 <= hour <= 20:
                price = 150.0 # expensive evening peak 
            else:
                price = 50.0 # normal price 
            writer.writerow([current_time.strftime("%H:%M"), price])

create_synthetic_prices()
print("Generated market data.csv!")




