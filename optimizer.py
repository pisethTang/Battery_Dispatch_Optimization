import csv 
import pulp 


# read csv 
prices = []
with open("market_data.csv", mode="r") as file:
    reader = csv.DictReader(file)
    for row in reader:
        prices.append(float(row["price_aud"]))

T = len(prices) # 48 intervals 
dt = 0.5 # 30-minute per interval 


# battery Limits
capacity = 5.0  # Increased from 2.0
max_mw = 2.5    # Increased from 1.0
efficiency = 0.9


# setup the math problem

prob = pulp.LpProblem("Battery_Test", pulp.LpMaximize)


# create all constaint variables 
charge = pulp.LpVariable.dicts("Charge", range(T), lowBound=0, upBound=max_mw)
discharge = pulp.LpVariable.dicts("Discharge", range(T), lowBound=0, upBound=max_mw)
soc = pulp.LpVariable.dicts("SoC", range(T), lowBound=0, upBound=capacity)


# objective function
profit = pulp.lpSum([
    (discharge[t] - charge[t]) * prices[t] * dt
    for t in range(T)
])

prob += profit




# need to understand this piece of code. 
# constraints (from the battery physics)
for t in range(T):
    if t == 0:
        # start empty 
        prob += soc[t] == (charge[t] * efficiency - discharge[t]) * dt 
    else:
        # 
        prob += soc[t] == soc[t-1] + (charge[t] * efficiency - discharge[t]) * dt


# 
prob.solve(pulp.PULP_CBC_CMD(msg=False))


# print the result 
print(f"Optimization Status: {pulp.LpStatus[prob.status]}")
print(f"Total Profit: ${pulp.value(prob.objective):.2f}")

# testing: print the exact actions it took at 6pm (interval 36)
print(f"\n At 18:00 (Evening Peak): ")
print(f"Discharging: {discharge[36].varValue} MW")
print(f"Charging: {charge[36].varValue} MW")
print(f"SoC: {soc[36].varValue} MWh")


#
