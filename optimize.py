import subprocess
import re

def set_spread(buy_spread, sell_spread, marker="EMERALDS_SPREAD"):
    with open('/Users/kavish.muthum/IMC/imc-prosperity-4/algo.py', 'r') as f:
        content = f.read()
    content = re.sub(rf'buy_edge = fair_value - \d+ # {marker}', f'buy_edge = fair_value - {buy_spread} # {marker}', content)
    content = re.sub(rf'sell_edge = fair_value \+ \d+ # {marker}', f'sell_edge = fair_value + {sell_spread} # {marker}', content)
    with open('/Users/kavish.muthum/IMC/imc-prosperity-4/algo.py', 'w') as f:
        f.write(content)

best_profit = -1e9
best_spread = 0

print("Finding optimal spread for TOMATOES...")
for spread in range(1, 15):
    set_spread(spread, spread, marker="TOMATOES_SPREAD")
    
    res = subprocess.run(['prosperity4btx', '/Users/kavish.muthum/IMC/imc-prosperity-4/algo.py', '0', '--data', '/Users/kavish.muthum/IMC/imc-prosperity-4/data', '--out', '/Users/kavish.muthum/IMC/imc-prosperity-4/run_temp.log'], capture_output=True, text=True)
    
    profits = re.findall(r'Total profit: ([\d,]+|-[\d,]+)', res.stdout)
    if profits:
        total_profit = int(profits[-1].replace(',', ''))
        print(f"Spread ±{spread}: {total_profit} Shells")
        
        if total_profit > best_profit:
            best_profit = total_profit
            best_spread = spread
        elif total_profit < best_profit:
            # Profit started to decline, but let's check one more just in case it's noisy
            pass 

print(f"\nFinal optimal spread for TOMATOES was ±{best_spread} yielding {best_profit} Shells.")
set_spread(best_spread, best_spread, marker="TOMATOES_SPREAD")
