from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import jsonpickle


class Product:
    EMERALDS = "EMERALDS"
    TOMATOES = "TOMATOES"


PARAMS = {
    Product.EMERALDS: {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0,
        # Market making params
        "disregard_edge": 1,
        "join_edge": 2,
        "default_edge": 4,
        "soft_position_limit": 10,
        "manage_position": True,
    },
    Product.TOMATOES: {
        "take_width": 1,
        "clear_width": 0,
        "reversion_beta": -0.38,
        # Market making params
        "disregard_edge": 1,
        "join_edge": 0,
        "default_edge": 2,
        "manage_position": True,
        "soft_position_limit": 15,
    },
}


class Trader:
    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params

        self.LIMIT = {Product.EMERALDS: 80, Product.TOMATOES: 80}

    # ── Core: take +EV orders ──────────────────────────────────────────
    def take_best_orders(
        self,
        product: str,
        fair_value: float,
        take_width: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> tuple[int, int]:
        position_limit = self.LIMIT[product]

        if len(order_depth.sell_orders) != 0:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -1 * order_depth.sell_orders[best_ask]

            if not prevent_adverse or abs(best_ask_amount) <= adverse_volume:
                if best_ask <= fair_value - take_width:
                    quantity = min(best_ask_amount, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, best_ask, quantity))
                        buy_order_volume += quantity
                        order_depth.sell_orders[best_ask] += quantity
                        if order_depth.sell_orders[best_ask] == 0:
                            del order_depth.sell_orders[best_ask]

        if len(order_depth.buy_orders) != 0:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]

            if not prevent_adverse or abs(best_bid_amount) <= adverse_volume:
                if best_bid >= fair_value + take_width:
                    quantity = min(best_bid_amount, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, best_bid, -1 * quantity))
                        sell_order_volume += quantity
                        order_depth.buy_orders[best_bid] -= quantity
                        if order_depth.buy_orders[best_bid] == 0:
                            del order_depth.buy_orders[best_bid]

        return buy_order_volume, sell_order_volume

    # ── Core: place resting orders (market make) ───────────────────────
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

        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -sell_quantity))
        return buy_order_volume, sell_order_volume

    # ── Core: reduce position towards neutral ──────────────────────────
    def clear_position_order(
        self,
        product: str,
        fair_value: float,
        width: int,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> tuple[int, int]:
        position_after_take = position + buy_order_volume - sell_order_volume
        fair_for_bid = round(fair_value - width)
        fair_for_ask = round(fair_value + width)

        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)

        if position_after_take > 0:
            clear_quantity = sum(
                volume
                for price, volume in order_depth.buy_orders.items()
                if price >= fair_for_ask
            )
            clear_quantity = min(clear_quantity, position_after_take)
            sent_quantity = min(sell_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_ask, -abs(sent_quantity)))
                sell_order_volume += abs(sent_quantity)

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

    # ── Fair value: TOMATOES (midwall of bid/ask walls) ─────────────────
    def tomatoes_fair_value(self, order_depth: OrderDepth, traderObject) -> float:
        if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
            return None

        # Bid wall: price level with the largest volume on the buy side
        bid_wall = max(order_depth.buy_orders.keys(),
                       key=lambda p: order_depth.buy_orders[p])
        # Ask wall: price level with the largest volume on the sell side
        ask_wall = min(order_depth.sell_orders.keys(),
                       key=lambda p: abs(order_depth.sell_orders[p]))
        # sell_orders are negative, so largest wall = most negative
        ask_wall = max(order_depth.sell_orders.keys(),
                       key=lambda p: abs(order_depth.sell_orders[p]))

        mid_wall = (bid_wall + ask_wall) / 2

        # Mean-reversion adjustment
        if traderObject.get("tomatoes_last_price") is not None:
            last_price = traderObject["tomatoes_last_price"]
            last_returns = (mid_wall - last_price) / last_price
            pred_returns = last_returns * self.params[Product.TOMATOES]["reversion_beta"]
            fair = mid_wall + (mid_wall * pred_returns)
        else:
            fair = mid_wall

        traderObject["tomatoes_last_price"] = mid_wall
        return fair

    # ── Wrapper: take ──────────────────────────────────────────────────
    def take_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        take_width: float,
        position: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
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
            prevent_adverse,
            adverse_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    # ── Wrapper: clear ─────────────────────────────────────────────────
    def clear_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        clear_width: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> tuple[List[Order], int, int]:
        orders: List[Order] = []
        buy_order_volume, sell_order_volume = self.clear_position_order(
            product,
            fair_value,
            clear_width,
            orders,
            order_depth,
            position,
            buy_order_volume,
            sell_order_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    # ── Wrapper: make (penny/join logic) ───────────────────────────────
    def make_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        disregard_edge: float,
        join_edge: float,
        default_edge: float,
        manage_position: bool = False,
        soft_position_limit: int = 0,
    ) -> tuple[List[Order], int, int]:
        orders: List[Order] = []
        asks_above_fair = [
            price
            for price in order_depth.sell_orders.keys()
            if price > fair_value + disregard_edge
        ]
        bids_below_fair = [
            price
            for price in order_depth.buy_orders.keys()
            if price < fair_value - disregard_edge
        ]

        best_ask_above_fair = min(asks_above_fair) if asks_above_fair else None
        best_bid_below_fair = max(bids_below_fair) if bids_below_fair else None

        ask = round(fair_value + default_edge)
        if best_ask_above_fair is not None:
            if abs(best_ask_above_fair - fair_value) <= join_edge:
                ask = best_ask_above_fair  # join
            else:
                ask = best_ask_above_fair - 1  # penny

        bid = round(fair_value - default_edge)
        if best_bid_below_fair is not None:
            if abs(fair_value - best_bid_below_fair) <= join_edge:
                bid = best_bid_below_fair
            else:
                bid = best_bid_below_fair + 1

        if manage_position:
            if position > soft_position_limit:
                ask -= 1
            elif position < -1 * soft_position_limit:
                bid += 1

        buy_order_volume, sell_order_volume = self.market_make(
            product,
            orders,
            bid,
            ask,
            position,
            buy_order_volume,
            sell_order_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    # ── Main entry point ───────────────────────────────────────────────
    def run(self, state: TradingState):
        traderObject = {}
        if state.traderData and state.traderData != "":
            traderObject = jsonpickle.decode(state.traderData)

        result = {}

        # ─── EMERALDS: fixed fair value = 10000 ───────────────────────
        if Product.EMERALDS in self.params and Product.EMERALDS in state.order_depths:
            emerald_position = state.position.get(Product.EMERALDS, 0)
            ep = self.params[Product.EMERALDS]

            emerald_take, buy_vol, sell_vol = self.take_orders(
                Product.EMERALDS,
                state.order_depths[Product.EMERALDS],
                ep["fair_value"],
                ep["take_width"],
                emerald_position,
            )
            emerald_clear, buy_vol, sell_vol = self.clear_orders(
                Product.EMERALDS,
                state.order_depths[Product.EMERALDS],
                ep["fair_value"],
                ep["clear_width"],
                emerald_position,
                buy_vol,
                sell_vol,
            )
            emerald_make, _, _ = self.make_orders(
                Product.EMERALDS,
                state.order_depths[Product.EMERALDS],
                ep["fair_value"],
                emerald_position,
                buy_vol,
                sell_vol,
                ep["disregard_edge"],
                ep["join_edge"],
                ep["default_edge"],
                ep["manage_position"],
                ep["soft_position_limit"],
            )
            result[Product.EMERALDS] = emerald_take + emerald_clear + emerald_make

        # ─── TOMATOES: dynamic fair value with mean-reversion ──────────
        if Product.TOMATOES in self.params and Product.TOMATOES in state.order_depths:
            tomato_position = state.position.get(Product.TOMATOES, 0)
            tp = self.params[Product.TOMATOES]

            tomato_fair = self.tomatoes_fair_value(
                state.order_depths[Product.TOMATOES], traderObject
            )
            if tomato_fair is not None:
                tomato_take, buy_vol, sell_vol = self.take_orders(
                    Product.TOMATOES,
                    state.order_depths[Product.TOMATOES],
                    tomato_fair,
                    tp["take_width"],
                    tomato_position,
                )
                tomato_clear, buy_vol, sell_vol = self.clear_orders(
                    Product.TOMATOES,
                    state.order_depths[Product.TOMATOES],
                    tomato_fair,
                    tp["clear_width"],
                    tomato_position,
                    buy_vol,
                    sell_vol,
                )
                tomato_make, _, _ = self.make_orders(
                    Product.TOMATOES,
                    state.order_depths[Product.TOMATOES],
                    tomato_fair,
                    tomato_position,
                    buy_vol,
                    sell_vol,
                    tp["disregard_edge"],
                    tp["join_edge"],
                    tp["default_edge"],
                    tp["manage_position"],
                    tp["soft_position_limit"],
                )
                result[Product.TOMATOES] = tomato_take + tomato_clear + tomato_make

        conversions = 1
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData