from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PRICES_PATH = DATA_DIR / "sa1_prices.parquet"
RESULTS_DIR = ROOT / "results"
DAILY_DIR = RESULTS_DIR / "daily"
MODELS_DIR = RESULTS_DIR / "models"

REGION = "SA1"
# first month of history to download from AEMO NEMWeb
HISTORY_START = "2019-01"

INTERVALS_PER_DAY = 48
DT_HOURS = 0.5

# battery used for every backtest day: the React app's default sliders + the API's default efficiency
BATTERY_CAPACITY_MWH = 5.0
BATTERY_MAX_MW = 2.5
BATTERY_EFFICIENCY = 0.9

# walk-forward split (all in NEM market time, AEST)
TEST_DAYS = 365
VALIDATION_MONTHS = 3
RETRAIN_EVERY_DAYS = 30

SEED = 42

METHODS = ["perfect_foresight", "naive", "lightgbm", "lstm"]
