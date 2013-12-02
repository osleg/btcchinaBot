#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import re
import hmac
import hashlib
import base64
import httplib
import json
import logging
import urllib2


class BTCChina():
    def __init__(self, access=None, secret=None):
        self.access_key = access
        self.secret_key = secret
        self.conn = httplib.HTTPSConnection("api.btcchina.com")
        logging.basicConfig()
        self.logger = logging.getLogger('btc.api')
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('Api initialized')
        self.logger.debug(self.conn.host)

    def _get_tonce(self):
        self.logger.debug('Getting tonce')
        return int(time.time() * 1000000)

    def _get_params_hash(self, pdict):
        pstring = ""
        # The order of params is critical for calculating a correct hash
        fields = ['tonce', 'accesskey', 'requestmethod', 'id', 'method', 'params']
        for f in fields:
            self.logger.debug('Field %s is: %s ' % (f, pdict.get(f, None)))
            if pdict[f]:
                if f == 'params':
                    # Convert list to string, then strip brackets and spaces
                    # probably a cleaner way to do this
                    param_string = re.sub("[\[\] ]", "", str(pdict[f])) # Why?! O_O
                    param_string = re.sub("'", '', param_string)
                    pstring += f + '=' + param_string + '&'
                else:
                    pstring += f + '=' + str(pdict[f]) + '&' # Adding parameters and their values
            else:
                pstring += f + '=&' # Adding empty parameter
        pstring = pstring.strip('&')
        self.logger.debug('Final string is: %s' % pstring)

        # now with correctly ordered param string, calculate hash
        phash = hmac.new(self.secret_key, pstring, hashlib.sha1).hexdigest()
        return phash

    def _private_request(self, post_data):
        #fill in common post_data parameters
        tonce = self._get_tonce()
        post_data['tonce'] = tonce
        post_data['accesskey'] = self.access_key
        post_data['requestmethod'] = 'post'

        # If ID is not passed as a key of post_data, just use tonce
        if not 'id' in post_data:
            #post_data['id'] = tonce
            post_data['id'] = '1'

        pd_hash = self._get_params_hash(post_data)

        # must use b64 encode        
        auth_string = 'Basic ' + base64.b64encode(self.access_key + ':' + pd_hash)
        self.logger.debug('Auth string is: %s ' % auth_string)
        headers = {'Authorization': auth_string, 'Json-Rpc-Tonce': tonce}
        self.logger.debug('Headers is: %s ' % headers)

        #post_data dictionary passed as JSON        
        self.conn.request("POST", '/api_trade_v1.php', json.dumps(post_data), headers)
        response = self.conn.getresponse()

        # check response code, ID, and existence of 'result' or 'error'
        # before passing a dict of results
        if response.status == 200:
            # this might fail if non-json data is returned
            resp_dict = json.loads(response.read())

            # The id's may need to be used by the calling application,
            # but for now, check and discard from the return dict
            if str(resp_dict['id']) == str(post_data['id']):
                if 'result' in resp_dict:
                    return resp_dict['result']
                elif 'error' in resp_dict:
                    return resp_dict['error']
        else:
            # not great error handling....
            print "status:", response.status
            #correcao bug
            print "reason:", response.reason
            return 'false'
        return None

    def ticker_data(self):
        data = urllib2.urlopen('https://vip.btcchina.com/bc/ticker')
        ticker = json.loads(data.read())
        return ticker

    def get_account_info(self, post_data={}):
        post_data['method'] = 'getAccountInfo'
        post_data['params'] = []
        return self._private_request(post_data)

    def get_balance(self):
        account_info = self.get_account_info()
        balance = account_info['balance']
        return balance

    def get_market_depth(self, post_data={}):
        post_data['method'] = 'getMarketDepth'
        post_data['params'] = []
        return self._private_request(post_data)

        #autor: benoni
    def get_market_depth2(self, post_data={}):
        post_data['method'] = 'getMarketDepth2'
        post_data['params'] = []
        post_data['id'] = 30
        return self._private_request(post_data)

        #

    def buy(self, price, amount, post_data={}):
        post_data['method'] = 'buyOrder'
        post_data['params'] = [price, amount]
        return self._private_request(post_data)

    def sell(self, price, amount, post_data={}):
        post_data['method'] = 'sellOrder'
        post_data['params'] = [price, amount]
        return self._private_request(post_data)

    def cancel(self, order_id, post_data={}):
        post_data['method'] = 'cancelOrder'
        post_data['params'] = [order_id]
        return self._private_request(post_data)

    def request_withdrawal(self, currency, amount, post_data={}):
        post_data['method'] = 'requestWithdrawal'
        post_data['params'] = [currency, amount]
        return self._private_request(post_data)

    def get_deposits(self, currency='BTC', pending=True, post_data={}):
        post_data['method'] = 'getDeposits'
        if pending:
            post_data['params'] = [currency]
        else:
            post_data['params'] = [currency, 'false']
        return self._private_request(post_data)

    def get_orders(self, id=None, open_only=True, post_data={}):
        # this combines getOrder and getOrders
        if id is None:
            post_data['method'] = 'getOrders'
            if open_only:
                post_data['params'] = []
            else:
                post_data['params'] = ['false']
        else:
            post_data['method'] = 'getOrder'
            post_data['params'] = [id]
        return self._private_request(post_data)

    def get_withdrawals(self, id='BTC', pending=True, post_data={}):
        # this combines getWithdrawal and getWithdrawls
        try:
            id = int(id)
            post_data['method'] = 'getWithdrawal'
            post_data['params'] = [id]
        except:
            post_data['method'] = 'getWithdrawals'
            if pending:
                post_data['params'] = [id]
            else:
                post_data['params'] = [id, 'false']
        return self._private_request(post_data)

    def get_transactions(self, post_data={}):
        post_data['method'] = 'getTransactions'
        post_data['params'] = []
        return self._private_request(post_data)    
