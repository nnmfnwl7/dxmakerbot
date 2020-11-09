#!/usr/bin/env python3
import time
import random
import argparse
import sys
import logging
from utils import dxbottools
from utils import getpricing as pricebot
from utils import dxsettings

logging.basicConfig(filename='botdebug.log',
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s - %(message)s',
                    datefmt='[%Y-%m-%d:%H:%M:%S]')

########################################################################
# for better understanding how are order statuses managed read:
# https://api.blocknet.co/#status-codes
#
# new             >> New order, not yet broadcasted
# open            >> Open order, waiting for taker
# accepting       >> Taker accepting order
# hold            >> Counterparties acknowledge each other
# initialized     >> Counterparties agree on order
# created         >> Swap process starting
# commited        >> Swap finalized
# finished        >> Order complete
# expired         >> Order expired
# offline         >> Maker or taker went offline
# canceled        >> Order was canceled
# invalid         >> Problem detected with the order
# rolled back     >> Trade failed, funds being rolled back
# rollback failed >> Funds unsuccessfully redeemed in failed trade
#
# order with statuses which are considered as open are in flow:
#       ['open', 'accepting', 'hold', 'initialized', 'created', 'commited']
#
# order with statuses which are considered as finished are:
#       ['finished']
#
# order with statuses which are considered by default to reopen are:
#       ['clear', 'expired', 'offline', 'canceled', 'invalid', 'rolled back', 'rollback failed']
#
# order with statuses which are considered by default + option <reopenfinished> enabled to reopen are:
#       ['clear', 'expired', 'offline', 'canceled', 'invalid', 'rolled back', 'rollback failed', 'finished']
########################################################################
# for better variables naming, understanding, finding and code management and autocomplete 
# variables has been divided into 3 groups global config as c, global static as s, global dynamic as d
########################################################################

class GlobVars(): pass    
#global config variables
c = GlobVars()
#global static variables
s = GlobVars()
#global dynamic variables
d = GlobVars()

# welcome message
def start_welcome_message():
    global c, s, d
    print('>>>> Starting maker bot')

# initialization of config independent items or items needed for config load
def init_preconfig():
    global c, s, d
    print('>>>> Preconfig initialization')
    
    global_vars_init_preconfig()
    
    feature__balance_save_asset__init_preconfig()
    
    pricing_storage__init_preconfig()
    
    feature__boundary__init_preconfig()
    
    events_wait_reopenfinished_init()
    
    feature__slide_dynamic__init_preconfig()
    
    feature__takerbot__init_preconfig()

# initialization of items dependent on config
def init_postconfig():
    global c, s, d
    print('>>>> Postconfig initialization')
    
    global_vars_init_postconfig()
    
    pricing_storage__set_update_internal(c.BOTdelaycheckprice)

#global variables initialization
def global_vars_init_preconfig():
    global c, s, d
    print('>>>> Global variables initialization')
    d.price_maker = 0
    d.ordersfinished = 0
    d.ordersfinishedtime = 0
    
    # price of asset vs maker in which are orders sizes set
    d.feature__sell_size_asset__price = 0
    
    d.balance_maker_total = 0
    d.balance_maker_available = 0
    d.balance_maker_reserved = 0
    d.balance_taker_available = 0
    d.balance_taker_total = 0
    d.balance_taker_reserved = 0
    
    s.status_list_with_reserved_balance = [ 'new', 'open', 'accepting', 'hold', 'initialized', 'created', 'commited']

# initialize pricing storage component
def pricing_storage__init_preconfig():
    global c, s, d
    
    d.pricing_storage = GlobVars()
    d.pricing_storage.prices = {}
    d.pricing_storage.prices_update = {}
    d.pricing_storage.update_interval = 60

# set update interval in seconds
def pricing_storage__set_update_internal(update_internal):
    global c, s, d
    
    d.pricing_storage.update_interval = update_internal

# get pair identificator for storing price information
def pricing_storage__get_pair_id(maker, taker):
    return str(maker + "__" + taker)

# get pricing information from external source
def pricing_storage__try_external_source_get_price(maker__item_to_sell, taker__payed_by, previous_price):
    global c, s, d
    
    maker_price_in_takers = pricebot.getpricedata(maker__item_to_sell, taker__payed_by, c.BOTuse)
    print('>>>> Updating pricing information for maker <{0}> taker <{1}> previous <{2}> actual <{3}>'.format(maker__item_to_sell, taker__payed_by, previous_price, maker_price_in_takers))
    
    return maker_price_in_takers

# try to update specific pair price from external source by rest
def pricing_storage__try_update_price(maker, taker):
    global c, s, d
    
    pair = pricing_storage__get_pair_id(maker, taker)
    
    price = pricing_storage__try_external_source_get_price(maker, taker, d.pricing_storage.prices.get(pair, None))
    
    if price > 0:
        d.pricing_storage.prices[pair] = price
        d.pricing_storage.prices_update[pair] = time.time()
        
    return price

# try to get price from pricing storage
def pricing_storage__try_get_price(maker, taker):
    global c, s, d
    
    price = 1
    
    if maker != taker:
        pair = pricing_storage__get_pair_id(maker, taker)
        
        price = d.pricing_storage.prices.get(pair, 0)
        if price == 0:
            price = pricing_storage__try_update_price(maker, taker)
        elif (time.time() - d.pricing_storage.prices_update.get(pair, 0)) > d.pricing_storage.update_interval:
            price = pricing_storage__try_update_price(maker, taker)
    
    return price

def feature__boundary__init_preconfig():
    global c, s, d
    # relative pricing to boundary asset - actual
    d.feature__boundary__price_relative_actual = 0
    # relative pricing to boundary asset - at bot initialization
    d.feature__boundary__price_relative_initial = 0
    
    # initial price of maker for taker
    d.feature__boundary__price_maker_initial_center = 0
    # initial price of maker to taker relative to boundary price
    d.feature__boundary__price_maker_initial_center_relative = 0

def feature__slide_dynamic__init_preconfig():
    global c, s, d
    
    d.dynamic_slide = 0
    
    d.feature__slide_dynamic__zero_asset_price = 0

def feature__takerbot__init_preconfig():
    global c, s, d
    
    s.feature__takerbot__list_of_usable_statuses = [ 'new', 'open']
    d.feature__takerbot__time_start = 0

# reopen after finished number and reopen after finished delay features initialization
def events_wait_reopenfinished_init():
    global c, s, d
    
    s.orders_pending_to_reopen_opened_statuses = ['open', 'accepting', 'hold', 'initialized', 'created', 'commited']
    
    events_wait_reopenfinished_reinit()

# reopen after finished number and reopen after finished delay features re-initialization
def events_wait_reopenfinished_reinit():
    global c, s, d
    
    d.orders_pending_to_reopen_opened = 0
    d.orders_pending_to_reopen_finished = 0
    d.orders_pending_to_reopen_finished_time = 0

def load_config_verify_or_exit():
    global c, s, d
    print('>>>> Verifying configuration')
    
    error_num = 0
    
    # arguments: main maker/taker
    if hasattr(c, 'BOTmakeraddress') == False:
        print('**** ERROR, <makeraddress> is not specified')
        error_num += 1
        
    if hasattr(c, 'BOTtakeraddress') == False:
        print('**** ERROR, <takeraddress> is not specified')
        error_num += 1
    
    if c.BOTsell_type <= -1 or c.BOTsell_type >= 1:
        print('**** ERROR, <sell_type> value <{0}> is invalid. Valid range is -1 up to 1 only'.format(c.BOTsell_type))
        error_num += 1
    
    # arguments: basic values
    if c.BOTsellstart <= 0:
        print('**** ERROR, <sellstart> value <{0}> is invalid'.format(c.BOTsellstart))
        error_num += 1
    
    if c.BOTsellend <= 0:
        print('**** ERROR, <sellend> value <{0}> is invalid'.format(c.BOTsellend))
        error_num += 1
    
    if c.BOTsellstartmin != 0:
        if c.BOTsellstartmin < 0:
            print('**** ERROR, <sellstartmin> value <{0}> is invalid. Must be more than 0'.format(c.BOTsellstartmin))
            error_num += 1
        
        if c.BOTsellstartmin >= c.BOTsellstart:
            print('**** ERROR, <sellstartmin> value <{}> is invalid. Must be less than <sellstart> <{}>'.format(c.BOTsellstartmin, c.BOTsellstart))
            error_num += 1
            
    if c.BOTsellendmin != 0:
        if c.BOTsellendmin < 0:
            print('**** ERROR, <sellendmin> value <{}> is invalid. Must be more than 0'.format(c.BOTsellendmin))
            error_num += 1
        
        if c.BOTsellendmin >= c.BOTsellend:
            print('**** ERROR, <sellendmin> value <{}> is invalid. Must be less than <sellend> <{}>'.format(c.BOTsellendmin, c.BOTsellend))
            error_num += 1
    
    # ~ if c.BOTmarking != 0:
        # ~ if c.BOTmarking < 0:
            # ~ print('**** ERROR, <marking> value <{}> is invalid. Must be more than 0'.format(c.BOTmarking))
            # ~ error_num += 1
        
        # ~ if c.BOTmarking >= 0.001:
            # ~ print('**** WARNING, <marking> value <{}> seems invalid. Values more than 0.001 can possibly have very impact on order value'.format(c.BOTmarking))
            # ~ print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
            # ~ if not c.imreallysurewhatimdoing:
                # ~ error_num += 1
                
    if c.BOTslidestart <= 1:
        print('**** WARNING, <slidestart> value <{0}> seems invalid. Values less than 1 means selling something under price.'.format(c.BOTslidestart))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
    
    if c.BOTslidestart > 2:
        print('**** WARNING, <slidestart> value <{0}> seems invalid. <1.01> means +1%, <1.10> means +10%, more than <2> means +100% of actual price'.format(c.BOTslidestart))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
    
    if c.BOTslideend <= 1:
        print('**** WARNING, <slideend> value <{0}> seems invalid. Values less than 1 means selling something under price.'.format(c.BOTslideend))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
    
    if c.BOTslideend > 2:
        print('**** WARNING, <slideend> value <{0}> seems invalid. <1.01> means +1%, <1.10> means +10%, more than <2> means +100% of actual price'.format(c.BOTslideend))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
    
    if c.BOTmaxopenorders < 1:
        print('**** ERROR, <maxopen> value <{0}> is invalid'.format(c.BOTmaxopenorders))
        error_num += 1
    
    if c.BOTreopenfinisheddelay < 0:
        print('**** ERROR, <reopenfinisheddelay> value <{0}> is invalid'.format(c.BOTreopenfinisheddelay))
        error_num += 1
    
    if c.BOTreopenfinishednum < 0:
        print('**** ERROR, <reopenfinishednum> value <{0}> is invalid'.format(c.BOTreopenfinishednum))
        error_num += 1
    
    if c.BOTreopenfinishednum > c.BOTmaxopenorders:
        print('**** ERROR, <reopenfinishednum> can not be more than <maxopenorders> value <{0}>/<{1}> is invalid'.format(c.BOTreopenfinishednum, c.BOTmaxopenorders))
        error_num += 1
    
    if c.BOTtakerbot < 0:
        print('**** ERROR, <takerbot> value <{0}> is invalid'.format(c.BOTtakerbot))
        error_num += 1
    
    if c.BOTboundary_start_price != 0:
        if c.BOTboundary_start_price < 0:
            print('**** ERROR, <boundary_start_price> value <{0}> is invalid. Center price must be positive number'.format(c.BOTboundary_start_price))
            error_num += 1
    
    if c.BOTboundary_max_relative != 0:
        if c.BOTboundary_max_relative < 0:
            print('**** ERROR, <boundary_max_relative> value <{0}> is invalid. For example value <1.12> means bot will work up to price relative to +12% of price when bot started'.format(c.BOTboundary_max_relative))
            error_num += 1
        elif c.BOTboundary_max_relative < 1:
            print('**** WARNING, <boundary_max_relative> value <{0}> is invalid. For example value <1.12> means bot will work up to price relative to +12% of price when bot started'.format(c.BOTboundary_max_relative))
            print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
            if not c.imreallysurewhatimdoing:
                error_num += 1
    
    if c.BOTboundary_min_relative != 0:
        if c.BOTboundary_min_relative < 0:
            print('**** ERROR, <boundary_min_relative> value <{0}> is invalid. For example value <0.8> means bot will work at least of 0.8 of price, which is -20% of price when bot started'.format(c.BOTboundary_min_relative))
            error_num += 1
        elif c.BOTboundary_min_relative > 1:
            print('**** WARNING, <boundary_min_relative> value <{0}> seems invalid. For example value <0.8> means bot will work at least of 0.8 of price, which is -20% of price when bot started'.format(c.BOTboundary_min_relative))
            print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
            if not c.imreallysurewhatimdoing:
                error_num += 1
    
    if (c.BOTboundary_max_relative != 0 or c.BOTboundary_min_relative != 0) and (c.BOTboundary_max_static != 0 and c.BOTboundary_min_static != 0):
        print('**** ERROR, <boundary_***_relative> and <boundary_***_static> can not be configured at same time')
        error_num += 1
    
    if c.BOTboundary_max_relative != 0 and c.BOTboundary_max_relative < c.BOTboundary_min_relative:
        print('**** ERROR, <boundary_max_relative> value <{0}> can not be less than <boundary_min_relative> value <{1}>.'.format(c.BOTboundary_max_relative, c.BOTboundary_min_relative))
        error_num += 1
    
    if c.BOTboundary_max_static < 0:
        print('**** ERROR, <boundary_max_static> value <{0}> is invalid. For example value <100> means bot will sell maker for price maximum of 100 takers by one maker'.format(c.BOTboundary_max_static))
        error_num += 1
    
    if c.BOTboundary_min_static < 0:
        print('**** ERROR, <boundary_min_static> value <{0}> is invalid. For example value <10> means bot will sell maker for minimum price 10 takers by one maker'.format(c.BOTboundary_min_static))
        error_num += 1
    
    if c.BOTboundary_max_static < c.BOTboundary_min_static:
        print('**** ERROR, <boundary_max_static> value <{0}> can not be less than <boundary_min_static> value <{1}>.'.format(c.BOTboundary_max_static, c.BOTboundary_min_static))
        error_num += 1
    
    if c.BOTbalance_save_number < 0:
        print('**** ERROR, <balance_save_number> value <{0}> is invalid'.format(c.BOTbalance_save_number))
        error_num += 1
    
    if c.BOTbalance_save_percent < 0 or c.BOTbalance_save_percent > 1:
        print('**** ERROR, <balance_save_percent> value <{0}> is invalid'.format(c.BOTbalance_save_percent))
        error_num += 1
    
    # arguments: dynamic values, special pump/dump order
    if c.BOTslide_dyn_zero != -1:
        if c.BOTslide_dyn_type == 'ratio' and (c.BOTslide_dyn_zero > 1 or c.BOTslide_dyn_zero < 0):
            print('**** ERROR, <slide_dyn_zero> value <{0}> is invalid'.format(c.BOTslide_dyn_zero))
            error_num += 1
            
        if c.BOTslide_dyn_type == 'static' and (c.BOTslide_dyn_zero <= 0):
            print('**** ERROR, <slide_dyn_zero> value <{0}> is invalid'.format(c.BOTslide_dyn_zero))
            error_num += 1
            
    if c.BOTslide_dyn_zero_asset is not None:
        if c.BOTslide_dyn_type == 'ratio':
            print('**** ERROR, <slide_dyn_type> value <{0}> can not be set with <slide_dyn_zero_asset>'.format(c.BOTslide_dyn_type))
            error_num += 1
            
        if c.BOTslide_dyn_zero == -1:
            print('**** ERROR, <BOTslide_dyn_zero> value <{0}> can not be set with <slide_dyn_zero_asset>'.format(c.BOTslide_dyn_zero))
            error_num += 1
    
    if c.BOTslide_dyn_positive < 0:
        print('**** WARNING, <slide_dyn_positive> value <{0}> seems invalid'.format(c.BOTslide_dyn_positive))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
            
    if c.BOTslide_dyn_negative < 0:
        print('**** WARNING, <slide_dyn_negative> value <{0}> seems invalid'.format(c.BOTslide_dyn_negative))
        print('++++ HINT, If you are really sure about what you are doing, you can ignore this warning by using --imreallysurewhatimdoing argument')
        if not c.imreallysurewhatimdoing:
            error_num += 1
        
    if c.BOTslide_dyn_zoneignore < 0 or c.BOTslide_dyn_zoneignore > 1:
        print('**** ERROR, <slide_dyn_zoneignore> value <{0}> is invalid'.format(c.BOTslide_dyn_zoneignore))
        error_num += 1
    
    if c.BOTslide_dyn_zonemax <= 0 or c.BOTslide_dyn_zonemax > 1:
        print('**** ERROR, <slide_dyn_zonemax> value <{0}> is invalid'.format(c.BOTslide_dyn_zonemax))
        error_num += 1
    
    if c.BOTslidepump < 0:
        print('**** ERROR, <slidepump> value <{0}> is invalid'.format(c.BOTslidepump))
        error_num += 1
    
    if c.BOTpumpamount <= 0 and c.BOTslidepump > 0:
        print('**** ERROR, <pumpamount> value <{0}> is invalid'.format(c.BOTpumpamount))
        error_num += 1
        
    # arguments: reset orders by events
    if c.BOTresetonpricechangepositive < 0:
        print('**** ERROR, <resetonpricechangepositive> value <{0}> is invalid'.format(c.BOTresetonpricechangepositive))
        error_num += 1
    
    if c.BOTresetonpricechangenegative < 0:
        print('**** ERROR, <resetonpricechangenegative> value <{0}> is invalid'.format(c.BOTresetonpricechangenegative))
        error_num += 1
    
    if c.BOTresetafterdelay < 0:
        print('**** ERROR, <resetafterdelay> value <{0}> is invalid'.format(c.BOTresetafterdelay))
        error_num += 1
    
    if c.BOTresetafterorderfinishnumber < 0:
        print('**** ERROR, <resetafterorderfinishnumber> value <{0}> is invalid'.format(c.BOTresetafterorderfinishnumber))
        error_num += 1
    
    if c.BOTresetafterorderfinishdelay < 0:
        print('**** ERROR, <resetafterorderfinishdelay> value <{0}> is invalid'.format(c.BOTresetafterorderfinishdelay))
        error_num += 1
    
    # arguments: internal values changes
    if c.BOTdelayinternal < 1:
        print('**** ERROR, <delayinternal> value <{0}> is invalid'.format(c.BOTdelayinternal))
        error_num += 1
        
    if c.BOTdelayinternalerror < 1:
        print('**** ERROR, <delayinternalerror> value <{0}> is invalid'.format(c.BOTdelayinternalerror))
        error_num += 1
        
    # arguments: internal values changes
    if c.BOTdelayinternalcycle < 1:
        print('**** ERROR, <delayinternalcycle> value <{0}> is invalid'.format(c.BOTdelayinternalcycle))
        error_num += 1
    
    if c.BOTdelaycheckprice < 1:
        print('**** ERROR, <delaycheckprice> value <{0}> is invalid'.format(c.BOTdelaycheckprice))
        error_num += 1
        
    if error_num > 0:
        print('>>>> Verifying configuration failed. In special cases you can try read help and use <imreallysurewhatimdoing> argument which allows you to specify meaningless configuration variables')
        sys.exit(1)
    else:
        print('>>>> Verifying configuration success')

def argparse_bool(arg):
    if isinstance(arg, bool):
        return arg
    elif isinstance(arg, str):
        if arg.lower() in ['true', 'enabled', 'yes']:
            return True
        else:
            return False
    else:
        return False

def load_config():
    global c, s, d
    print('>>>> Loading program configuration')
    
    parser = argparse.ArgumentParser()
    
    # arguments: main maker/taker
    parser.add_argument('--maker', type=str, help='asset being sold (default=BLOCK)', default='BLOCK')
    parser.add_argument('--taker', type=str, help='asset being bought (default=LTC)', default='LTC')
    parser.add_argument('--makeraddress', type=str, help='trading address of asset being sold (default=None)', default=None)
    parser.add_argument('--takeraddress', type=str, help='trading address of asset being bought (default=None)', default=None)
    parser.add_argument('--address_only', type=argparse_bool, nargs='?', const=True, help='limit bot to use and compute funds only from maker and taker address(default=False disabled)', default=False)
    
    # ~ parser.add_argument('--maker_address_only', nargs='+', type=str, help='limit bot to use and compute funds from specific maker addresses(or multiple addresses separated by space) only, otherwise all addresses are used', action='store_true')
    # ~ parser.add_argument('--taker_address_only', nargs='+', type=str, help='limit bot to use and compute funds from specific taker addresses(or multiple addresses separated by space) only, otherwise all addresses are used', action='store_true')
    
    # arguments: basic values
    parser.add_argument('--sell_type', type=float, choices=range(-1, 1), help='<float> number between -1 and 1. -1 means maximum exponential to 0 means linear to 1 means maximum logarithmic. '
    'Recommended middle range log and exp values are 0.8 and -0.45'
    ' (default=0 linear)', default=0)
    parser.add_argument('--sell_size_asset', type=str, help='size of orders are set in specific asset instead of maker (default=--maker)', default=None)
    parser.add_argument('--sellstart', type=float, help='size of first order or random from range sellstart and sellend (default=0.001)', default=0.001)
    parser.add_argument('--sellend', type=float, help='size of last order or random from range sellstart and sellend (default=0.001)', default=0.001)
    
    parser.add_argument('--sellstartmin', type=float, help='Minimum acceptable size of first order.'
    'If this is configured and there is not enough balance to create first order at <sellstart> size, order will be created at maximum possible size between <sellstart> and <sellstartmin>'
    'By default this feature is disabled.'
    '(default=0 disabled)', default=0)
    parser.add_argument('--sellendmin', type=float, help='Minimum acceptable size of last order.'
    'If this is configured and there is not enough balance to create last order at <sellend> size, order will be created at maximum possible size between <sellend> and <sellendmin>'
    'By default this feature is disabled.'
    '(default=0 disabled)', default=0)
    # ~ parser.add_argument('--marking', type=float, help='mark order amount by decimal number for example 0.000777 (default=0 disabled)', default=0)
    
    parser.add_argument('--sellrandom', help='orders size will be random number between sellstart and sellend, otherwise sequence of orders starting by sellstart amount and ending with sellend amount(default=disabled)', action='store_true')
    parser.add_argument('--slidestart', type=float, help='price of first order will be equal to slidestart * price source quote(default=1.01 means +1%%)', default=1.01)
    parser.add_argument('--slideend', type=float, help='price of last order will be equal to slideend * price source quote(default=1.021 means +2.1%%)', default=1.021)
    parser.add_argument('--maxopen', type=int, help='Max amount of orders to have open at any given time. Placing orders sequence: first placed order is at slidestart(price slide),sellstart(amount) up to slideend(price slide),sellend(amount), last order placed is slidepump if configured, is not counted into this number (default=5)', default=5)
    parser.add_argument('--make_next_on_hit', type=argparse_bool, nargs='?', const=True, help='create next order on 0 amount hit, so if first order is not created, rather skipped, next is created(default=False disabled)', default=False)
    parser.add_argument('--reopenfinisheddelay', type=int, help='finished orders will be reopened after specific delay(seconds) of last filled order(default=0 disabled)', default=0)
    parser.add_argument('--reopenfinishednum', type=int, help='finished orders will be reopened after specific number of filled orders(default=0 disabled)', default=0)
    
    parser.add_argument('--partial_orders', type=argparse_bool, nargs='?', const=True, help='enable or disable partial orders. Partial orders minimum is set by <sellstartmin> <sellendmin> along with dynamic size of orders(default=False disabled)', default=False)
    parser.add_argument('--takerbot', type=int, help='Keep checking for possible partial orders which meets requirements(size, price) and accept that orders.'
    'If this feature is enabled, takerbot is automatically searching for orders at size between <sellstart-sellend>...<sellstartmin-sellendmin> and at price <slidestart-slideend>+<dynamic slide>*<price> and higher.'
    'This feature can be also understood as higher layer implementation of limit order feature on top of atomic swaps on BlockDX exchange. Takerbot can possible cancel multiple opened orders to autotake orders which meets requirements'
    '(I.e. value 30 means check every 30 seconds)'
    'By default this feature is disabled.'
    '(default=0 disabled)', default=0)
    
    # arguments: boundaries configuration
    parser.add_argument('--boundary_asset', type=str, help='boundary measurement asset, i.e.: if maker/taker pair is BLOCK/BTC and boundary_asset_is USDT, so possible boundary min 1.5 and max 3 USD (default= --taker)', default=None)
    parser.add_argument('--boundary_asset_track', type=argparse_bool, nargs='?', const=True, help='Track boundary asset price updates. This means, ie if trading BLOCK/BTC on USD also track USD/BTC price and update boundaries by it (default=False disabled)', default=False)
    
    parser.add_argument('--boundary_reversed_pricing', type=argparse_bool, nargs='?', const=True, help='reversed set pricing as 1/X, ie BLOCK/BTC vs BTC/BLOCK pricing can set like 0.000145 on both bot trading sides, instead of 0.000145 vs 6896.55.'
    'Is used in configuration <boundary_start_price>, <boundary_max_static> and <boundary_min_static>.'
    ' (default=False Disabled)', default=False)
    
    parser.add_argument('--boundary_start_price', type=float, help='manually set center price. Its usable only when using relative boundaries and boundary_asset_track is Disabled (default=0 automatic)', default=0)
    
    parser.add_argument('--boundary_max_relative', type=float, help='maximum acceptable price of maker(sold one) where bot will stop selling, price is relative to price when bot started,i.e.: Start price:100, config value:3, so bot will sell up to 100*3 = 300 price, (default=0 disabled)', default=0)
    parser.add_argument('--boundary_min_relative', type=float, help='minimum acceptable price of maker(sold one) where bot will stop selling, price is relative to price when bot started,i.e.: Start price:100, config value:0.8, so bot will sell at least for 100*0.8 = 80 price, (default=0 disabled)', default=0)
    
    parser.add_argument('--boundary_max_static', type=float, help='maximum acceptable price of maker(sold one) where bot will stop selling(default=0 disabled)', default=0)
    parser.add_argument('--boundary_min_static', type=float, help='minimum acceptable price of maker(sold one) where bot will stop selling(default=0 disabled)', default=0)
    
    parser.add_argument('--boundary_max_nocancel', help='do not cancel orders, default is to cancel orders', action='store_true')
    parser.add_argument('--boundary_max_noexit', help='wait instead of exit program, default is to exit program', action='store_true')
    parser.add_argument('--boundary_min_nocancel', help='do not cancel orders, default is to cancel orders', action='store_true')
    parser.add_argument('--boundary_min_noexit', help='wait instead of exit program, default is to exit program', action='store_true')
    
    parser.add_argument('--balance_save_asset', type=str, help='size of balance to save is set in specific asset instead of maker (default=--maker)', default=None)
    parser.add_argument('--balance_save_asset_track', type=argparse_bool, nargs='?', const=True, help='Track balance save asset price updates. This means, ie if trading BLOCK/BTC on USD also track USD/BLOCK price and update balance to save by it (default=False disabled)', default=False)
    parser.add_argument('--balance_save_number', help='min taker balance you want to save and do not use for making orders specified by number (default=0)', default=0)
    parser.add_argument('--balance_save_percent', help='min taker balance you want to save and do not use for making orders specified by percent of maker+taker balance (default=0.05 means 5%%)', default=0.05)

    # arguments: dynamic values, special pump/dump order
    parser.add_argument('--slide_dyn_type', type=str, choices=['ratio', 'static'], help='maker*price:taker ratio when dynamic slide intensity is 0. Or static value in maker when dynamic slide intensity is 0 (default=ratio)', default='ratio')
    parser.add_argument('--slide_dyn_zero_asset', type=str, help='dynamic slide zero is set in specific asset instead of maker (default=--maker)', default=None)
    parser.add_argument('--slide_dyn_zero_asset_track', type=argparse_bool, nargs='?', const=True, help='track dynamic slide zero asset price updates. This means, ie if trading BLOCK/BTC on USD also track USD/BLOCK price and update dynamic slide zero by it (default=False disabled)', default=False)
    parser.add_argument('--slide_dyn_zero', type=float, help=
    'Ratio value or static specific value when dynamic slide intensity is 0%%.'
    ' Value -1 means to autoconfig value to intensity be 0%% for bot startup MAKER/TAKER amounts.'
    ' Otherwise it means maker/taker ratio where dynamic slide is at 0%% intensity.'
    ' ie #1 0.5 means 0%% intensity at 50:50 balance,'
    ' ie #2 1.0 means 0%% intensity at 100%% of balance in TAKER,'
    ' 0 means 0%% intensity at 100%% of balance in MAKER.'
    ' Static value means static amount of maker where dynamic slide intensity is at 0%%.'
    '(default= 0.5 means 50:50 balance)', default=0.5)
    parser.add_argument('--slide_dyn_positive', type=float, help='dynamic price slide increase positive, applied if maker price goes up, range between 0 and slide_dyn_positive, dynamically computed by assets ratio.'
    'I.e. 0.5 means slide increase +0%% up to +50%%'
    '(default=0 disabled)', default=0)
    parser.add_argument('--slide_dyn_negative', type=float, help='dynamic price slide increase negative, applied if maker price goes down, range between 0 and slide_dyn_negative, dynamically computed by assets ratio.'
    'I.e. 0.1 means slide increase +0%% up to +10%%'
    '(default=0 disabled)', default=0)
    parser.add_argument('--slide_dyn_zoneignore', type=float, help='dynamic price slide increase ignore is zone when dynamic slide is not activated(default=0.05 means 5%% of balance)', default=0.05)
    parser.add_argument('--slide_dyn_zonemax', type=float, help='percentage when dynamic order price slide increase gonna reach maximum(default=0.9 means at 90%%)', default=0.9)
    
    parser.add_argument('--slidepump', type=float, help='if slide pump is non zero a special order out of slidemax is set, this order will be filled when pump happen(default=0 disabled, 0.5 means order will be placed +50%% out of maximum slide)', default=0)
    parser.add_argument('--pumpamount', type=float, help='pump order size, otherwise sellend is used(default=--sellend)', default=0)
    parser.add_argument('--pumpamountmin', type=float, help='minimum acceptable pump order size, otherwise sellendmin is used(default=--sellendmin)', default=0)

    # arguments: reset orders by events
    parser.add_argument('--resetonpricechangepositive', type=float, help='percentual price positive change(you can buy more) when reset all orders. I.e. 0.05 means reset at +5%% change. (default=0 disabled)', default=0)
    parser.add_argument('--resetonpricechangenegative', type=float, help='percentual price negative change(you can buy less) when reset all orders. I.e. 0.05 means reset at -5%% change. (default=0 disabled)', default=0)
    parser.add_argument('--resetafterdelay', type=int, help='keep resetting orders in specific number of seconds (default=0 disabled)', default=0)
    parser.add_argument('--resetafterorderfinishnumber', type=int, help='number of orders to be finished before resetting orders (default=0 disabled)', default=0)
    parser.add_argument('--resetafterorderfinishdelay', type=int, help='delay after finishing last order before resetting orders in seconds (default=0 disabled)', default=0)

    # arguments: internal values changes
    parser.add_argument('--delayinternal', type=float, help='sleep delay, in seconds, between place/cancel orders or other internal operations(can be used ie. case of bad internet connection...) (default=2.3)', default=2.3)
    parser.add_argument('--delayinternalerror', type=float, help='sleep delay, in seconds, when error happen to try again. (default=10)', default=10)
    parser.add_argument('--delayinternalcycle', type=float, help='sleep delay, in seconds, between main loops to process all things to handle. (default=8)', default=8)
    parser.add_argument('--delaycheckprice', type=float, help='sleep delay, in seconds to check again pricing (default=180)', default=180)

    # arguments: pricing source arguments
    parser.add_argument('--usecb', help='enable cryptobridge pricing', action='store_true')
    parser.add_argument('--usecg', help='enable coingecko pricing', action='store_true')
    parser.add_argument('--usecustom', help='enable custom pricing', action='store_true')

    # arguments: utility arguments
    parser.add_argument('--cancelall', help='cancel all orders and exit', action='store_true')
    parser.add_argument('--cancelmarket', help='cancel all orders in market specified by pair --maker and --taker', action='store_true')
    
    # arguments: special arguments
    parser.add_argument('--imreallysurewhatimdoing', help='This argument allows user to specify non-standard configuration values for special cases like user want to sell under actual price', action='store_true')
    
    args = parser.parse_args()

    # arguments: main maker/taker
    c.BOTsellmarket = args.maker.upper()
    c.BOTbuymarket = args.taker.upper()
    
    # try to autoselect maker/taker address from config file
    if c.BOTsellmarket in dxsettings.tradingaddress:
        c.BOTmakeraddress = dxsettings.tradingaddress[c.BOTsellmarket]
    
    if c.BOTbuymarket in dxsettings.tradingaddress:
        c.BOTtakeraddress = dxsettings.tradingaddress[c.BOTbuymarket]
    
    # try to autoselect maker/taker address from program arguments
    if args.makeraddress is not None:
        c.BOTmakeraddress = args.makeraddress
        
    if args.takeraddress is not None:
        c.BOTtakeraddress = args.takeraddress
    
    c.BOTaddress_only = bool(args.address_only)
    
    c.BOTpartial_orders = bool(args.partial_orders)
    
    if args.boundary_asset is None:
        c.BOTboundary_asset = c.BOTbuymarket
    else:
        c.BOTboundary_asset = str(args.boundary_asset)
    
    c.BOTboundary_asset_track = bool(args.boundary_asset_track)
    
    c.BOTboundary_reversed_pricing = bool(args.boundary_reversed_pricing)
    
    c.BOTboundary_start_price = float(args.boundary_start_price)
    
    c.BOTboundary_max_relative = args.boundary_max_relative
    c.BOTboundary_min_relative = args.boundary_min_relative
    
    c.BOTboundary_max_static = args.boundary_max_static
    c.BOTboundary_min_static = args.boundary_min_static
    
    c.BOTboundary_max_nocancel = args.boundary_max_nocancel
    c.BOTboundary_max_noexit = args.boundary_max_noexit
    c.BOTboundary_min_nocancel = args.boundary_min_nocancel
    c.BOTboundary_min_noexit = args.boundary_min_noexit
    
    # arguments: basic values
    c.BOTsellrandom = args.sellrandom
    
    if args.sell_size_asset is None:
        c.BOTsell_size_asset = c.BOTsellmarket
    else:
        c.BOTsell_size_asset = str(args.sell_size_asset)
    
    c.BOTsell_type = float(args.sell_type)
    
    c.BOTsellstart = float(args.sellstart)
    c.BOTsellend = float(args.sellend)
    c.BOTsellstartmin = float(args.sellstartmin)
    c.BOTsellendmin = float(args.sellendmin)
    c.BOTslidestart = float(args.slidestart)
    c.BOTslideend = float(args.slideend)
    c.BOTslidemin = min(c.BOTslidestart, c.BOTslideend)
    c.BOTslidemax = max(c.BOTslidestart, c.BOTslideend)
    c.BOTmaxopenorders = int(args.maxopen)
    c.BOTmake_next_on_hit = bool(args.make_next_on_hit)
    c.BOTreopenfinisheddelay = int(args.reopenfinisheddelay)
    c.BOTreopenfinishednum = int(args.reopenfinishednum)
    if c.BOTreopenfinishednum > 0 or c.BOTreopenfinisheddelay > 0:
        c.BOTreopenfinished = 1
    else:
        c.BOTreopenfinished = 0
    
    # ~ c.BOTmarking = float(args.marking)
    
    if args.balance_save_asset is None:
        c.BOTbalance_save_asset = c.BOTsellmarket
    else:
        c.BOTbalance_save_asset = str(args.balance_save_asset)
    c.BOTbalance_save_asset_track = bool(args.balance_save_asset_track)
    c.BOTbalance_save_number = float(args.balance_save_number)
    c.BOTbalance_save_percent = float(args.balance_save_percent)
    
    c.BOTtakerbot = int(args.takerbot)
    
    # arguments: dynamic values, special pump/dump order
    if args.slide_dyn_zero_asset is None:
        c.BOTslide_dyn_zero_asset = c.BOTsellmarket
    else:
        c.BOTslide_dyn_zero_asset = str(args.slide_dyn_zero_asset)
    c.BOTslide_dyn_zero_asset_track = bool(args.slide_dyn_zero_asset_track)
    c.BOTslide_dyn_type = str(args.slide_dyn_type)
    c.BOTslide_dyn_zero = float(args.slide_dyn_zero)
    c.BOTslide_dyn_positive = float(args.slide_dyn_positive)
    c.BOTslide_dyn_negative = float(args.slide_dyn_negative)
    c.BOTslide_dyn_zoneignore = float(args.slide_dyn_zoneignore)
    c.BOTslide_dyn_zonemax = float(args.slide_dyn_zonemax)
    
    c.BOTslidepump = float(args.slidepump)
    c.BOTslidepumpenabled = (True if c.BOTslidepump > 0 else False)
    c.BOTpumpamount = (float(args.pumpamount) if float(args.pumpamount) > 0 else c.BOTsellend)
    
    # arguments: reset orders by events
    c.BOTresetonpricechangepositive = float(args.resetonpricechangepositive)
    c.BOTresetonpricechangenegative = float(args.resetonpricechangenegative)
    c.BOTresetafterdelay = int(args.resetafterdelay)
    c.BOTresetafterorderfinishnumber = int(args.resetafterorderfinishnumber)
    c.BOTresetafterorderfinishdelay = int(args.resetafterorderfinishdelay)
    
    # arguments: internal values changes
    c.BOTdelayinternal = float(args.delayinternal)
    c.BOTdelayinternalerror = float(args.delayinternalerror)
    c.BOTdelayinternalcycle = float(args.delayinternalcycle)
    c.BOTdelaycheckprice = int(args.delaycheckprice)
    
    # arguments: pricing source arguments
    if args.usecustom:
        c.BOTuse = 'custom'
    elif args.usecg:
        c.BOTuse = 'cg'
    elif args.usecb:
        c.BOTuse = 'cb'
    else:
        c.BOTuse = 'bt'
    
    # arguments: utility arguments
    c.cancelall = args.cancelall
    c.cancelmarket = args.cancelmarket
    
    # arguments: special arguments
    c.imreallysurewhatimdoing = args.imreallysurewhatimdoing
    
    load_config_verify_or_exit()
    
# global variables which have dependency on configuration be done
def global_vars_init_postconfig():
    global c, s, d
    print('>>>> Global variables post-configuration initialization')
    
    if c.BOTreopenfinished == 0:
        s.reopenstatuses = ['clear', 'expired', 'offline', 'canceled', 'invalid', 'rolled back', 'rollback failed']
    else:
        s.reopenstatuses = ['clear', 'expired', 'offline', 'canceled', 'invalid', 'rolled back', 'rollback failed', 'finished']
    
    s.ordersvirtualmax = c.BOTmaxopenorders + int(c.BOTslidepumpenabled) # pump and dump order is extra if exist
    d.ordersvirtual = [0]*s.ordersvirtualmax
    for i in range(s.ordersvirtualmax):
        d.ordersvirtual[i] = {}
        d.ordersvirtual[i]['status'] = 'canceled'
        d.ordersvirtual[i]['id'] = 0
    

def do_utils_cancel_market():
    global c, s, d
    print('>>>> Using utility to cancel {0}-{1} orders and exit'.format(c.BOTsellmarket, c.BOTbuymarket))
    results = dxbottools.cancelallordersbymarket(c.BOTsellmarket, c.BOTbuymarket)
    print('>>>> Cancel orders result: {0}'.format(results))
    return results

# do utils and exit
def do_utils_and_exit():
    global c, s, d
    if c.cancelall:
        print('>>>> Utility to cancell all orders on all markets was specified and exit')
        results = dxbottools.cancelallorders()
        print(results)
        sys.exit(0)
    elif c.cancelmarket:
        do_utils_cancel_market()
        sys.exit(0)

# try to update pricing information
def pricing_update_main():
    global c, s, d
    
    price_maker = pricing_storage__try_get_price(c.BOTsellmarket, c.BOTbuymarket)
    
    if price_maker != 0:
        d.price_maker = price_maker
    
    return price_maker

# check if pricing works or exit        
def pricing_check_or_exit():
    global c, s, d
    print('>>>> Checking pricing information for <{0}> <{1}>'.format(c.BOTsellmarket, c.BOTbuymarket))
    
    # check if sell and buy market are not same
    if c.BOTsellmarket == c.BOTbuymarket:
        print('ERROR: Maker and taker asset cannot be the same')
        sys.exit(1)
    
    # try to get main pricing
    price_maker = pricing_update_main()
    if price_maker == 0:
        print('#### Main pricing not available')
        sys.exit(1)
    
    # try to get initial price of asset which balance save size is set in
    price__balance_save_asset = feature__balance_save_asset__pricing_update()
    if price__balance_save_asset == 0:
        print('#### balance save asset pricing not available')
        sys.exit(1)
    
    # try to get initial price of asset vs maker in which is dynamic slide zero set
    price_slide_dynamic_zero_asset = feature__slide_dynamic__zero_asset_pricing_update()
    if price_slide_dynamic_zero_asset == 0:
        print('#### dynamic slide zero asset pricing not available')
        sys.exit(1)
    
    # try to get initial price of asset vs maker in which are orders sizes set, ie USD
    price_sell_size_asset = feature__sell_size_asset__pricing_update()
    if price_sell_size_asset == 0:
        print('#### Sell size asset pricing not available')
        sys.exit(1)
    
    # try to get initial boundary pricing if custom
    price_boundary = feature__boundary__pricing_update_relative_init()
    if price_boundary == 0:
        print('#### Boundary pricing not available')
        sys.exit(1)

# asset which dynamic slide zero size is set in pricing update
def feature__slide_dynamic__zero_asset_pricing_update():
    global c, s, d
    
    temp_price = pricing_storage__try_get_price(c.BOTslide_dyn_zero_asset, c.BOTsellmarket)
    if temp_price != 0:
        d.feature__slide_dynamic__zero_asset_price = temp_price
    
    return temp_price

# convert asset which dynamic slide zero size is set to maker 
def feature__slide_dynamic__zero_asset_convert_to_maker(size_in_slide_dyn_zero_asset):
    global c, s, d
    
    return d.feature__slide_dynamic__zero_asset_price * size_in_slide_dyn_zero_asset
    
# price of asset which balance save size is set in initialization
def feature__balance_save_asset__init_preconfig():
    global c, s, d
    
    d.feature__balance_save_asset__price = 0

# price of asset which balance save size is set in pricing update
def feature__balance_save_asset__pricing_update():
    global c, s, d
    
    temp_price = pricing_storage__try_get_price(c.BOTbalance_save_asset, c.BOTsellmarket)
    if temp_price != 0:
        d.feature__balance_save_asset__price = temp_price
    
    return temp_price

# convert asset which balance save size is set to maker 
def feature__balance_save_asset__convert_to_maker(size_in_balance_save_asset):
    global c, s, d
    
    return d.feature__balance_save_asset__price * size_in_balance_save_asset

# get price of asset vs maker in which are orders sizes set, ie USD
def feature__sell_size_asset__pricing_update():
    global c, s, d
    
    temp_price = pricing_storage__try_get_price(c.BOTsell_size_asset, c.BOTsellmarket)
    if temp_price != 0:
        d.feature__sell_size_asset__price = temp_price
    
    return temp_price

# relative boundaries can be specified as relative to maker taker market so price must be checked separately
def feature__boundary__pricing_update():
    global c, s, d
    
    tmp_feature__boundary__price_relative_actual = 0
    
    # not reversed pricing system: BOUNDARY >> TAKER
    if c.BOTboundary_reversed_pricing is False:
        price_boundary_for_taker = pricing_storage__try_get_price(c.BOTboundary_asset, c.BOTbuymarket)
        tmp_feature__boundary__price_relative_actual = price_boundary_for_taker
        print(">>>> Boundary pricing update: not reversed: <{}/{}>: <{}>".format(c.BOTboundary_asset, c.BOTbuymarket, tmp_feature__boundary__price_relative_actual))
    
    # reversed pricing system: BOUNDARY >> 1/MAKER
    else:
        price_boundary_for_maker = pricing_storage__try_get_price(c.BOTboundary_asset, c.BOTsellmarket)
        if price_boundary_for_maker == 0:
            tmp_feature__boundary__price_relative_actual = 0
        else:
            tmp_feature__boundary__price_relative_actual = 1/price_boundary_for_maker
        print(">>>> Boundary pricing update: reversed: <{}/{}>: <{}>".format(c.BOTboundary_asset, c.BOTbuymarket, tmp_feature__boundary__price_relative_actual))
        
    if tmp_feature__boundary__price_relative_actual != 0:
        d.feature__boundary__price_relative_actual = tmp_feature__boundary__price_relative_actual
    
    return tmp_feature__boundary__price_relative_actual

# initial get pricing for relative boundaries
def feature__boundary__pricing_update_relative_init():
    global c, s, d
    
    tmp_feature__boundary__price_relative_actual = feature__boundary__pricing_update()
    
    d.feature__boundary__price_relative_initial = tmp_feature__boundary__price_relative_actual
    
    if c.BOTboundary_start_price > 0:
        d.feature__boundary__price_maker_initial_center = c.BOTboundary_start_price * tmp_feature__boundary__price_relative_actual
        d.feature__boundary__price_maker_initial_center_relative = c.BOTboundary_start_price
        print(">>>> Boundary pricing initial update: manual: {} = {} * {}".format(d.feature__boundary__price_maker_initial_center, c.BOTboundary_start_price, tmp_feature__boundary__price_relative_actual))
    else:
        d.feature__boundary__price_maker_initial_center = d.price_maker
        d.feature__boundary__price_maker_initial_center_relative = d.price_maker / tmp_feature__boundary__price_relative_actual
        print(">>>> Boundary pricing initial update: auto: {}".format(d.feature__boundary__price_maker_initial_center))
        
    return tmp_feature__boundary__price_relative_actual
        
# update balances for specific assset
def balance_get(token, address_only = None):
    global c, s, d
    
    ret = {"total": 0, "available": 0, "reserved": 0}
    
    # get all utxos
    utxos = dxbottools.get_utxos(token, True)
    
    # check if get utxos error been occurred
    if isinstance(utxos, list):
        
        for utxo in utxos:
            if address_only == None or utxo.get("address", "") == address_only:
                tmp = utxo.get("amount", 0)
                if utxo.get("orderid", "") == "":
                    ret["available"] += float(tmp)
                else:
                    ret["reserved"] += float(tmp)
                ret["total"] += float(tmp)
    else:
        print('ERROR: get_utxos call invalid response: {}'.format(utxos))
    
    return ret
    
# update actual balanced of maker and taker
def update_balances():
    global c, s, d
    
    print('>>>> Updating balances')
    
    tmp_maker = {}
    tmp_taker = {}
    
    tmp_maker_address = None
    tmp_taker_address = None
    
    # if bot using funds from specific address only
    if c.BOTaddress_only is True:
        tmp_maker_address = c.BOTmakeraddress
        tmp_taker_address = c.BOTtakeraddress
    
    tmp_maker = balance_get(c.BOTsellmarket, tmp_maker_address)
    tmp_taker = balance_get(c.BOTbuymarket, tmp_taker_address)
    
    d.balance_maker_total = tmp_maker["total"]
    d.balance_maker_available = tmp_maker["available"]
    d.balance_maker_reserved = tmp_maker["reserved"]
    
    d.balance_taker_total = tmp_taker["total"]
    d.balance_taker_available = tmp_taker["available"]
    d.balance_taker_reserved = tmp_taker["reserved"]
    
    print('>>>> Actual balance maker token <{}> <{}> total <{}> available <{}> reserved <{}>'.format(tmp_maker_address, c.BOTsellmarket, d.balance_maker_total, d.balance_maker_available, d.balance_maker_reserved))
    print('>>>> Actual balance taker token <{}> <{}> total <{}> available <{}> reserved <{}>'.format(tmp_taker_address, c.BOTbuymarket, d.balance_taker_total, d.balance_taker_available, d.balance_taker_reserved))

# initialize dynamic slide feature
def feature__slide_dynamic__init_postpricing():
    global c, s, d
    
    balance_taker_in_maker = (d.balance_taker_total / d.price_maker) #convert taker balance to by price
    balance_total = d.balance_maker_total + balance_taker_in_maker
    
    if c.BOTslide_dyn_type == 'ratio':
        if c.BOTslide_dyn_zero == -1:
            if balance_total == 0:
                c.BOTslide_dyn_zero = 0.5
            else:
                c.BOTslide_dyn_zero = d.balance_maker_total / balance_total
            
            print('>>>> dynamic slide initialization auto-set <ratio> zero intensity at value <{0}>'.format(c.BOTslide_dyn_zero))
        else:
            print('>>>> dynamic slide initialization manu-set <ratio> zero intensity at value <{0}>'.format(c.BOTslide_dyn_zero))
    elif c.BOTslide_dyn_type == 'static':
        if c.BOTslide_dyn_zero == -1:
            c.BOTslide_dyn_zero = d.balance_maker_total
            print('>>>> dynamic slide initialization auto-set <static> zero intensity at value <{0}>'.format(c.BOTslide_dyn_zero))
            if c.BOTslide_dyn_zero == 0:
                print('!!!! Invalid auto configuration <BOTslide_dyn_zero> is <{0}>'.format(c.BOTslide_dyn_zero))
                sys.exit(1)
        else:
            print('>>>> dynamic slide initialization manu-set <static> zero intensity at value <{0}>'.format(c.BOTslide_dyn_zero))
    else:
        print('!!!! internal BUG Detected <BOTslide_dyn_type> is <{0}>'.format(c.BOTslide_dyn_type))
        sys.exit(1)
        
# get <ratio> dynamic slide intensity
def feature__slide_dynamic__get_intensity__ratio():
    global c, s, d
    
    slide_dynamic_intensity = 0
    
    balance_taker_in_maker = (d.balance_taker_total / d.price_maker) #convert taker balance to by price
    balance_total = d.balance_maker_total + balance_taker_in_maker
    
    if balance_total == 0:
        slide_dynamic_intensity = 0
    else:
        slide_dynamic_intensity = ((c.BOTslide_dyn_zero * balance_total) - d.balance_maker_total) / ((c.BOTslide_dyn_zero * balance_total) * c.BOTslide_dyn_zonemax)
    
    return slide_dynamic_intensity
    
# get <static> dynamic slide intensity
def feature__slide_dynamic__get_intensity__static():
    global c, s, d
    
    tmp_bot_slide_dyn_zero = feature__slide_dynamic__zero_asset_convert_to_maker(c.BOTslide_dyn_zero)
    
    slide_dynamic_intensity = (tmp_bot_slide_dyn_zero - d.balance_maker_total) / (tmp_bot_slide_dyn_zero * c.BOTslide_dyn_zonemax)
    
    return slide_dynamic_intensity
    
# recompute and get dynamic slide intensity by dynamic slide type and dynamic slide zero
def feature__slide_dynamic__get_intensity():
    global c, s, d
    
    slide_dynamic_intensity = 0
    
    if c.BOTslide_dyn_type == 'ratio':
        slide_dynamic_intensity = feature__slide_dynamic__get_intensity__ratio()
    elif c.BOTslide_dyn_type == 'static':
        slide_dynamic_intensity = feature__slide_dynamic__get_intensity__static()
    else:
        print('!!!! internal BUG Detected <BOTslide_dyn_type> is <{0}>'.format(c.BOTslide_dyn_type))
        sys.exit(1)
        
    slide_dynamic_intensity = min(slide_dynamic_intensity, 1)
    slide_dynamic_intensity = max(slide_dynamic_intensity, -1)
    
    return slide_dynamic_intensity

# custom dynamic spread(slide) computation
def feature__slide_dynamic__update():
    global c, s, d
    print('>>>> Updating dynamic slide')
    
    # custom dynamic price slide == custom dynamic spread == slide_dynamic_intensity

    # dynamic_spread_intensity number is min at 0 to max at 1 number
    # dynamic_spread_intensity starting by 0 in "dynamic_spread_ignore_zone" at "slide dynamic zero"
    # groving up to 1 when reached "dynamic_spread_max_zone"
    #
    # Theory about:
    #
    # if price of TAKER(TO BUY) is going up, opposite BOT is selling more and more,
    # so this BOT have more and more MAKER(TO SELL)
    # in this case you wanna buy TAKER by MAKER cheaper with smaller spread, but with possible market overturn expectations
    # for this case slide_dyn_negative argument is used
    #
    # if price of TAKER(TO BUY) is going down, opposite BOT is selling less and less,
    # also this BOT is buying more and more,
    # so this BOT have less and less MAKER(TO SELL)
    # for this case slide_dyn_positive argument is used
    # 
    # dynamic_spread_intensity in general means how much intensity of
    # slide_dyn_negative or slide_dyn_positive to use,
    # computation of dynamic spread is than:
    # case 1 if price of TAKER(TO BUY) is going up = slide_dyn_negative * abs(dynamic_spread_intensity)
    # case 2 if price of TAKER(TO BUY) is going down = slide_dyn_positive * dynamic_spread_intensity
    #
    # final spread(slide) than is gonna be sum of this-dynamic-spread and statically configured spread
    
    slide_dynamic_intensity = feature__slide_dynamic__get_intensity()
    
    if abs(slide_dynamic_intensity) < c.BOTslide_dyn_zoneignore:
        d.dynamic_slide = 0
        print('>>>> Using dynamic_spread <{}> because slide_dynamic_intensity <{}> is in slide_dyn_zoneignore <{}>'.format(d.dynamic_slide, slide_dynamic_intensity, c.BOTslide_dyn_zoneignore))
    elif slide_dynamic_intensity > 0:
        d.dynamic_slide = abs(slide_dynamic_intensity) * c.BOTslide_dyn_positive
        print('>>>> Using dynamic_spread <{}> computed by slide_dynamic_intensity <{}> multiplied by slide_dyn_positive <{}>'.format(d.dynamic_slide, slide_dynamic_intensity, c.BOTslide_dyn_positive))
    elif slide_dynamic_intensity < 0:
        d.dynamic_slide = abs(slide_dynamic_intensity) * c.BOTslide_dyn_negative
        print('>>>> Using dynamic_spread <{}> computed by slide_dynamic_intensity <{}> multiplied by slide_dyn_negative <{}>'.format(d.dynamic_slide, slide_dynamic_intensity, c.BOTslide_dyn_negative))
        
    return d.dynamic_slide

def virtual_orders__get_status(order):
    return order.get("status",None)

def virtual_orders__update_status(order, status, ifyes = None, ifnot = None):
    if (ifyes is None) or (order.get("status", None) in ifyes):
        if ifnot is None or order.get("status", None) not in ifnot:
            order["status"] = status
            return True
    return False
    
# virtual-orders cancel, clear and wait for process done
def virtual_orders__clear_all():
    global c, s, d
    print('>>>> Clearing all session virtual orders and waiting for be done...')
    
    # mark all virtual orders as cleared
    for i in range(s.ordersvirtualmax):
        virtual_orders__update_status(d.ordersvirtual[i], 'clear', ifnot = ['clear'])
    
    virtual_orders__cancel_all()

# virtual-orders cancel and wait for process done
def virtual_orders__cancel_all():
    global c, s, d
    print('>>>> Canceling all session virtual orders and waiting for be done...')
    
    # loop while some orders are opened otherwise break while, do not cancel orders which are in progress
    while 1:
        clearing = int(0)
        ordersopen = dxbottools.getallmyordersbymarket(c.BOTsellmarket,c.BOTbuymarket)
        # loop all previously opened virtual orders and try clearing opened
        for i in range(s.ordersvirtualmax):
            # try to find match between session and existing orders and clear it
            for z in ordersopen:
                # clear orders which are new or opened and match by id
                if (z['status'] == "open" or z['status'] == 'new') and z['id'] == d.ordersvirtual[i]['id']:
                    print('>>>> Clearing virtual order index <{0}> id <{1}> and waiting for be done...'.format(i, z['id']))
                    dxbottools.rpc_connection.dxCancelOrder(z['id'])
                    clearing += 1
                    break
        if clearing > 0:
            print('>>>> Sleeping waiting for old orders to be cleared')
            time.sleep(c.BOTdelayinternal)
        else:
            break
        
    # wait for orders which are in progress state (TODO)
    
# search for item that contains named item that contains specific data
def lookup_universal(lookup_data, lookup_name, lookup_id):
    # find my orders, returns order if orderid passed is inside myorders
    for zz in lookup_data:
        if zz[lookup_name] == lookup_id:
            return zz

def lookup_order_id_2(orderid, myorders):
    return lookup_universal(myorders, 'id', orderid)

# check all virtual-orders if there is some finished  
def virtual_orders__check_status_update_status():
    global c, s, d
    print('>>>> Checking all session virtual orders how many orders finished and last time when order was finished...')
    
    ordersopen = dxbottools.getallmyordersbymarket(c.BOTsellmarket,c.BOTbuymarket)
    for i in range(s.ordersvirtualmax):
        if d.ordersvirtual[i]['id'] != 0:
            # check how many virtual open orders finished
            order = lookup_order_id_2(d.ordersvirtual[i]['id'], ordersopen)
            
            #debug log
            print('>>>> Order <{}> sell maker <{}> amount <{}> to buy taker <{}> amount <{}> status original <{}> to actual <{}> id <{}> market price <{}> order price <{}> description <{}>'
            .format(d.ordersvirtual[i]['vid'], d.ordersvirtual[i]['maker'], d.ordersvirtual[i]['maker_size'], d.ordersvirtual[i]['taker'], d.ordersvirtual[i]['taker_size'], 
            d.ordersvirtual[i]['status'], (order['status'] if (order is not None) else 'no status'), d.ordersvirtual[i]['id'], d.ordersvirtual[i]['market_price'], d.ordersvirtual[i]['order_price'], d.ordersvirtual[i]['name'] ))
            
            # if virtual order is clear but order is still in progress skip this order as finished order
            if d.ordersvirtual[i]['status'] == 'clear':
                continue
            
            # if previous status was not finished or clear and now finished is or was taken by takerbot, count this order in finished number
            if d.ordersvirtual[i]['status'] != 'finished':
                if (order is not None) and order['status'] == 'finished':
                    d.ordersfinished += 1
                    d.ordersfinishedtime = time.time()
                elif feature__takerbot__virtual_order_was_taken_get(d.ordersvirtual[i]) == True:
                    d.ordersfinished += 1
                    d.ordersfinishedtime = time.time()
            
            # update "reopen finished feature" data
            events_wait_reopenfinished_update(d.ordersvirtual[i], order, feature__takerbot__virtual_order_was_taken_get(d.ordersvirtual[i]))
            
            
            # finally update virtual order status
            # if order was taken by takerbot clear virtual order
            if feature__takerbot__virtual_order_was_taken_get(d.ordersvirtual[i]) == True:
                virtual_orders__update_status(d.ordersvirtual[i], 'clear', ifnot = ['clear'])
                feature__takerbot__virtual_order_was_taken_set(d.ordersvirtual[i], False)
            # if order does not exist clear virtual order
            elif order is None:
                virtual_orders__update_status(d.ordersvirtual[i], 'clear', ifnot = ['clear'])
            # else update status of virtual order to existing order status
            else:
                virtual_orders__update_status(d.ordersvirtual[i], order['status'], ifnot = ['clear'])

# update information needed by reopen after finish feature to know how many orders are opened and how many finished
def events_wait_reopenfinished_update(virtual_order, actual_order, finished_by_takerbot):
    global c, s, d
    
    # if previous status was not open and now open is, count this order in opened number
    if virtual_order['status'] not in s.orders_pending_to_reopen_opened_statuses and (actual_order is not None) and actual_order['status'] in s.orders_pending_to_reopen_opened_statuses:
        d.orders_pending_to_reopen_opened += 1
        if d.orders_pending_to_reopen_opened > c.BOTmaxopenorders:
            print('!!!! internal BUG Detected. DEBUG orders opened {0} orders finished {1} last time order finished {2}'.format(d.orders_pending_to_reopen_opened, d.orders_pending_to_reopen_finished, d.orders_pending_to_reopen_finished_time))
            sys.exit(1)
        
    # if previous status was open and now is not open, do not count this order in opened number
    if virtual_order['status'] in s.orders_pending_to_reopen_opened_statuses and ((actual_order is None) or actual_order['status'] not in s.orders_pending_to_reopen_opened_statuses):
        d.orders_pending_to_reopen_opened -= 1
        if d.orders_pending_to_reopen_opened < 0:
            print('!!!! internal BUG Detected. DEBUG orders opened {0} orders finished {1} last time order finished {2}'.format(d.orders_pending_to_reopen_opened, d.orders_pending_to_reopen_finished, d.orders_pending_to_reopen_finished_time))
            sys.exit(1)
        
    # if previous status was not finished and now finished is, count this order in finished number
    if virtual_order['status'] != 'finished' and (((actual_order is not None) and actual_order['status'] == 'finished') or finished_by_takerbot == True):
        d.orders_pending_to_reopen_finished += 1
        d.orders_pending_to_reopen_finished_time = time.time()
    
    # ~ print('%%%% DEBUG orders opened {0} orders finished {1} last time order finished {2}'.format(d.orders_pending_to_reopen_opened, d.orders_pending_to_reopen_finished, d.orders_pending_to_reopen_finished_time))

# create order and update also corresponding virtual-order
def virtual_orders__create_one(order_id, order_name, price, slide, stageredslide, dynslide, sell_amount, sell_amount_min):
    global c, s, d
    makermarketpriceslide = float(price) * (slide + stageredslide + dynslide)
    
    # limit precision to 6 digits
    sell_amount = '%.6f' % sell_amount
    
    buyamount = (float(sell_amount) * float(makermarketpriceslide)) 
    
    # limit precision to 6 digits
    buyamount = '%.6f' % buyamount
    
    print('>>>> Placing partial<{}> Order id <{}> name <{}> {}->{} at price {} slide {} staggered-slide {} dynamic-slide {} final-price {} to sell {} n buy {}'
          .format(c.BOTpartial_orders, order_id, order_name, c.BOTsellmarket, c.BOTbuymarket, price, slide, stageredslide, dynslide, makermarketpriceslide, sell_amount, buyamount))
    
    if c.BOTpartial_orders is False:
        try:
            results = {}
            results = dxbottools.makeorder(c.BOTsellmarket, str(sell_amount), c.BOTmakeraddress, c.BOTbuymarket, str(buyamount), c.BOTtakeraddress)
            print('>>>> Order placed - id: <{}>, maker_size: <{}>, taker_size: <{}>'.format(results['id'], results['maker_size'], results['taker_size']))
            # ~ logging.info('Order placed - id: {0}, maker_size: {1}, taker_size: {2}'.format(results['id'], results['maker_size'], results['taker_size']))
        except Exception as err:
            print('ERROR: %s' % err)
    else:
        try:
            results = {}
            results = dxbottools.make_partial_order(c.BOTsellmarket, str(sell_amount), c.BOTmakeraddress, c.BOTbuymarket, str(buyamount), c.BOTtakeraddress, sell_amount_min, False)
            print('>>>> Order placed - id: <{}>, maker_size: <{}>, taker_size: <{}>'.format(results['id'], results['maker_size'], results['taker_size']))
            # ~ logging.info('Order placed - id: {0}, maker_size: {1}, taker_size: {2}'.format(results['id'], results['maker_size'], results['taker_size']))
        except Exception as err:
            print('ERROR: %s' % err)
    
    if results:
        d.ordersvirtual[order_id] = results
        d.ordersvirtual[order_id]['vid'] = order_id
        d.ordersvirtual[order_id]['status'] = 'creating'
        d.ordersvirtual[order_id]['name'] = order_name
        d.ordersvirtual[order_id]['market_price'] = price
        d.ordersvirtual[order_id]['order_price'] = makermarketpriceslide
        d.ordersvirtual[order_id]['maker_size_min'] = sell_amount_min

# recompute order tx fee (TODO)
def sell_amount_txfee_recompute(sell_amount):
    global c, s, d
    txfee = sell_amount * 0.007
    return txfee

# recompute amount available minus reserved for save and fees, also apply max and min
def balance_available_to_sell_recompute(sell_amount_max=0, sell_amount_min=0):
    global c, s, d
    
    # get available balance without fee
    sell_amount = d.balance_maker_available
    sell_amount_txfee = sell_amount_txfee_recompute(sell_amount)
    sell_amount = sell_amount - sell_amount_txfee
    sell_amount = max(sell_amount, 0)
    
    #apply BOTbalance_save_number if enabled
    if c.BOTbalance_save_number != 0:
        balance_save_size = feature__balance_save_asset__convert_to_maker(c.BOTbalance_save_number)
        sell_amount_tmp = sell_amount
        sell_amount = min(sell_amount, d.balance_maker_available - sell_amount_txfee - balance_save_size)
        sell_amount = max(sell_amount, 0)
        print('>>>> balance_save_number {} apply, sell amount original {} new {}'.format(balance_save_size, sell_amount_tmp, sell_amount))
        
    #apply BOTbalance_save_percent if enabled
    if c.BOTbalance_save_percent != 0:
        sell_amount_tmp = sell_amount
        sell_amount = min(sell_amount, d.balance_maker_available - sell_amount_txfee - (c.BOTbalance_save_percent * d.balance_maker_total))
        sell_amount = max(sell_amount, 0)
        print('>>>> balance_save_percent {} apply, sell amount original {} new {}'.format(c.BOTbalance_save_percent, sell_amount_tmp, sell_amount))
    
    # apply maximum amount if enabled
    if sell_amount_max != 0:
        sell_amount_tmp = sell_amount
        sell_amount = min(sell_amount_max, sell_amount)
        print('>>>> sell amount max {} apply, sell amount original {} new {}'.format(sell_amount_max, sell_amount_tmp, sell_amount))
    
    # apply minimum amount if enabled otherwise try to apply maximum as exact amount if enabled
    if sell_amount_min != 0:
        sell_amount_tmp = sell_amount
        if sell_amount < sell_amount_min:
            sell_amount = 0
        print('>>>> sell amount min {} apply, sell amount original {} new {}'.format(sell_amount_min, sell_amount_tmp, sell_amount))
    elif sell_amount_max != 0:
        sell_amount_tmp = sell_amount
        if sell_amount_max != sell_amount:
            sell_amount = 0
        print('>>>> strict sell amount max {} apply, sell amount original {} new {}'.format(sell_amount_max, sell_amount_tmp, sell_amount))
    
    # ~ if c.BOTmarking != 0:
        # ~ if sell_amount != 0:
            # ~ sell_amount_tmp = sell_amount
            # ~ before, after = str(sell_amount_tmp).split('.')
            # ~ sell_amount_tmp = before + "." + str(int(after))
            # ~ if sell_amount > c.BOTmarking:
    
    return sell_amount

# one time needed prepare process before switching into second internal loop 
def virtual_orders__prepare_once():
    global c, s, d
    update_balances()
    
    while pricing_update_main() == 0:
        print('#### Pricing not available... waiting to restore...')
        time.sleep(c.BOTdelayinternalerror)
    
    d.reset_on_price_change_start = d.price_maker
    
    # how many orders finished reset
    d.ordersfinished = 0
    
    d.time_start_reset_orders = time.time()
    d.ordersfinishedtime = 0
    
    d.time_start_update_pricing = time.time()
    
    events_wait_reopenfinished_reinit()

# every time main event loop pass, some dynamics should be recomputed
def virtual_orders__prepare_recheck():
    global c, s, d
    # every loop of creating or checking orders maker balance can be changed...
    update_balances()
    
    feature__slide_dynamic__update()
    
    # every loop of creating or checking orders maker price can be changed...
    while True:
        if pricing_update_main() != 0:
            break
        print('#### Pricing main not available... waiting to restore...')
        time.sleep(c.BOTdelayinternalerror)
    
    if c.BOTbalance_save_asset_track is True:
        while True:
            if feature__balance_save_asset__pricing_update() != 0:
                break
            print('#### Pricing of balance save asset not available... waiting to restore...')
            time.sleep(c.BOTdelayinternalerror)
    
    if c.BOTslide_dyn_zero_asset_track is True:
        while True:
            if feature__slide_dynamic__zero_asset_pricing_update() != 0:
                break
            print('#### Pricing of dynamic slide zero asset not available... waiting to restore...')
            time.sleep(c.BOTdelayinternalerror)
    
    while True:
        if feature__sell_size_asset__pricing_update() != 0:
            break
        print('#### Pricing of sell size asset not available... waiting to restore...')
        time.sleep(c.BOTdelayinternalerror)
    
    while True:
        if feature__boundary__pricing_update() != 0:
            break
        print('#### Pricing boundaries not available... waiting to restore...')
        time.sleep(c.BOTdelayinternalerror)
    
    events_wait_reopenfinished_reset_detect()
    
    # get open orders, match them with virtual orders, and check how many finished
    virtual_orders__check_status_update_status()

#
def feature__boundary__get_max_relative():
    global c, s, d
    
    maximum = 0
    
    if c.BOTboundary_max_relative != 0:
        if c.BOTboundary_asset_track is False:
            maximum = d.feature__boundary__price_maker_initial_center * c.BOTboundary_max_relative
        else:
            maximum = (d.feature__boundary__price_maker_initial_center_relative * d.feature__boundary__price_relative_actual) * c.BOTboundary_max_relative
        
    return maximum

#
def feature__boundary__get_max_static():
    global c, s, d
    
    maximum = float(0)
    
    if c.BOTboundary_max_static != 0:
        if c.BOTboundary_asset_track is False:
            maximum = c.BOTboundary_max_static * d.feature__boundary__price_relative_initial
        else:
            maximum = c.BOTboundary_max_static * d.feature__boundary__price_relative_actual
        
    return maximum

#
def feature__boundary__get_max():
    global c, s, d
    
    maximum = feature__boundary__get_max_relative()
    
    if maximum == 0:
        maximum = feature__boundary__get_max_static()
    
    return maximum

#
def feature__boundary__get_min_relative():
    global c, s, d
    
    minimum = 0
    
    if c.BOTboundary_min_relative != 0:
        if c.BOTboundary_asset_track is False:
            minimum = d.feature__boundary__price_maker_initial_center * c.BOTboundary_min_relative
        else:
            minimum = (d.feature__boundary__price_maker_initial_center_relative * d.feature__boundary__price_relative_actual) * c.BOTboundary_min_relative
        
    return minimum

#
def feature__boundary__get_min_static():
    global c, s, d
    
    minimum = 0
    
    if c.BOTboundary_min_static != 0:
        if c.BOTboundary_asset_track is False:
            minimum = c.BOTboundary_min_static * d.feature__boundary__price_relative_initial
        else:
            minimum = c.BOTboundary_min_static * d.feature__boundary__price_relative_actual
            
    return minimum

#
def feature__boundary__get_min():
    global c, s, d
    
    minimum = feature__boundary__get_min_relative()
    
    if minimum == 0:
        minimum = feature__boundary__get_min_static()
    
    return minimum

# recompute and get price with boundary limits
def feature__boundary__recompute_price():
    global c, s, d
    
    price = d.price_maker
    
    maximum = feature__boundary__get_max()
    minimum = feature__boundary__get_min()
    
    if maximum != 0:
        price = min(price, maximum)
    
    if minimum != 0:
        price = max(price, minimum)
    
    return price

# function to check if price is not out of maximum boundary 
def feature__boundary__hit_max():
    global c, s, d
    
    # check if relative max boundary is configured
    if c.BOTboundary_max_relative != 0:
        # wait if out of price relative boundary happen
        maximum = feature__boundary__get_max_relative()
        if maximum < d.price_maker:
            print('>>>> Maximum relative boundary <{}> hit <{}> / <{}>'.format(c.BOTboundary_max_relative, maximum, d.price_maker))
            return True
            
    # check if static max boundary is configured
    if c.BOTboundary_max_static != 0:
        # wait if out of price static boundary happen
        maximum = feature__boundary__get_max_static()
        if maximum < d.price_maker:
            print('>>>> Maximum static boundary <{}> hit <{}> / <{}>'.format(c.BOTboundary_max_static, maximum, d.price_maker))
            return True
    
    return False

# function to check if price is not out of minimum boundary 
def feature__boundary__hit_min():
    global c, s, d
    
    # check if relative min boundary is configured
    if c.BOTboundary_min_relative != 0:
        # wait if out of price relative boundary happen
        minimum = feature__boundary__get_min_relative()
        if minimum > d.price_maker:
            print('>>>> Minimum relative boundary <{}> hit <{}> / <{}>'.format(c.BOTboundary_min_relative, minimum, d.price_maker))
            return True
    
    # check if static min boundary is configured
    if c.BOTboundary_min_static != 0:
        # wait if out of price static boundary happen
        minimum = feature__boundary__get_min_static()
        if minimum > d.price_maker:
            print('>>>> Minimum static boundary <{}> hit <{}> / <{}>'.format(c.BOTboundary_min_static, minimum, d.price_maker))
            return True
    
    return False

# function to check if price is not out of maximum boundary 
def feature__boundary__hit_max_exit():
    global c, s, d
    
    if not c.BOTboundary_max_noexit:
        if feature__boundary__hit_max() == True:
            if not c.BOTboundary_max_nocancel:
                virtual_orders__cancel_all()
            return True
            
    return False

# function to check if price is not out of minimum boundary 
def feature__boundary__hit_min_exit():
    global c, s, d
    
    if not c.BOTboundary_min_noexit:
        if feature__boundary__hit_min() == True:
            if not c.BOTboundary_min_nocancel:
                virtual_orders__cancel_all()
            return True
    
    return False

# function to check if price is not out of maximum boundary 
def feature__boundary__hit_max_noexit_cancel():
    global c, s, d
    
    if c.BOTboundary_max_noexit:
        if not c.BOTboundary_max_nocancel:
            if feature__boundary__hit_max() == True:
                virtual_orders__cancel_all()
                return True
            
    return False

# function to check if price is not out of minimum boundary 
def feature__boundary__hit_min_noexit_cancel():
    global c, s, d
    
    if c.BOTboundary_min_noexit:
        if not c.BOTboundary_min_nocancel:
            if feature__boundary__hit_min() == True:
                virtual_orders__cancel_all()
                return True
    
    return False

# function to scan all events that makes bot to exit
def events_exit_bot():
    global c, s, d
    ret = False
    
    print('checking for exit bot events')
    
    # detect and handle max boundary exit event
    if feature__boundary__hit_max_exit() == True:
        ret = True
    
    # detect and handle min boundary exit event
    if feature__boundary__hit_min_exit() == True:
        ret = True
    
    return ret
    
# function to scan all events that makes bot to reset orders
def events_reset_orders():
    global c, s, d
    
    print('checking for reset order events')
    
    # if c.BOTresetonpricechangepositive is set and price has been changed, break and reset orders
    if c.BOTresetonpricechangepositive != 0 and d.price_maker >= (d.reset_on_price_change_start * (1 + c.BOTresetonpricechangepositive)):
        print('>>>> Reset on positive price change {0}% has been reached: price stored / actual {1} / {2}, going to order reset now...'.format(c.BOTresetonpricechangepositive, d.reset_on_price_change_start, d.price_maker))
        return True
        
    # if c.BOTresetonpricechangenegative is set and price has been changed, break and reset orders
    if c.BOTresetonpricechangenegative != 0 and d.price_maker <= (d.reset_on_price_change_start * (1 - c.BOTresetonpricechangenegative)):
        print('>>>> Reset on negative price change {0}% has been reached: price stored / actual {1} / {2}, going to order reset now...'.format(c.BOTresetonpricechangenegative, d.reset_on_price_change_start, d.price_maker))
        return True
    
    # if BOTresetafterdelay is set and reached break and reset orders
    if c.BOTresetafterdelay != 0 and (time.time() - d.time_start_reset_orders) > c.BOTresetafterdelay:
        print('>>>> Maximum orders lifetime {0} / {1} has been reached, going to order reset now...'.format((time.time() - d.time_start_reset_orders), c.BOTresetafterdelay))
        return True
        
    # if BOTresetafterorderfinishnumber is set and already reached break and reset orders
    if c.BOTresetafterorderfinishnumber != 0 and d.ordersfinished >= c.BOTresetafterorderfinishnumber:
        print('>>>> Maximum orders finished {0} / {1} has been reached, going to order reset...'.format(d.ordersfinished, c.BOTresetafterorderfinishnumber))
        return True
        
    #if BOTresetafterorderfinishdelay is set and already reached break and reset orders
    if c.BOTresetafterorderfinishdelay != 0 and d.ordersfinished != 0 and d.ordersfinishedtime != 0 and (time.time() - d.ordersfinishedtime) > c.BOTresetafterorderfinishdelay:
        print('>>>> Maximum orders lifetime {0} / {1} after order finished has been reached, going to order reset now...'.format((time.time() - d.ordersfinishedtime), c.BOTresetafterorderfinishdelay))
        return True
        
    return False

# automatically detect passed wait events so reset data
def events_wait_reopenfinished_reset_detect():
    global c, s, d
    
    if events_wait_reopenfinished_check_num_silent() == "reached" or events_wait_reopenfinished_check_delay_silent() == "reached":
        print(">>>> reopen after finished reseting data...")
        d.orders_pending_to_reopen_finished = 0
        d.orders_pending_to_reopen_finished_time = 0;

# function to check bot have to wait, finished orders will be reopened after specific number of filled orders
def events_wait_reopenfinished_check_num_silent():
    global c, s, d
    
    # check if finished num is configured
    if c.BOTreopenfinishednum == 0:
        return "disabled"
    
    # this feature is activated only if at least one order has finished
    if d.orders_pending_to_reopen_finished > 0:
        # this feature is activated only if there is enough finished+open orders
        if (d.orders_pending_to_reopen_finished + d.orders_pending_to_reopen_opened) >= c.BOTreopenfinishednum:
            # wait if finished number has not been reached
            if d.orders_pending_to_reopen_finished < c.BOTreopenfinishednum:
                return "wait"
            else:
                return "reached"
                
    return "not ready"

# function to check bot have to wait, finished orders will be reopened after specific number of filled orders
def events_wait_reopenfinished_check_num():
    global c, s, d
    ret = events_wait_reopenfinished_check_num_silent()
    if ret == "wait":
        print('%%%% DEBUG Reopen finished order num {0} / {1} not reached, waiting...'.format(d.orders_pending_to_reopen_finished, c.BOTreopenfinishednum))
    
    return ret
    
# function to check bot have to wait, finished orders will be reopened after specific delay
def events_wait_reopenfinished_check_delay_silent():
    global c, s, d
    
    # check if finished delay is configured
    if c.BOTreopenfinisheddelay == 0:
        return "disabled"
    
    # this feature is activated only if at least one order has finished
    if d.orders_pending_to_reopen_finished_time != 0:
        # wait if we already have some finished order time and delay not reached
        if (time.time() - d.orders_pending_to_reopen_finished_time) < c.BOTreopenfinisheddelay:
            return "wait"
        else:
            return "reached"
    
    return "not ready"

# function to check bot have to wait, finished orders will be reopened after specific delay
def events_wait_reopenfinished_check_delay():
    global c, s, d
    ret = events_wait_reopenfinished_check_delay_silent()
    if ret == "wait":
        print('%%%% DEBUG Reopen finished orders delay {0} / {1} not reached, waiting...'.format((time.time() - d.orders_pending_to_reopen_finished_time), c.BOTreopenfinisheddelay))
        
    return ret

# main reopen fisnihed delay/num detection function
def events_wait_reopenfinished_check():
    global c, s, d
    
    # check reopen after finished number or delay detection
    ret_delay = events_wait_reopenfinished_check_delay()
    ret_num = events_wait_reopenfinished_check_num()
    if ret_delay == "wait" and ret_num == "wait": # timeout did not happen but number of finished orders has been reached
        return True
    elif ret_delay == "disabled" and ret_num == "wait":
        return True
    elif ret_delay == "wait" and ret_num == "disabled":
        return True

# function to scan all events that makes bot wait
def events_wait():
    global c, s, d
    ret = False
    
    print('checking for wait events')
    
    # wait if there is not enough balance to place order and pay fee
    if balance_available_to_sell_recompute() == 0:
        ret = True
    
    # check reopen after finished number or delay detection
    if events_wait_reopenfinished_check() == True:
        ret = True
    
    # detect and handle max boundary event
    if feature__boundary__hit_max_noexit_cancel() == True:
        ret = True
    
    # detect and handle min boundary event
    if feature__boundary__hit_min_noexit_cancel() == True:
        ret = True
    
    return ret

# function to compute and return amount of maker to be sold
def sell_amount_recompute(sell_start, sell_end, order_num_all, order_num_actual, sell_type):
    global c, s, d
    
    sell_amount = float(0)
    
    # sell amount old style random
    if c.BOTsellrandom:
        sell_min = min(sell_start, sell_end)
        sell_max = max(sell_start, sell_end)
        sell_amount = random.uniform(sell_min, sell_max)
    
    # sell amount staggered
    else:
        # linear staggered orders size distribution
        if sell_type == 0:
            sell_type_res = order_num_actual / order_num_all
        
        # exponential staggered order size distribution
        elif sell_type > 0:
            sell_type_res = (order_num_actual / order_num_all)**(1-(sell_type))
        
        # logarithmic staggered order size distribution
        elif sell_type < 0:
            # ~ sell_type_res = (order_num_actual / order_num_all)**(1-(10*sell_type))
            sell_type_res = (order_num_actual / order_num_all)**((float(100)**(sell_type*-1))+(sell_type*4.4))
        
        # sell amount = amount starting point + (variable amount * intensity) 
        sell_amount = sell_start + ((sell_end - sell_start) * sell_type_res)
        # ~ sell_amount = sell_start + (( (sell_end - sell_start) / max((order_num_all-1),1) )*order_num_actual)

    # sell amount limit to 6 decimal numbers
    sell_amount = float('%.6f' % sell_amount)
    
    return sell_amount

# function to loop all virtual orders and recreate em if needed
def virtual_orders__handle():
    global c, s, d
    
    print('checking for virtual orders to handle')
    
    # loop all virtual orders and try to create em
    
    # staggered orders handling
    for i in range(s.ordersvirtualmax - int(c.BOTslidepumpenabled)):
        if d.ordersvirtual[i]['status'] in s.reopenstatuses:
            update_balances()
            
            # compute dynamic order size range, apply <sell_type> linear/log/exp on maximum amount by order number distribution
            sell_amount_max_sse = sell_amount_recompute(c.BOTsellstart, c.BOTsellend, s.ordersvirtualmax - int(c.BOTslidepumpenabled), i, c.BOTsell_type)
            sell_amount_min_sse = sell_amount_recompute(c.BOTsellstartmin, c.BOTsellendmin, s.ordersvirtualmax - int(c.BOTslidepumpenabled), i, c.BOTsell_type)
            
            # convert sell size in sell size asset to maker asset
            sell_amount_max = sell_amount_max_sse * d.feature__sell_size_asset__price
            sell_amount_min = sell_amount_min_sse * d.feature__sell_size_asset__price
            
            # recompute sell amount by available balance, other limit conditions
            sell_amount = balance_available_to_sell_recompute(sell_amount_max, sell_amount_min)
            
            # convert final amount to sell to sell size asset amount
            sell_amount_sse = sell_amount / d.feature__sell_size_asset__price
            
            # recompute price by configured boundaries
            price_maker_with_boundaries = feature__boundary__recompute_price()
            
            print('>>>> Order maker size <{}/{} {}~{} min {}~{} final {}~{}>'.format(c.BOTsellmarket, c.BOTsell_size_asset, sell_amount_max, sell_amount_max_sse, sell_amount_min, sell_amount_min_sse, sell_amount, sell_amount_sse))
            
            if sell_amount == 0:
                # do not create next order on first 0 amount hit, so if first order is not created, also next not created
                if c.BOTmake_next_on_hit is True:
                    continue
                else:
                    break
                
            # first order is min slide
            if i == 0:
                order_name = 'first staggered order with min-slide'
            # last order is max slide
            elif i == (s.ordersvirtualmax - int(c.BOTslidepumpenabled) -1):
                order_name = 'last staggered order with max-slide'
            # any other orders between min and max slide
            else:
                order_name = 'middle staggered order with computed-slide'
            
            # compute staggered orders slides
            staggeredslide = ((c.BOTslideend - c.BOTslidestart) / max((s.ordersvirtualmax -1 -int(c.BOTslidepumpenabled)),1 ))*i
            
            virtual_orders__create_one(i, order_name, price_maker_with_boundaries, c.BOTslidestart, staggeredslide, d.dynamic_slide, sell_amount, sell_amount_min)
            time.sleep(c.BOTdelayinternal)
    
    # special pump/dump order handling
    if c.BOTslidepumpenabled is True and d.ordersvirtual[s.ordersvirtualmax-1]['status'] in s.reopenstatuses:
        update_balances()
        
        # convert sell size in sell size asset to maker asset
        sell_amount_pumpdump = c.BOTpumpamount * d.feature__sell_size_asset__price
        
        # recompute sell amount by available balance, other limit conditions
        sell_amount = balance_available_to_sell_recompute(sell_amount_pumpdump, sell_amount_pumpdump)
        
        if sell_amount > 0:
            virtual_orders__create_one(s.ordersvirtualmax-1, 'pump/dump', price_maker_with_boundaries, c.BOTslidemax, c.BOTslidepump, d.dynamic_slide, sell_amount, sell_amount_min)
            
# check if virtual order was taken by takerbot
def feature__takerbot__virtual_order_was_taken_get(virtual_order):
    return virtual_order.get('takerbot', False)

# set flag that order was taker by takerbot
def feature__takerbot__virtual_order_was_taken_set(virtual_order, true_false):
    virtual_order['takerbot'] = true_false
    
#by adding takerbot feature:
#   counting reset after finish functionality is affected
#   counting reset after timeout functionality is affected
#   counting reopen finished orders after number of timeout functionality is affected
#Solution #1(prob TODO) is to reset all orders after takerbot success action, but if price action happen before it can cause bot loss.
#Solution #2(added) is to update above 4 features to know takerbot did action
#
# function to loop all already created orders, find match with thirty party created orders and accept em.
def feature__takerbot__run():
    global c, s, d
    
    print('checking for takerbot actions')
    
    ret = False
    
    # run takerbot process if feature is enabled
    if c.BOTtakerbot != 0:
        # turn on takerbot timer first
        if d.feature__takerbot__time_start == 0:
            d.feature__takerbot__time_start = time.time()
        # run takerbot on timer
        elif (time.time() - d.feature__takerbot__time_start) > c.BOTtakerbot:
            
            # get market order book type 3 format results
            fullbook = dxbottools.rpc_connection.dxGetOrderBook(3, c.BOTsellmarket, c.BOTbuymarket)
            bidlist = list(fullbook.get('bids', list([])))
            
            # convert market order book from list to dictionary format
            keys = [ 'order_price', 'size' , 'order_id' ]
            orders_market = [dict(zip(keys, bidlist_item)) for bidlist_item in bidlist ]
            
            # simulation of market order >> testing >> debug
            # ~ orders_market.append({'order_price': '0.029277', 'size': '1.98', 'order_id': '123456789'})
            
            # convert strings to floats
            for i in range(len(orders_market)):
                orders_market[i]['order_price'] = float(orders_market[i]['order_price'])
                orders_market[i]['size'] = float(orders_market[i]['size'])
            
            # filter only opened virtual orders
            orders_virtual_sorted = list()
            for i in range(len(d.ordersvirtual)):
                if d.ordersvirtual[i].get('order_price', None) is not None:
                    orders_virtual_sorted.append(d.ordersvirtual[i])
            
            # sort market order book and my order book by price
            orders_market_sorted = sorted(orders_market, key=lambda order: order['order_price'], reverse=True)
            orders_virtual_sorted = sorted(orders_virtual_sorted, key=lambda order: order['order_price'], reverse=False)
            
            # simulation >> testing >> debug
            # ~ print('\n\norders_market_sorted: <{}>'.format(orders_market_sorted))
            # ~ print('\n\norders_virtual_sorted: <{}>'.format(orders_virtual_sorted))
            
            # takerbot process. Something like limit orders layer on top of blockdx atomic swap order book.
            
            # go all market open orders sorted by best price
            err = None
            for i in range(len(orders_market_sorted)):
                print('\n *** checking order_market_sorted no <{}> <{}>\n'.format(i, orders_market_sorted[i]))
                
                maker_sum = float(0)
                order_candidates = list()
                
                # go all bot open orders, sum up bot orders to match market order size
                for j in range(len(orders_virtual_sorted)):
                    print('\n *** *** checking order_virtual_sorted no <{}> <{}>\n'.format(j, orders_virtual_sorted[j]))
                    
                    # count orders which are price better or same
                    if orders_market_sorted[i]['order_price'] >= orders_virtual_sorted[j]['order_price']:
                        # count orders which status is new/open
                        if orders_virtual_sorted[j]['status'] in s.feature__takerbot__list_of_usable_statuses:
                            # count order only if market order size at least virtual order minimum acceptable size
                            if (orders_virtual_sorted[j]['maker_size_min'] != 0 and orders_market_sorted[i]['size'] >= orders_virtual_sorted[j]['maker_size_min']) or (orders_market_sorted[i]['size'] >= float(orders_virtual_sorted[j]['maker_size'])):
                                print('\n *** *** *** order_virtual_sorted no <{}> passed requirements <{}>\n'.format(j, orders_virtual_sorted[j]))
                                
                                # add virtual order to list of candidates for takerbot to be cancelled and market order accepted
                                order_candidates.append(orders_virtual_sorted[j])
                                
                                # increase available maker amount to sell
                                maker_sum = maker_sum + float(orders_virtual_sorted[j]['maker_size'])
                                
                                # if there is enough balance and order meet requirements, try to handle situation and take order
                                if maker_sum >= float(orders_market_sorted[i]['size']):
                                    print('\n *** *** *** *** summary of makers sizes <{}> is enough for <{}>\n'.format(maker_sum, orders_market_sorted[i]['size']))
                                    # try to cancel bot orders which are dependant on takerbot action
                                    for k in range(len(order_candidates)):
                                        ret_cancelorder = dxbottools.rpc_connection.dxCancelOrder(order_candidates[k]['id'])
                                        err = ret_cancelorder.get('error', None)
                                        # in case of error we must exit whole takerbot process and let bot recreate orders
                                        if err is not None:
                                            print('\n *** *** *** *** *** cancel virtual order candidate <{}> failed <{}> \n'.format(k, err))
                                            break
                                    
                                    #try to accept order
                                    ret_takeorder = dxbottools.takeorder(orders_market_sorted[i]['order_id'], c.BOTtakeraddress, c.BOTmakeraddress)
                                    err = ret_takeorder.get('error', None)
                                    
                                    # if process success, update order candidates as accepted by takerbot
                                    if err is None:
                                        print('\n *** *** *** *** *** take market order <{}> success\n'.format(i))
                                        for k in range(len(order_candidates)):
                                            feature__takerbot__virtual_order_was_taken_set(order_candidates[k], True)
                                        ret = True
                                    # in case of error we must exit whole takerbot process and let bot recreate orders
                                    else:
                                        print('\n *** *** *** *** *** take market order <{}> failed <{}> \n'.format(i, err))
                                        break
                                else:
                                    print('\n *** *** *** *** summary of makers sizes <{}> is not enough for <{}>\n'.format(maker_sum, orders_market_sorted[i]['size']))
                    else:
                        break
                    
                    # in case of error we must exit whole takerbot process and let bot recreate orders
                    if err is not None:
                        break
                # in case of error we must exit whole takerbot process and let bot recreate orders
                if err is not None:
                    break
                
                # when takerbot checks all the open orders on the market, reset it
                if i == len(orders_market_sorted)-1:
                    d.feature__takerbot__time_start = time.time()
    
    return ret

# main function
if __name__ == '__main__':
    
    ####################################################################
    # following logic is about:
    # one time needed initialization 
    # one time needed checks
    ####################################################################
    
    start_welcome_message() # some welcome message
    
    
    init_preconfig() # initialization of config independent items or items needed for config load
    
    load_config() # load configuration from config file if specified than load program arguments with higher priority by replacing config file options
    
    init_postconfig() # initialization of items dependent on config
    
    
    do_utils_and_exit() # if some utility are planned do them and exit program
    
    
    pricing_check_or_exit() # check if pricing works
    
    
    update_balances() # update balances information
    
    feature__slide_dynamic__init_postpricing()
    
    while 1:  # primary loop, starting point, after reset-orders-events
        
        ################################################################
        # following logic is about to wait for all session orders to be 
        # canceled and cleared
        ################################################################
        
        virtual_orders__clear_all()
        
        ################################################################
        # following logic is about to prepare for order placement by:
        # updating balances
        # update pricing
        # update custom dynamic parameters
        # reset counters
        # reset timers
        ################################################################
        
        virtual_orders__prepare_once()
        
        while 1: # secondary loop, starting point for handling events and orders
            
            ############################################################
            # following loop is about to:
            # staggered orders are created 
            # pump/dump order is created
            # finished orders are recreated if needed
            # orders reset on delay/afterfinish/afterfinishdelay...
            ############################################################
        
            virtual_orders__prepare_recheck() # every time main event loop pass, specific dynamic vars should be recomputed
            
            # highest priority is to check for events that forces bot to exit
            if events_exit_bot() == True:
                sys.exit(0)
                
            # second highest priority is to check for events that forces bot to reset orders.
            elif events_reset_orders() == True:
                break
                
            # takerbot priority is before wait events which can potentially break takerbot functionality. Check for partial orders to be accepted. If some orders been takerbot accepted, bot must call prepare recheck() function again so pass is called
            elif feature__takerbot__run() == True:
                pass
                
            # check for events that forces bot to wait instead of placing orders
            elif events_wait() == True:
                pass
                
            # lowest priority after all main events is to loop all virtual orders and try to re/create them
            else:
                virtual_orders__handle()
            
            time.sleep(c.BOTdelayinternalcycle)
            
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
