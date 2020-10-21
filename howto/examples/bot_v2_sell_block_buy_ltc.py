#!/usr/bin/env python3

# ~ MIT License

# ~ Copyright (c) 2020 FAZER

# ~ Permission is hereby granted, free of charge, to any person obtaining a copy
# ~ of this software and associated documentation files (the "Software"), to deal
# ~ in the Software without restriction, including without limitation the rights
# ~ to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# ~ copies of the Software, and to permit persons to whom the Software is
# ~ furnished to do so, subject to the following conditions:

# ~ The above copyright notice and this permission notice shall be included in all
# ~ copies or substantial portions of the Software.

# ~ THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# ~ IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# ~ FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# ~ AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# ~ LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# ~ OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# ~ SOFTWARE.


botconfig = str(
#bot is configured to sell(maker) Blocknet for Litecoin
    "--maker BLOCK"
    "--taker LTC"

#your addresses
    "--makeraddress blocknet_addr_is_missing_here"
    "--takeraddress litecoin_addr_is_missing_here"

#limit bot to use and compute funds only from maker and taker address(default=False disabled)
    # ~ "--address_only True"

#do not save any maker balance
    "--balancesavenumber 0 --balancesavepercent 0"
  
#bot will try to create orders with dynamic size if there is no balance available to create order at maximum. but only between <value, min value>
#also takerbot is accepting at least order with size in range between <value, min value>
    # lets say size of orders are set in USDT
        # ~ "--sell_size_asset USDT"
    # lets say size of orders are set in BLOCK
        "--sell_size_asset BLOCK"
    #first placed order at maker size min 15 up to max 100 by available balance
        "--sellstart 100.0 --sellstartmin 15.0"
    #last placed order at maker size min 15 up to max 50 by available balance
        "--sellend 50.0 --sellendmin 15.0"

# maximum exponential to 0 means linear to 1 means maximum logarithmic. Recommended middle range log and exp values are 0.8 and -0.45 (default=0 linear)
    # ~ "--sell_type 0.45"

# EXAMPLE INFOGRAPHIC:
#      ^
#      |                                                
# O    |                                              8  > order number #1 up to order number #8 with LINEAR --sell_type 0 order amount distribution
# R    |                                           7  | 
# D    |                                        6  |--| 
# E    |                                     5  |--|--| 
# R S  |                                  4  |--|--|--| 
#   I  |                               3  |--|--|--|--| 
#   Z  |                            2  |--|--|--|--|--| 
#   E  |                         1  |--|--|--|--|--|--| 
#      |                         |--|--|--|--|--|--|--| 
#      ------------------------------------------------------>
#                                ^                        price
#                          center price
#

#      ^
#      |                                                
# O    |                                           7  8  > order number #1 up to order number #8 with EXPONENTIAL --sell_type -0.45 order amount distribution
# R    |                                           |--| 
# D    |                                        6  |--| 
# E    |                                        |--|--| 
# R S  |                                     5  |--|--| 
#   I  |                                     |--|--|--| 
#   Z  |                                  4  |--|--|--| 
#   E  |                         1  2  3  |--|--|--|--| 
#      |                         |--|--|--|--|--|--|--| 
#      ------------------------------------------------------>
#                                ^                        price
#                          center price
#

#configure bot to have 3 orders opened.
#all other orders between first and last order are automatically recomputed by number of orders and linearly distributed between <sellstart, sellstartmin> and <sellend, sellendmin>
#so if bot have order size from <1> up to <6> and max number of orders is 3 middle will be 3.5, so orders will be <1> <3.5> <6>
    "--maxopen 3"

#create next order on 0 amount hit, so if first order is not created, rather skipped, next is created(default=False disabled)
    # ~ "--make_next_on_hit True"

#enable or disable partial orders. Partial orders minimum is set by <sellstartmin> <sellendmin> along with dynamic size of orders(default=False disabled)
    "--partial_orders True"

#first order at price slide to 110%(if price is 1 USD final is 1.10 USD), second order with price slide 106.5% and last order with price slide to 103%
    "--slidestart 1.10 --slideend 1.03"

#no pump order. pump and dump orders are very useful, in case of pump you can buy back more and cheap.
    "--slidepump 0 --pumpamount 0 --pumpamountmin 0"

#enabled dynamic slide based on maker amount. Dynamic slide -1 means autoconfigured to value 0 at bot start with actual amount when bot started
    "--slidedyntype static --slidedynzero -1"
    #dynamic slide is ignored(not applied) when maker balance change -+0.2%. dynamic slide will reach max at +-80%
        "--slidedynzoneignore 0.02 --slidedynzonemax 0.8"
    #in case when selling more and more maker than opposite bot(if any), so balance of maker is less and less, means interest for maker is more and more, so prediction of maker price is will go up.
    #so order price can be increated more and more, so final price of last order can possibly reach value = price*(1.01+0.20)
        "--slidedynpositive 0.20"
    #in case when selling less and less maker than opposite bot(if any), so balance of maker is more and more, means interest for maker is less and less, so prediction of maker price is will go down.
    #handling #1 if this situation is, bot can be configured as expectation that price will go back. so bot will increase price in spite of interest of maker is going down.
        "--slidedynnegative 0.15"
    #handling #2 of this situation is, bot can be configured to slightly decrease final price of maker order.
        # ~ "--slidedynnegative -0.01 --imreallysurewhatimdoing"

#recreate order when 2 orders are accepted
    "--reopenfinishednum 2"
#recreate orders by 600seconds timeout of last taken/accepted order
    "--reopenfinisheddelay 600"

#reset all orders on positive +0.1% price change, but on negative price change, reset only when will reach -0.5% price change
    "--resetonpricechangepositive 0.01 --resetonpricechangenegative 0.05"

#do not reset all orders at timer, reset all orders when 3 orders are taken/accepted, do not reset orders on timer when some order is accepted
    "--resetafterdelay 0 --resetafterorderfinishnumber 3 --resetafterorderfinishdelay 0"

#boundaries configuration:
    #do not exit bot when boundary reached
        "--boundary_max_noexit --boundary_min_noexit"
    #cancel orders on max boundary. The reason can be user is not willing to continue selling his maker-asset once price is too high and user i.e rather continue staking
        # ~ "--boundary_max_nocancel"
    #do not cancel orders on min boundary, but rather keep open orders on minimum boundary. The reason can be user is not willing to sell his maker-asset by very low price.
        "--boundary_min_nocancel"
    
        #set relative maximum and minimum maker price boundaries
            #set max at 105% and min 95% of price when bot was started
                "--boundary_max_relative 1.05 --boundary_min_relative 0.95"
            #set and track relative boundaries against USDT
                # ~ "--boundary_asset USD"
                # ~ "--boundary_asset_track True"
            
        #alternative set static boundary configuration, set maximum and minimum bot price boundary at static values relative to bitcoin
            #set relative boundary pricing to BTC.
                # ~ "--boundary_asset BTC"
            #set track boundary asset price updates. This means, ie if trading BLOCK/BTC on USD also track USD/BTC price and update boundaries by it.
                # ~ "--boundary_asset_track True"
            #Enable reversed pricing as 1/X, ie BLOCK/BTC vs BTC/BLOCK pricing can set like 0.000145 on both bot trading sides, instead of 0.000145 vs 6896.55.
                # ~ "--boundary_reversed_pricing False"
            #set manually starting center price
                # ~ "--boundary_start_price 0.00014511"
            #set manually boundaries
                # ~ "--boundary_max_static 0.00020015 --boundary_min_static 0.00013715"

#takerbot act like limit orders on your actually created orders, its also taking whole range of dynamic size and multiple orders
    #enabled takerbot feature to check orders to take on 10 second interval
        "--takerbot 10"
   
#delay between internal operations 2.3s
    "--delayinternal 2.3"
#check price every 60 seconds
    "--delaycheckprice 60"
#sleep delay, in seconds, when error happen to try again. (default=10)
    "--delayinternalerror 10"
#sleep delay, in seconds, between main loops to process all things to handle
    "--delayinternalcycle 8"

)
