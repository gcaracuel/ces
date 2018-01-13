from bittrex.bittrex import *
from models import *
from exceptions import ExchangeAPIException

class BittrexWrapper:
    def __init__(self, api_key, api_secret):
        self._handle = Bittrex(api_key, api_secret)
        self._markets = {}
        self._currencies = {}
        self._load_markets()

    def _add_currency(self, code, name):
        self._currencies[code] = Currency(code, name)

    def _make_market_name(self, base_currency_code, market_currency_code):
        return '{0}-{1}'.format(base_currency_code, market_currency_code)

    def _load_markets(self):
        result = self._handle.get_markets()
        for market in result['result']:
            base_currency = market['BaseCurrency']
            market_currency = market['MarketCurrency']
            if base_currency not in self._markets:
                self._markets[base_currency] = set()
            self._markets[base_currency].add(market_currency)
            self._add_currency(market_currency, market['MarketCurrencyLong'])
            self._add_currency(base_currency, market['BaseCurrencyLong'])

    def _check_result(self, result):
        if not result['success']:
            raise ExchangeAPIException(result['message'])

    def get_base_currencies(self):
        return [self._currencies[x] for x in self._markets.keys()]

    def get_markets(self, base_currency_code):
        if base_currency_code not in self._markets:
            raise Exception('Invalid base currency {0}'.format(base_currency_code))
        return [self._currencies[x] for x in self._markets[base_currency_code]]

    def get_market_state(self, base_currency_code, market_currency_code):
        market_name = self._make_market_name(base_currency_code, market_currency_code)
        result = self._handle.get_ticker(market_name)
        self._check_result(result)
        data = result['result']
        return MarketState(data['Ask'], data['Bid'], data['Last'])

    def get_orderbook(self, base_currency_code, market_currency_code):
        market_name = self._make_market_name(base_currency_code, market_currency_code)
        result = self._handle.get_orderbook(market_name)
        self._check_result(result)
        data = result['result']
        buy_orderbook = Orderbook()
        sell_orderbook = Orderbook()
        for item in data['buy']:
            buy_orderbook.add_order(Order(item['Rate'], item['Quantity']))
        for item in data['sell']:
            sell_orderbook.add_order(Order(item['Rate'], item['Quantity']))
        return (buy_orderbook, sell_orderbook)

    def get_wallets(self):
        result = self._handle.get_balances()
        self._check_result(result)
        output = []
        for data in result['result']:
            currency = data['Currency']
            # Shouldn't happen. TODO: log this
            if currency not in self._currencies:
                continue
            balance = Wallet(
                self._currencies[currency],
                data['Balance'],
                data['Available'],
                data['Pending'],
                data['CryptoAddress']
            )
            output.append(balance)
        return output

    def get_wallet(self, currency_code):
        result = self._handle.get_balance(currency_code)
        self._check_result(result)
        data = result['result']
        return Wallet(
            self._currencies[currency_code],
            data['Balance'],
            data['Available'],
            data['Pending'],
            data['CryptoAddress']
        )
