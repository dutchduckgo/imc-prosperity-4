from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np
import math

class Product:
    EMERALDS = "EMERALDS"
    TOMATOES = "TOMATOES"

PARAMS = {
    Product.EMERALDS: {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0,
    },
    Product.TOMATOES: {
        "take_width": 1,
        "clear_width": 0,
    },
}

class Trader:

    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params

        self.LIMIT = {Product.EMERALDS: 80, Product.TOMATOES: 80}

    def take_best_orders(
            self,
        product: str,
        fair_value: int,
        take_width: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> (int, int):
        position_limit = self.LIMIT[product]

        if len(order_depth.sell_orders) > 0:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_volume = -1 * order_depth.sell_orders[best_ask]

            if best_ask <= fair_value - take_width:
                quantity = min(best_ask_volume, position_limit - position)

                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity
                    order_depth.sell_orders[best_ask] += quantity
                    if order_depth.sell_orders[best_ask] == 0:
                        del order_depth.sell_orders[best_ask]
        
        if len(order_depth.buy_orders) > 0:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_volume = order_depth.buy_orders[best_bid]

            if best_bid >= fair_value + take_width:
                quantity = min(best_bid_volume, position_limit + position) 

                if quantity > 0:
                    orders.append(Order(product, best_bid, -1 * quantity))
                    sell_order_volume += quantity
                    order_depth.buy_orders[best_bid] -= quantity
                    if order_depth.buy_orders[best_bid] == 0:
                        del order_depth.buy_orders[best_bid]
        
        return buy_order_volume, sell_order_volume
    
    def market_make(
            
    )



    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        