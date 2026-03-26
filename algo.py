from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json

class Trader:
    
    def run(self, state: TradingState):
        result = {}
        
        # Load state
        if state.traderData == "" or state.traderData == "SAMPLE":
            data = {"TOMATOES_EWMA": None}
        else:
            try:
                data = json.loads(state.traderData)
            except:
                data = {"TOMATOES_EWMA": None}
                
        tomato_ewma = data.get("TOMATOES_EWMA", None)
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            # ----------------------------------------------------
            # EMERALDS STRATEGY (Stationary, Inventory Skewing)
            # ----------------------------------------------------
            if product == 'EMERALDS':
                fair_value = 10000
                position = state.position.get('EMERALDS', 0)
                limit = 20
                
                # Base quoting spreads
                buy_edge = fair_value - 7 # EMERALDS_SPREAD
                sell_edge = fair_value + 7 # EMERALDS_SPREAD
                
                # Dynamic Inventory Risk Control
                if position > 10:
                    # We have too many items. Quote tighter to sell, wider to buy.
                    buy_edge -= 1
                    sell_edge -= 1
                elif position < -10:
                    # We are too short. Quote tighter to buy, wider to sell.
                    buy_edge += 1
                    sell_edge += 1

                # Market Sweeping (Always grab obvious profit)
                if len(order_depth.sell_orders) > 0:
                    best_ask, best_ask_amount = min(order_depth.sell_orders.items())
                    if int(best_ask) <= buy_edge:
                        vol = min(-best_ask_amount, limit - position)
                        if vol > 0:
                            orders.append(Order(product, best_ask, vol))
                            position += vol
                            
                if len(order_depth.buy_orders) > 0:
                    best_bid, best_bid_amount = max(order_depth.buy_orders.items())
                    if int(best_bid) >= sell_edge:
                        vol = min(best_bid_amount, position + limit)
                        if vol > 0:
                            orders.append(Order(product, best_bid, -vol))
                            position -= vol

                # Market Making (Provide liquidity)
                buy_vol = limit - position
                if buy_vol > 0:
                    orders.append(Order(product, buy_edge, buy_vol))
                
                sell_vol = limit + position
                if sell_vol > 0:
                    orders.append(Order(product, sell_edge, -sell_vol))

            # ----------------------------------------------------
            # TOMATOES STRATEGY (Trending, EWMA + Inventory Skew)
            # ----------------------------------------------------
            elif product == 'TOMATOES':
                best_ask, best_ask_amount = min(order_depth.sell_orders.items()) if len(order_depth.sell_orders) > 0 else (0, 0)
                best_bid, best_bid_amount = max(order_depth.buy_orders.items()) if len(order_depth.buy_orders) > 0 else (0, 0)
                
                # Calculate True Market Mid Build
                mid_price = None
                if best_ask > 0 and best_bid > 0:
                    mid_price = (best_ask + best_bid) / 2
                elif best_ask > 0:
                    mid_price = best_ask
                elif best_bid > 0:
                    mid_price = best_bid
                
                # EWMA logic
                alpha = 0.15  # Decay factor, determines how responsive the EWMA is
                
                if mid_price is not None:
                    if tomato_ewma is None:
                        tomato_ewma = mid_price
                    else:
                        tomato_ewma = alpha * mid_price + (1 - alpha) * tomato_ewma

                if tomato_ewma is not None:
                    # Trading for TOMATOES disabled by user request.
                    pass

            result[product] = orders
            
        data["TOMATOES_EWMA"] = tomato_ewma
        traderData = json.dumps(data)
        
        return result, 0, traderData
