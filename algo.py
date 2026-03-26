from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict, Tuple
import json

class Trader:

    def take_best_orders(self, product: str, order_depth: OrderDepth, buy_edge: int, sell_edge: int, position: int, limit: int) -> Tuple[List[Order], int]:
        """Fill any orders on the book that are better than our required edges."""
        orders: List[Order] = []
        
        # Take Sells (Buy)
        if len(order_depth.sell_orders) > 0:
            ask_iter = sorted(order_depth.sell_orders.items())
            for ask, ask_qty in ask_iter:
                if ask <= buy_edge:
                    vol = min(-ask_qty, limit - position)
                    if vol > 0:
                        orders.append(Order(product, ask, vol))
                        position += vol

        # Take Bids (Sell)
        if len(order_depth.buy_orders) > 0:
            bid_iter = sorted(order_depth.buy_orders.items(), reverse=True)
            for bid, bid_qty in bid_iter:
                if bid >= sell_edge:
                    vol = min(bid_qty, position + limit)
                    if vol > 0:
                        orders.append(Order(product, bid, -vol))
                        position -= vol
        
        return orders, position

    def market_make(self, product: str, buy_edge: int, sell_edge: int, position: int, limit: int) -> List[Order]:
        """Place passive orders on the book to provide liquidity."""
        orders: List[Order] = []
        
        buy_vol = limit - position
        if buy_vol > 0:
            orders.append(Order(product, buy_edge, buy_vol))
        
        sell_vol = limit + position
        if sell_vol > 0:
            orders.append(Order(product, sell_edge, -sell_vol))
            
        return orders

    def reduce_position(self, buy_edge: int, sell_edge: int, position: int, threshold: int = 10) -> Tuple[int, int]:
        """Skew edges to encourage trades that reduce our current position."""
        if position > threshold:
            # Too long: quote tighter to sell, wider to buy.
            buy_edge -= 1
            sell_edge -= 1
        elif position < -threshold:
            # Too short: quote tighter to buy, wider to sell.
            buy_edge += 1
            sell_edge += 1
        return buy_edge, sell_edge

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
            position = state.position.get(product, 0)
            limit = 20

            if product == 'EMERALDS':
                fair_value = 10000
                buy_edge = fair_value - 7 # EMERALDS_SPREAD
                sell_edge = fair_value + 7 # EMERALDS_SPREAD
                
                # 1. Apply multi-stage inventory skewing
                buy_edge, sell_edge = self.reduce_position(buy_edge, sell_edge, position)

                # 2. Take profitable orders
                take_orders, position = self.take_best_orders(product, order_depth, buy_edge, sell_edge, position, limit)
                orders.extend(take_orders)

                # 3. Market make
                mm_orders = self.market_make(product, buy_edge, sell_edge, position, limit)
                orders.extend(mm_orders)

            elif product == 'TOMATOES':
                # EWMA logic for price tracking
                best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
                best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
                
                mid_price = None
                if best_ask is not None and best_bid is not None:
                    mid_price = (best_ask + best_bid) / 2
                elif best_ask is not None:
                    mid_price = best_ask
                elif best_bid is not None:
                    mid_price = best_bid
                
                alpha = 0.15
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
