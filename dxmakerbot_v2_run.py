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

import time
import subprocess
import argparse
import sys

# main function
if __name__ == '__main__':
    
    # parse configuration argument
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='python configuration file', default=None)
    parser.add_argument('--cancelall', help='cancel all orders and exit', action='store_true')
    parser.add_argument('--cancelmarket', help='cancel all orders in market specified by --config file pair', action='store_true')
    args = parser.parse_args()
    config = args.config
    cancelall = args.cancelall
    cancelmarket = args.cancelmarket
    
    # check if configuration argument is set
    if config is None:
        print("[E] --config file <{}>".format(config))
        sys.exit(1)
    
    print("[I] --config file <{}>".format(config))
    
    # try to import configuration file
    cfg = __import__(config)
    
    # check configuration file
    if not cfg.botconfig:
        print("[E] --config is invalid")
        sys.exit(1)
    
    print("[I] --config <{}>".format(cfg.botconfig))
    
    # update configuration to be valid
    botconfig = cfg.botconfig.replace(" --", "--")
    botconfig = botconfig.replace("--", " --")
    
    # check if cancel all or market orders orders
    cancel_orders_arg = ""
    if cancelall:
        cancel_orders_arg = "--cancelall"
    elif cancelmarket:
        cancel_orders_arg = "--cancelmarket"
        
    # run dxmakerbot process:
    # case1: if exception rises, try to recover from situation, cancel all open orders and restart dxmakerbot process again
    # case2: if exit success, exit program
    while 1:
        # run dxmakerbot
        print("[I] starting dxmakerbot")
        result = subprocess.run("python3 dxmakerbot_v2.py" + botconfig + " " + cancel_orders_arg, shell=True)
        # if dxmakerbot process exit success exit program
        if result.returncode == 0:
            break
        
        # if dxmakerbot process exit with error try to cancel all existing orders
        while 1:
            # cancel all orders
            print("[W] dxmakerbot crashed, clearing open orders")
            result2 = subprocess.run("python3 dxmakerbot_v2.py" + botconfig + " --cancelmarket", shell=True)
            # check if cancel all orders success or try to do it again
            if result2.returncode == 0:
                break
            # wait a while on error to try again
            print("[W] dxmakerbot crash >> recovery try >> cancel orders >> internal error >> failed")
            time.sleep(3)
        
        # wait a while
        time.sleep(3)
        
        
