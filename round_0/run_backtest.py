import sys
import pandas as pd
from datamodel import Listing
from backtester import Backtester
from round_0_v2 import Trader

# --- Load data ---
DATA_DIR = "../TUTORIAL_ROUND_1"

DAYS = [-2, -1]  # change to [-2] or [-1] to test on a single day

prices_dfs = []
trades_dfs = []
for day in DAYS:
    pdf = pd.read_csv(f"{DATA_DIR}/prices_round_0_day_{day}.csv", sep=";")
    prices_dfs.append(pdf)
    tdf = pd.read_csv(f"{DATA_DIR}/trades_round_0_day_{day}.csv", sep=";")
    tdf.rename(columns={"symbol": "symbol"}, inplace=True)
    trades_dfs.append(tdf)

market_data = pd.concat(prices_dfs, ignore_index=True)
trade_history = pd.concat(trades_dfs, ignore_index=True)
print(f"Running on days: {DAYS}")

# --- Config ---
listings = {
    "EMERALDS": Listing("EMERALDS", "EMERALDS", "SEASHELLS"),
    "TOMATOES": Listing("TOMATOES", "TOMATOES", "SEASHELLS"),
}

position_limits = {
    "EMERALDS": 80,
    "TOMATOES": 80,
}

fair_marks = {
    "EMERALDS": lambda od: 10000,
}

# --- Run ---
trader = Trader()
bt = Backtester(
    trader=trader,
    listings=listings,
    position_limit=position_limits,
    fair_marks=fair_marks,
    market_data=market_data,
    trade_history=trade_history,
    file_name="backtest_output.log",
)

bt.run()

# --- Print summary ---
print(f"Final PnL by product:")
for product, pnl in bt.pnl.items():
    print(f"  {product}: {pnl:.2f}")
print(f"  TOTAL:    {sum(v for v in bt.pnl.values() if v is not None):.2f}")
print(f"\nFinal positions: {bt.cash}")
print(f"Positions:       {bt.current_position}")
print(f"Own trades:      {sum(1 for t in bt.trades if t['buyer'] == 'SUBMISSION' or t['seller'] == 'SUBMISSION')}")
print(f"\nFull log written to backtest_output.log")
