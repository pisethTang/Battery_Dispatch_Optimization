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

// --- BACKTEST TYPES (GET /backtest/days, /backtest/day/{date}) ---

export type ForecastMethod = "naive" | "lightgbm" | "lstm";
export type BacktestMethod = "perfect_foresight" | ForecastMethod;

export interface MethodDay {
  charge_mw: number[];
  discharge_mw: number[];
  soc_mwh: number[];
  cumulative_profit_aud: number[];
  profit_aud: number;
}

export interface BacktestDay {
  date: string;
  intervals: string[];
  actual_price: number[];
  forecast_price: Record<ForecastMethod, number[]>;
  methods: Record<BacktestMethod, MethodDay>;
}

export interface ModelSummary {
  capture_rate: number;
  realised_aud: number;
  mae: number;
  rmse: number;
  days_with_loss: number;
}

export interface BacktestDayRow {
  date: string;
  price_max: number;
  price_min: number;
  perfect_foresight_aud: number;
  naive_aud: number;
  lightgbm_aud: number;
  lstm_aud: number;
}

export interface BacktestIndex {
  summary: {
    Z_test_days: number;
    split: { train: string[]; validation: string[]; test: string[]; retrain_every_days: number };
    battery: { capacity_mwh: number; max_mw: number; efficiency: number };
    models: Record<ForecastMethod, ModelSummary>;
    best_ml_model: ForecastMethod;
    perfect_foresight_aud: number;
  };
  best_model: ForecastMethod;
  best_day: string;
  worst_day: string;
  biggest_spike_day: string;
  definitions: Record<"best_day" | "worst_day" | "biggest_spike_day", string>;
  days: BacktestDayRow[];
}
