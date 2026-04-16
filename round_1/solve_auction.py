#!/usr/bin/env python3
"""
Auction Order Book Optimizer v2
─────────────────────────────────
Key fix: volume granularity dropped to 1 unit, and price range extended.
Queue logic: price priority applies BEFORE time priority.
A bid at a price HIGHER than all existing bids jumps to the front of the queue.
"""

EXISTING_BIDS = [(30, 30_000), (29, 5_000), (28, 12_000), (27, 28_000)]
EXISTING_ASKS = [(28, 40_000), (31, 20_000), (32, 20_000), (33, 30_000)]
COVER_PRICE   = 30

# ── Depth helpers ─────────────────────────────────────────────────────────────
def cum_bids(bids, price):
    return sum(v for p, v in bids if p >= price)

def cum_asks(asks, price):
    return sum(v for p, v in asks if p <= price)

# ── Clearing price ─────────────────────────────────────────────────────────────
def find_clearing_price(bids, asks):
    candidates = sorted(set(p for p, _ in bids) | set(p for p, _ in asks))
    best_price, best_vol = None, -1
    for p in candidates:
        vol = min(cum_bids(bids, p), cum_asks(asks, p))
        if vol > best_vol or (vol == best_vol and (best_price is None or p > best_price)):
            best_vol, best_price = vol, p
    return best_price, best_vol

# ── Fill calculation ──────────────────────────────────────────────────────────
def compute_our_fill(side, our_price, our_vol, clearing_price, bids_with_us, asks_with_us):
    """
    Price priority → time priority.
    We are LAST in time at our price level.
    All EXISTING orders at BETTER prices AND same price are ahead of us.

    For a BID:
      - "Better" means higher price (willing to pay more → higher priority)
      - Existing bids at prices STRICTLY > our_price get filled before us
      - Existing bids at our_price also get filled before us (earlier time)
      - So: ahead = all existing bids at price >= our_price
    """
    if our_price < clearing_price and side == 'bid':
        return 0
    if our_price > clearing_price and side == 'ask':
        return 0

    if side == 'bid':
        cb = cum_bids(bids_with_us, clearing_price)
        ca = cum_asks(asks_with_us, clearing_price)
        T  = min(cb, ca)
        if cb <= ca:
            # Bids are short side — every eligible bid gets filled
            return our_vol
        # Bids are long side — queue matters
        ahead = sum(v for p, v in EXISTING_BIDS if p >= our_price)
        return min(our_vol, max(0, T - ahead))
    else:
        cb = cum_bids(bids_with_us, clearing_price)
        ca = cum_asks(asks_with_us, clearing_price)
        T  = min(cb, ca)
        if ca <= cb:
            return our_vol
        ahead = sum(v for p, v in EXISTING_ASKS if p <= our_price)
        return min(our_vol, max(0, T - ahead))

# ── Evaluator ─────────────────────────────────────────────────────────────────
def evaluate(side, price, vol):
    if side == 'bid':
        bids_w, asks_w = EXISTING_BIDS + [(price, vol)], EXISTING_ASKS
    else:
        bids_w, asks_w = EXISTING_BIDS, EXISTING_ASKS + [(price, vol)]

    cp, _ = find_clearing_price(bids_w, asks_w)
    fill   = compute_our_fill(side, price, vol, cp, bids_w, asks_w)
    profit = fill * (COVER_PRICE - cp if side == 'bid' else cp - COVER_PRICE)
    return profit, fill, cp

# ── Grid search ───────────────────────────────────────────────────────────────
# Prices: wide range.
# Volumes: coarse pass first, then fine-tune around interesting thresholds.

PRICE_RANGE = range(26, 40)

print("Running coarse search (step=100)...")
results = []
for side in ('bid', 'ask'):
    for price in PRICE_RANGE:
        for vol in range(100, 500_001, 100):
            profit, fill, clearing = evaluate(side, price, vol)
            results.append((profit, side, price, vol, fill, clearing))

results.sort(key=lambda x: -x[0])
best_coarse = results[0]
print(f"Coarse best: {best_coarse[1].upper()} ${best_coarse[2]} × {best_coarse[3]:,}  "
      f"→ fill {best_coarse[4]:,} @ ${best_coarse[5]}  profit=${best_coarse[0]:,.0f}")

# Fine search: ±5000 units around the coarse optimum at the best prices
print("\nRunning fine search (step=1) near optimal region...")
fine_results = []
_, best_side, best_price_c, best_vol_c, _, _ = best_coarse

# Collect unique (side, price) combos from top 20 coarse results
candidates = list(dict.fromkeys((r[1], r[2]) for r in results[:20]))

for side, price in candidates:
    lo = max(1, best_vol_c - 5_000)
    hi = best_vol_c + 5_000
    for vol in range(lo, hi + 1):
        profit, fill, clearing = evaluate(side, price, vol)
        fine_results.append((profit, side, price, vol, fill, clearing))

fine_results.sort(key=lambda x: -x[0])

# ── Baseline ──────────────────────────────────────────────────────────────────
base_cp, base_vol = find_clearing_price(EXISTING_BIDS, EXISTING_ASKS)

print("\n" + "=" * 70)
print("CLEARING PRICE SWEEP (existing book only)")
print(f"  {'Price':>6}  {'CumBid':>9}  {'CumAsk':>9}  {'Traded':>9}")
all_ps = sorted(set(p for p,_ in EXISTING_BIDS)|set(p for p,_ in EXISTING_ASKS))
for p in all_ps:
    marker = "  ← baseline clearing" if p == base_cp else ""
    print(f"  ${p:>5}  {cum_bids(EXISTING_BIDS,p):>9,}  "
          f"{cum_asks(EXISTING_ASKS,p):>9,}  "
          f"{min(cum_bids(EXISTING_BIDS,p),cum_asks(EXISTING_ASKS,p)):>9,}{marker}")

print("\n" + "=" * 70)
print("TOP 15 ORDERS (coarse search, step=100)")
print("-" * 70)
print(f"  {'#':>2}  {'Side':>4}  {'Price':>6}  {'Volume':>9}  {'Fill':>9}  {'Clear':>6}  {'Profit':>10}")
seen = set()
rank = 0
for row in results:
    key = (row[1], row[2], row[5])   # side, price, clearing — show unique combos
    if key not in seen:
        seen.add(key)
        rank += 1
        profit, side, price, vol, fill, clearing = row
        print(f"  {rank:>2}  {side.upper():>4}  ${price:>5}  {vol:>9,}  "
              f"{fill:>9,}  ${clearing:>5}  ${profit:>9,.0f}")
    if rank >= 15:
        break

print("\n" + "=" * 70)
print("TOP 10 ORDERS (fine search, step=1)")
print("-" * 70)
print(f"  {'#':>2}  {'Side':>4}  {'Price':>6}  {'Volume':>9}  {'Fill':>9}  {'Clear':>6}  {'Profit':>10}")
for i, (profit, side, price, vol, fill, clearing) in enumerate(fine_results[:10], 1):
    print(f"  {i:>2}  {side.upper():>4}  ${price:>5}  {vol:>9,}  "
          f"{fill:>9,}  ${clearing:>5}  ${profit:>9,.0f}")

# ── Optimal ───────────────────────────────────────────────────────────────────
best = fine_results[0]
bp, bside, bprice, bvol, bfill, bclearing = best
print("\n" + "=" * 70)
print("OPTIMAL ORDER")
print("-" * 70)
print(f"  Action          : {bside.upper()}")
print(f"  Limit price     : ${bprice}")
print(f"  Volume          : {bvol:,}")
print(f"  Resulting clear : ${bclearing}")
print(f"  Our fill        : {bfill:,}")
margin = COVER_PRICE - bclearing if bside=='bid' else bclearing - COVER_PRICE
print(f"  Profit          : ${bp:,.0f}  (${margin}/unit × {bfill:,} units)")
print("=" * 70)

# ── Show the cliff: profit vs volume at optimal price ─────────────────────────
print(f"\nPROFIT CLIFF  –  {bside.upper()} @ ${bprice}  (fine-grain near threshold)")
print(f"  {'Volume':>9}  {'Clearing':>8}  {'Fill':>9}  {'Profit':>10}")
prev_cp = None
for vol in range(max(1, bvol - 3000), bvol + 3001):
    p, f, cp = evaluate(bside, bprice, vol)
    if cp != prev_cp or vol in (bvol,):
        print(f"  {vol:>9,}  ${cp:>7}  {f:>9,}  ${p:>9,.0f}   {'← OPTIMAL' if vol==bvol else '← cliff' if prev_cp and cp!=prev_cp else ''}")
        prev_cp = cp