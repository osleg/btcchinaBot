# -*- coding: utf-8 -*-
__author__ = 'Alex Kir'

import logging
from time import sleep
import sys
from urllib2 import URLError
from datetime import datetime

import btcchina

import settings


def timestamp_string():
    return "[" + datetime.now().strftime("%I:%M:%S %p") + "]"


class ExchangeInterface:
    def __init__(self, access, secret, dry_run):
        self.dry_run = dry_run
        self.btc = btcchina.BTCChina(secret=secret, access=access)
        self.USD_DECIMAL_PLACES = 5

    def cancel_all_orders(self):
        if self.dry_run: return

        trade_data = self.btc.get_orders()
        sleep(1)
        orders = trade_data['result']['order']
        for order in orders:
            typestring = 'sell' if order['type'] == 'bid' else 'buy'
            print timestamp_string(), 'Cancelling:', typestring, order['ammoutn'], '@', order['price']
            while True:
                try:
                    self.btc.cancel(order['id'])
                    sleep(1)
                except URLError as e:
                    print e.reason
                    sleep(10)
                except ValueError as e:
                    print e
                    sleep(10)
                else:
                    break

    def get_ticker(self):
        print "Getting Ticker"
        ticker = self.btc.ticker_data()["ticker"]
        return {"last": float(ticker["last"]), "buy": float(ticker["buy"]), "sell": float(ticker["sell"])}

    def get_trade_data(self):
        if self.dry_run:
            btc = float(settings.DRY_BTC)
            cny = float(settings.DRY_CNY)
            orders = []
        else:
            while True:
                try:
                    balance = self.btc.get_balance()
                    trade_data = self.btc.get_orders()
                    sleep(1)
                except URLError as e:
                    print e.reason
                    sleep(10)
                except ValueError as e:
                    print e
                    sleep(10)
                else:
                    break

            btc = float(balance['btc'])
            cny = float(balance['cny'])
            orders = []

            for o in trade_data['order']:
                print o
                order = {'id': o['id'], 'price': float(o['price']), 'ammount': float(o['ammount'])}
                order['type'] = 'sell' if o['type'] == "bid" else "buy"
                orders.append(order)

        return {'btc': btc, 'cny': cny, 'orders': orders}

    def place_order(self, price, ammount, order_type):
        if settings.DRY_RUN:
            print timestamp_string(), order_type.capitalize() + ':', ammount, '@', price
            return None

        if order_type == 'buy':
            order = self.btc.buy(price, ammount)
            print order['result']
            order_id = order['id']
        elif order_type == 'sell':
            order = self.btc.sell(price, ammount)['id']
            print order['result']
            order_id = order['id']
        else:
            print 'Invalid Order type: ', order_type
            exit()

        print timestamp_string(), order_type.capitalize() + ':', ammount, '@', price
        return order_id

class OrderManager:
    def __init__(self):
        logging.basicConfig()
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('Init OrderManager')
        self.exchange = ExchangeInterface(settings.API_ACCESS, settings.API_SECRET, settings.DRY_RUN)
        self.start_time = datetime.now()
        self.reset()

    def reset(self):
        self.logger.debug("Reseting")
        self.exchange.cancel_all_orders()
        self.orders = {}

        ticker = self.exchange.get_ticker()
        self.logger.debug("-----TICKER-----")
        self.logger.debug(ticker)
        self.start_position = ticker["last"]
        trade_data = self.exchange.get_trade_data()
        self.logger.debug(trade_data)
        self.start_btc = trade_data["btc"]
        self.start_cny = trade_data["cny"]
        self.logger.info((timestamp_string(), "BTC:", self.start_btc, "  CNY:", self.start_cny))

        # Sanity check:
        if self.get_position(-1) >= ticker["sell"] or self.get_position(1) <= ticker["buy"]:
            self.logger.info(self.start_position)
            self.logger.info(self.get_position(-1), ticker["sell"], self.get_position(1), ticker["buy"])
            self.logger.info("Sanity check failed, exchange data is screwy")
            exit()

        for i in range(1, settings.ORDER_PAIRS + 1):
            self.place_order(-i, "buy")
            self.place_order(i, "sell")

        if settings.DRY_RUN:
            exit()

    def get_position(self, index):
        self.logger.debug("Getting Position")
        return round(self.start_position * (1 + settings.INTERVAL) ** index, self.exchange.USD_DECIMAL_PLACES)

    def place_order(self, index, order_type):
        self.logger.debug("Placing Order")
        position = self.get_position(index)
        order_id = self.exchange.place_order(position, settings.ORDER_SIZE, order_type)
        self.orders[index] = {"id": order_id, "type": order_type}

    def check_orders(self):
        self.logger.debug('Checking Order')
        trade_data = self.exchange.get_trade_data()
        order_ids = [o["id"] for o in trade_data["orders"]]
        old_orders = self.orders.copy()
        print_status = False

        for index, order in old_orders.iteritems():
            if order["id"] not in order_ids:
                self.logger.info("Order filled, id:", order["id"])
                del self.orders[index]
                if order["type"] == "buy":
                    self.place_order(index + 1, "sell")
                else:
                    self.place_order(index - 1, "buy")
                print_status = True

        num_buys = 0
        num_sells = 0

        for order in self.orders.itervalues():
            if order["type"] == "buy":
                num_buys += 1
            else:
                num_sells += 1

        if num_buys < settings.ORDER_PAIRS:
            low_index = min(self.orders.keys())
            if num_buys == 0:
                # No buy orders left, so leave a gap
                low_index -= 1
            for i in range(1, settings.ORDER_PAIRS - num_buys + 1):
                self.place_order(low_index - i, "buy")

        if num_sells < settings.ORDER_PAIRS:
            high_index = max(self.orders.keys())
            if num_sells == 0:
                # No sell orders left, so leave a gap
                high_index += 1
            for i in range(1, settings.ORDER_PAIRS - num_sells + 1):
                self.place_order(high_index + i, "sell")

        if print_status:
            btc = trade_data["btc"]
            cny = trade_data["cny"]
            self.logger.info("Profit:", btc - self.start_btc, "BTC,", cny - self.start_cny, "CNY   Run Time:",
                             datetime.now() - self.start_time)

    def run_loop(self):
        self.logger.debug('Running loop')
        while True:
            sleep(60)
            self.check_orders()
            sys.stdout.write(".")
            sys.stdout.flush()


om = OrderManager()
om.run_loop()