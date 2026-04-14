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
        "default_edge": 7,
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
    ) -> tuple[int, int]:
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
        self,
        product: str,
        orders: List[Order],
        bid: int,
        ask: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> tuple[int, int]:
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, round(bid), buy_quantity))
        
        sell_quantity = self.LIMIT[product] - (sell_order_volume - position)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -1 * sell_quantity))

        return buy_order_volume, sell_order_volume
    
    def reduce_position(
        self,
        product: str,
        fair_value: float,
        width: int,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> List[Order]:
        position_after_take = position + buy_order_volume - sell_order_volume
        fair_for_bid = round(fair_value - width)
        fair_for_ask = round(fair_value + width)

        # remaining room to buy more
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume) 

        if position_after_take > 0:
            clear_quantity = sum(
                volume
                for price, volume in order_depth.buy_orders.items()
                if price >= fair_for_ask
            )
            clear_quantity = min(clear_quantity, position_after_take)
            sell_quantity = min(sell_quantity, clear_quantity)
            if sell_quantity > 0:
                orders.append(Order(product, fair_for_ask, -1 * sell_quantity))
                sell_order_volume += sell_quantity

        if position_after_take < 0:
            clear_quantity = sum(
                abs(volume)
                for price, volume in order_depth.sell_orders.items()
                if price <= fair_for_bid
            )
            clear_quantity = min(clear_quantity, abs(position_after_take))
            sent_quantity = min(buy_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_bid, abs(sent_quantity)))
                buy_order_volume += abs(sent_quantity)

        return buy_order_volume, sell_order_volume


    def take_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        take_width: float,
        position: int,
    ) -> tuple[List[Order], int, int]:
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0

        buy_order_volume, sell_order_volume = self.take_best_orders(
            product,
            fair_value,
            take_width,
            orders,
            order_depth,
            position,
            buy_order_volume,
            sell_order_volume,
        )

        return orders, buy_order_volume, sell_order_volume



    
    def run(self, state: TradingState):
        traderObject = {}
        if state.traderData != None and state.traderData != "":
            traderObject = jsonpickle.decode(state.traderData)

        result = {}

        if Product.EMERALDS in self.params and Product.EMERALDS in state.order_depths:
            emerald_position = (
                state.position[Product.EMERALDS]
                if Product.EMERALDS in state.position
                else 0
            )
            emerald_take_orders, buy_order_volume, sell_order_volume = self.take_orders(
                Product.EMERALDS,
                state.order_depths[Product.EMERALDS],
                self.params[Product.EMERALDS]["fair_value"],
                self.params[Product.EMERALDS]["take_width"],
                emerald_position,
            )

            emerald_clear_orders = []
            buy_order_volume, sell_order_volume = self.reduce_position(
                Product.EMERALDS,
                self.params[Product.EMERALDS]["fair_value"],
                self.params[Product.EMERALDS]["clear_width"],
                emerald_clear_orders,
                state.order_depths[Product.EMERALDS],
                emerald_position,
                buy_order_volume,
                sell_order_volume,
            )

            emerald_make_orders = []
            self.market_make(
                Product.EMERALDS,
                emerald_make_orders,
                self.params[Product.EMERALDS]["fair_value"] - self.params[Product.EMERALDS]["default_edge"],
                self.params[Product.EMERALDS]["fair_value"] + self.params[Product.EMERALDS]["default_edge"],
                emerald_position,
                buy_order_volume,
                sell_order_volume,
            )

            result[Product.EMERALDS] = emerald_take_orders + emerald_clear_orders + emerald_make_orders

        traderData = jsonpickle.encode(traderObject)
        conversions = 1
        return result, conversions, traderData

        

