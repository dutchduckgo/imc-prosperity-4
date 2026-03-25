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

    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        