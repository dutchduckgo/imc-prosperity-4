# imc-prosperity-4

Writeup

For class Trader, we need:

(wrapper function -> logic)

### take_orders -> take_best_orders
Fill any orders that are +EV

### make_orders -> market_make
Market make

### clear_orders -> reduce_position
We want to maintain a neutral position, and we want to make 0 EV trades to achieve this sometimes. This is not just out of principle, but I've read that sometimes there are very profitable trades that you want to take a max position on; when that happens, you would like to already have an empty position.
