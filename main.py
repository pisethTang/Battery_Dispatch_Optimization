from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field 
from typing import List, cast 
from datetime import datetime 
# import numpy as np


# import math 

# linear programming lib
import pulp 





# initialize the api 
app = FastAPI(
    title="Battery Dispatch Optimization API",
    description="Calculates optimal charge/discharge schedules against 30-minute spot prices",
    version="1.0.0"
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

    return {
        "optimization_status": pulp.LpStatus[prob.status],
        "total_profit_aud": total_profit_aud,
        "schedule": schedule
    }
















# endpoints 

@app.post("/api/v1/optimize")
async def optimize_dispatch(request: DispatchRequest):
    try:
        # Pass the validated JSON data directly into the math engine
        result = calculate_optimal_dispatch(request.battery, request.market_data)
        return {"status": "success", "data": result}
    except Exception as e:
        # If the math fails, return a clean 500 error to the client
        raise HTTPException(status_code=500, detail=str(e))




# @app.post("/api/v1/optimize")
# async def optimize_dispatch(request: DispatchRequest):
#     """
#     Accepts battery specs and a 24-hour price forecast.
#     Currently returns the validated payload. Optimization logic coming next.
#     """
    
#     # For now, we just prove the data made it through validation safely
#     interval_count = len(request.market_data)
    
#     return {
#         "status": "success",
#         "message": f"Successfully received battery specs and {interval_count} pricing intervals.",
#         "received_battery_capacity": request.battery.capacity_mwh
#     }


