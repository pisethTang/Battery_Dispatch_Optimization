import pytest 
from fastapi.testclient import TestClient
from datetime import datetime, timezone 
from main import app, calculate_optimal_dispatch, BatterySpecs, MarketInterval





client = TestClient(app)




# --- 1. UNIT TEST: The Math Engine ---
def test_calculate_optimal_dispatch_basic_arbitrage():
    # Setup a perfectly efficient battery for easy math
    battery = BatterySpecs(capacity_mwh=2.0, max_mw=1.0, efficiency=1.0) 
    market_data = [
        MarketInterval(timestamp=datetime.now(timezone.utc), price_aud_mwh=10.0),  # Cheap
        MarketInterval(timestamp=datetime.now(timezone.utc), price_aud_mwh=10.0),  # Cheap
        MarketInterval(timestamp=datetime.now(timezone.utc), price_aud_mwh=100.0), # Expensive
        MarketInterval(timestamp=datetime.now(timezone.utc), price_aud_mwh=100.0), # Expensive
    ]
    
    result = calculate_optimal_dispatch(battery, market_data)
    
    # The Math: 

    #  Wrong assertion
    # Charge 1MW for 1 hour (2 blocks) at $10/MWh = Costs $20 to get 2MWh
    # Discharge 1MW for 1 hour at $100/MWh = Earns $200
    # Expected Profit: $200 - $20 = $180
    # assert result["total_profit_aud"] == 180.0
    # ----------------


    # The Math: 
    # Charge 1.0 MW for 1 hour (2 blocks) = 1.0 MWh total energy
    # Cost: 1.0 MWh * $10 = $10
    # Discharge: 1.0 MWh * $100 = $100
    # Expected Profit: $100 - $10 = $90
    assert result["total_profit_aud"] == 90.0
    assert result["schedule"][0]["charge_mw"] == 1.0 # Should charge in the first block




# --- 2. INTEGRATION TEST: The API Endpoint ---
def test_optimize_endpoint_success():
    payload = {
        "battery": {
            "capacity_mwh": 5.0,
            "max_mw": 2.5,
            "efficiency": 0.9
        },
        "market_data": [
            {"timestamp": "2026-03-24T10:00:00Z", "price_aud_mwh": 10.0},
            {"timestamp": "2026-03-24T10:30:00Z", "price_aud_mwh": 150.0}
        ]
    }
    
    # Send a fake POST request to your API
    response = client.post("/api/v1/optimize", json=payload)
    
    # Assert the server responded with 200 OK
    assert response.status_code == 200
    
    # Assert the JSON structure is exactly what we expect
    data = response.json()
    assert data["status"] == "success"
    assert "total_profit_aud" in data["data"]
    assert len(data["data"]["schedule"]) == 2




# --- 3. EDGE CASE TEST: Pydantic Validation ---
def test_optimize_endpoint_invalid_battery():
    payload = {
        "battery": {
            "capacity_mwh": -5.0, # INVALID: Capacity cannot be negative!
            "max_mw": 2.5,
            "efficiency": 0.9
        },
        "market_data": [
            {"timestamp": "2026-03-24T10:00:00Z", "price_aud_mwh": 10.0}
        ]
    }
    
    response = client.post("/api/v1/optimize", json=payload)
    
    # Pydantic should intercept this bad data and return a 422 Unprocessable Entity error
    # before it ever reaches the PuLP math engine.
    assert response.status_code == 422