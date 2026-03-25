from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware 



from pydantic import BaseModel, Field 
from typing import List, cast 
from datetime import datetime 
import pandas as pd
# import numpy as np



from openelectricity import OEClient
from openelectricity.types import MarketMetric
from datetime import datetime, timedelta

# import math 

# linear programming lib
import pulp 




# create a router with a prefix 
router = APIRouter(
    prefix="/api/v1",
)


# initialize the api 
app = FastAPI(
    title="Battery Dispatch Optimization API",
    description="Calculates optimal charge/discharge schedules against 30-minute spot prices",
    version="1.0.0"
)


# 

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",                  # local 
        "https://d2zg9d8ixwrq14.cloudfront.net",  # production
        "https://optigrid.seth-tang.me",          # (subdomain of seth-tang.me) - production
        
    ], # Allows React to talk to FastAPI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# pydantic models 
class BatterySpecs(BaseModel):
    capacity_mwh: float = Field(..., gt=0, description="Total capacity in MWh")
    max_mw: float = Field(..., gt=0, description="Max charge/discharge rate in MW")
    efficiency: float = Field(0.90, ge=0, le=1, description="Round-trip efficiency (e.g., 0.9 for 90%)")

class MarketInterval(BaseModel):
    timestamp: datetime
    price_aud_mwh: float = Field(..., description="Spot price per MWh in AUD")

class DispatchRequest(BaseModel):
    battery: BatterySpecs
    market_data: List[MarketInterval]





# utility functions
def calculate_optimal_dispatch(battery: BatterySpecs, market_data: List[MarketInterval]):
    # 1. Initialize the LP Problem
    prob = pulp.LpProblem("Battery_Arbitrage", pulp.LpMaximize)
    
    T = len(market_data)
    dt = 0.5  # 30-minute intervals = 0.5 hours
    
    # 2. Define Variables
    # Create dictionaries to hold our decision variables for each timestep
    charge = pulp.LpVariable.dicts("Charge_MW", range(T), lowBound=0, upBound=battery.max_mw)
    discharge = pulp.LpVariable.dicts("Discharge_MW", range(T), lowBound=0, upBound=battery.max_mw)
    soc = pulp.LpVariable.dicts("SoC_MWh", range(T), lowBound=0, upBound=battery.capacity_mwh)
    
    # 3. Objective Function (Maximize Profit)
    profit = pulp.lpSum([
        (discharge[t] - charge[t]) * market_data[t].price_aud_mwh * dt
        for t in range(T)
    ])
    prob += profit
    
    # 4. Constraints (Physics of the battery)
    for t in range(T):
        if t == 0:
            # Assume the battery starts completely empty
            prob += soc[t] == (charge[t] * battery.efficiency - discharge[t]) * dt
        else:
            # Update SoC based on the previous timestep
            prob += soc[t] == soc[t-1] + (charge[t] * battery.efficiency - discharge[t]) * dt
            
    # 5. Solve the problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    # 6. Extract the results into a clean dictionary
    schedule = []
    for t in range(T):
        schedule.append({
            "timestamp": market_data[t].timestamp,
            "price_aud_mwh": market_data[t].price_aud_mwh,
            "charge_mw": round(charge[t].varValue, 2),
            "discharge_mw": round(discharge[t].varValue, 2),
            "soc_mwh": round(soc[t].varValue, 2)
        })
        
    objective_value = cast(float | None, pulp.value(prob.objective))
    total_profit_aud = round(objective_value, 2) if objective_value is not None else 0.0


    response = {
        "optimization_status": pulp.LpStatus[prob.status],
        "total_profit_aud": total_profit_aud,
        "schedule": schedule
    }
    # print(f"response: {response}")

    return response 








# endpoints 
@router.get("/")
def read_root():
    return {"status": "online", "message": "OptiGrid API is running locally and in the cloud!"}


@router.post(f"/optimize")
async def optimize_dispatch(request: DispatchRequest):
    try:
        # Pass the validated JSON data directly into the math engine
        result = calculate_optimal_dispatch(request.battery, request.market_data)
        return {"status": "success", "data": result}
    except Exception as e:
        # If the math fails, return a clean 500 error to the client
        raise HTTPException(status_code=500, detail=str(e))

# health check
@router.get(f"/health")
async def health_check():
    return {"status": "ok"}


    




@router.post(f"/simulate")
def run_live_simulation(battery: BatterySpecs):
    # Fetch live data just like we did in pipeline.py
    try:
        with OEClient() as client: 
            response = client.get_market(
                network_code="NEM",
                network_region="SA1", 
                metrics=[MarketMetric.PRICE],
                interval="5m",
                date_start=datetime.now() - timedelta(days=1)
            )

            # Wrangle the Pandas data into 30-min intervals
            df = response.to_pandas()
            df["interval"] = pd.to_datetime(df["interval"])
            df = df.set_index("interval").resample("30min").mean().reset_index().tail(48)
            
            # Format it for the PuLP engine
            market_data = [
                MarketInterval(
                    timestamp=row["interval"].isoformat(),
                    price_aud_mwh=float(row['price']) if pd.notna(row['price']) else 0.0
                )
                for _, row in df.iterrows()
            ]
            
            # Run the math engine and return the result to React!
            return calculate_optimal_dispatch(battery, market_data)

    except Exception as e:
        return {"status": "error", "message": str(e)}
    



# include router in the app 
app.include_router(router)