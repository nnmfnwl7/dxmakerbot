#!/usr/bin/python3
from utils.authproxy import AuthServiceProxy, JSONRPCException
import flask.json
import decimal
import time
import calendar
import dateutil
from dateutil import parser
from utils import dxsettings

rpc_connection = AuthServiceProxy("http://%s:%s@127.0.0.1:%s"%(dxsettings.rpcuser, dxsettings.rpcpassword, dxsettings.rpcport))

class MyJSONEncoder(flask.json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            # convert decimal instances to strings
            return str(obj)
        return super(MyJSONEncoder, self).default(obj)


def lookup_order_id(orderid, myorders):
  # find my orders, returns order if orderid passed is inside myorders
  return [zz for zz in myorders if zz['id'] == orderid]


def canceloldestorder(maker, taker):
    retcode, myorders = getopenordersbymarket(maker, taker)
    oldestepoch = 3539451969
    currentepoch = 0
    epochlist = 0
    oldestorderid = 0
    if retcode == 0:
        for z in myorders:
            if z['status'] == "open":
                createdat = z['created_at']
                currentepoch = getepochtime((z['created_at']))
                if oldestepoch > currentepoch:
                    oldestorderid = z['id']
                    oldestepoch = currentepoch
                if oldestorderid != 0:
                    rpc_connection.dxCancelOrder(oldestorderid)
    return oldestorderid, oldestepoch

# cancel order specified by list
def cancel_orders_list(orders_list):
    
    retcode = 0
    
    # check if input is a list
    if isinstance(orders_list, list):
        
        # for all orders in list
        for z in orders_list:
            
            # get order ID
            order_id = z.get('id', None)
            
            # check if order has an ID
            if order_id is not None:
                
                # try to cancel order
                results = rpc_connection.dxCancelOrder(order_id)
                
                # add cancel order result to result data
                z['results'] = results
                
                # update retcode in case of cancel order errors
                err = results.get('error', None)
                if err is not None:
                    retcode = -2
                
                # ~ # print result of actual cancel order try and sleep
                # ~ print (results)
                # ~ time.sleep(3.5)
            else:
                retcode = -2
                z['results'] = {}
                z['results']['error'] = "Order ID does not exist >> id"
                z['results']['code'] = "9999"
                z['results']['name'] = "cancel_orders_list"
    else:
        retcode = -1
    
    if retcode != 0:
        print('ERROR: cancel orders list >> {0} >> {1}'.format(retcode, orders_list))
    
    return retcode, orders_list

# cancel all my open orders
def cancelallorders():
    
    # returns open orders by market
    myorders = rpc_connection.dxGetMyOrders()
    
    # check if get RPC error not been occurred
    if isinstance(myorders, list):
        
        # filter orders with status open/new
        retdata = [zz for zz in myorders if (zz['status'] == "open") or zz['status'] == "new"]
        
        # try to cancel orders
        retcode, retdata = cancel_orders_list(retdata)
    else:
        retcode = -1
        retdata = myorders
    
    if retcode != 0:
        print('ERROR: cancel all orders >> {0} >> {1}'.format(retcode, retdata))
    
    return retcode, retdata

# cancel all my open orders for specified market pair
def cancelallordersbymarket(maker, taker):
    
    # get all my open orders 
    retcode, retdata = getopenordersbymarket(maker, taker)
    
    if retcode == 0:
        
        # filter orders with status open/new
        retdata = [zz for zz in retdata if (zz['status'] == "open") or (zz['status'] == "new")]
        
        # try to cancel orders
        retcode, retdata = cancel_orders_list(retdata)
    
    if retcode != 0:
        print('ERROR: cancel all orders by market result: {0} >> {1}'.format(retcode, retdata))
    
    return retcode, retdata

# returns all my orders for specified market pair
def getallmyordersbymarket(maker, taker):
    myorders = rpc_connection.dxGetMyOrders()
    return [zz for zz in myorders if (zz['maker'] == maker) and (zz['taker'] == taker)]

# returns all my open orders for specified market pair
def getopenordersbymarket(maker, taker):
    
    # get all my orders
    myorders = rpc_connection.dxGetMyOrders()
    
    # check if get RPC error not been occurred
    if isinstance(myorders, list):
        
        retcode = 0
        # filter orders which match open/new and specified market
        myorders = [zz for zz in myorders if ((zz['status'] == "open") or (zz['status'] == "new")) and (zz['maker'] == maker) and (zz['taker'] == taker)]
    else:
        retcode = -1
    
    if retcode != 0:
        print('ERROR: get open orders by market  >> {0} >> {1}'.format(retcode, myorders))
    
    return retcode, myorders

def getopenordersbymaker(maker):
    # return orders open w/ maker 
    myorders = rpc_connection.dxGetMyOrders()
    return [zz for zz in myorders if (zz['status'] == "open") and (zz['maker'] == maker)]

def getopenorders():
    # return open orders
    myorders = rpc_connection.dxGetMyOrders()
    return [zz for zz in myorders if zz['status'] == "open"] 

def getopenorder_ids():
    # return open order IDs
    myorders = rpc_connection.dxGetMyOrders()
    return [zz['id'] for zz in myorders if zz['status'] == "open"]

def getepochtime(created):
    # converts created to epoch
    return calendar.timegm(dateutil.parser.parse(created).timetuple())
   
def getorderbook(maker, taker):
    fullbook = rpc_connection.dxGetOrderBook(3, maker, taker)
    asklist = fullbook['asks']
    bidlist = fullbook['bids']
    return (asklist, bidlist)

def getlowprice(orderlist):
    return min(orderlist, key=lambda x: x[0])

def gethighprice(orderlist):
    return max(orderlist, key=lambda x: x[0])

def makeorder(maker, makeramount, makeraddress, taker, takeramount, takeraddress):
    #
    results = rpc_connection.dxMakeOrder(maker, makeramount, makeraddress, taker, takeramount, takeraddress, 'exact')
    if 'id' in results:
      return results
    else:
      raise RuntimeError(results)

def make_partial_order(maker, makersize, makeraddress, taker, takersize, takeraddress, minimum_size, repost = True):
    results = rpc_connection.dxMakePartialOrder(maker, str(makersize), makeraddress, taker, str(takersize), takeraddress, str(minimum_size), str(repost))
    if 'id' in results:
      return results
    else:
      raise RuntimeError(results)

def takeorder(id, fromaddr, toaddr):
    results = rpc_connection.dxTakeOrder(id, fromaddr, toaddr)
    return results

def get_utxos(asset, include_used = False):
    # ~ print ('### Getting utxos list debug input: >>> dxGetUtxos({}, {})'.format(asset, include_used))
    results = rpc_connection.dxGetUtxos(asset, include_used)
    # ~ print ('### Getting utxos list debug output: >>> {}'.format(results))
    return results

# return float balance of specific token or return 0 of not exist
def get_token_balance(balances, token_name):
    return float(balances.get(token_name, 0))

def showorders():
    print ('### Getting balances >>>')
    mybalances = rpc_connection.dxGetTokenBalances()
    print (mybalances)
    print ('### Getting my orders >>>')
    myorders = rpc_connection.dxGetMyOrders()
    for z in myorders:
      print (z['status'], z['id'], z['maker'], z['maker_size'], z['taker'],z['taker_size'], float(z['taker_size'])/float(z['maker_size']))

    allorders = rpc_connection.dxGetOrders()
    print ('#############################################################')
    for z in allorders:
      # checks if your order
      if lookup_order_id(z['id'], myorders):
        ismyorder = "True"
      else:
        ismyorder = "False"
