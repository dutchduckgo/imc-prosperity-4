from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np
import math

class Product:
    EMERALDS = "EMERALDS"
    TOMATOES = "TOMATOES"

class Trader:
    
