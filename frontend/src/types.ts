// request types (fe -> be)


export interface BatterySpecs {
    capacity_mwh: number; 
    max_mw: number;
    efficiency: number;
}


export interface MarketInterval{
    timestamp: string;
    price_aud_mwh: number;
}


export interface DispatchRequest {
    battery: BatterySpecs;
 
       market_data: MarketInterval[];
}





// --- RESPONSE TYPES (Backend -> Frontend) ---

export interface ScheduleAction {
  timestamp: string;
  price_aud_mwh: number;
  charge_mw: number;
  discharge_mw: number;
  soc_mwh: number;
}

export interface OptimizationData {
  optimization_status: string;
  total_profit_aud: number;
  schedule: ScheduleAction[];
}

export interface ApiResponse {
  status: string;
  data: OptimizationData;
}