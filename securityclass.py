import requests
import datetime


class Security:

    def __init__(self, symbol):
        self.symbol = symbol
        self.data_pack = self.request_td_opchain()
        self.price = self.data_pack['underlying']['mark']
        self.putmap = self.data_pack['putExpDateMap']
        self.callmap = self.data_pack['callExpDateMap']
        self.expirations = self.instantiate_contracts()
        self.gex = round(self.gamma_exposure())
        self.dollar_gamma = round(self.gex * self.price, 2)

    def __str__(self):
        string = '{0.symbol:8}|${0.price:10}|{0.gex:10}|${0.dollar_gamma:15}'.format(self)
        return string

    def request_td_opchain(self):
        symbol = self.symbol
        endpoint = 'https://api.tdameritrade.com/v1/marketdata/chains'
        accesskey = ''
        payload = {'apikey': accesskey,
                   'symbol': '{}'.format(symbol),
                   'contractType': 'ALL',
                   'includeQuotes': 'TRUE',
                   'strategy': 'SINGLE',
                   'range': 'ALL'
                   }
        content = requests.get(url=endpoint, params=payload)
        print(content)
        data = content.json()
        return data

    def instantiate_contracts(self):
        expirations = {}
        for date in self.callmap:
            obj = Contract(security=self, date=date)
            expirations[obj.date[0:10]] = obj
        return expirations

    def gamma_exposure(self):
        gamma = 0
        for contract in self.expirations:
            gamma += self.expirations[contract].gex
        return gamma

    def custom_gamma(self, distance):
        gamma = 0
        for contract in self.expirations:
            if int(self.expirations[contract].days_to_expiration) <= distance:
                contractobject = self.expirations[contract]
                for strike in contractobject.calls:
                    strikeobject = contractobject.calls[strike]
                    gamma += strikeobject.gex
                for strike in contractobject.puts:
                    strikeobject = contractobject.puts[strike]
                    gamma += strikeobject.gex
        dollargamma = gamma * self.price
        return gamma, dollargamma

    def print_check(self, date):
        raw = self.data_pack
        calldatemap = raw['putExpDateMap']
        for item in calldatemap:
            print(item)
            # print(calldatemap[item])
            for thing in calldatemap[item]:

                print(thing, calldatemap[item][thing][0]['gamma'], calldatemap[item][thing][0]['openInterest'])
                date = item[0:10]
                strikeobj = self.expirations[date].puts[thing]
                print('From Program', strikeobj.strike_price, strikeobj.gamma, strikeobj.openInterest, strikeobj.gex)
        callstotal = 0
        for strike in self.expirations[date].calls:
            callstotal += self.expirations[date].calls[strike].gex
            print('new total = {}'.format(callstotal))
        print('-' * 50)
        for strike in self.expirations[date].puts:
            callstotal += self.expirations[date].puts[strike].gex
            print('new total = {}'.format(callstotal))


class Contract:

    def __init__(self, security, date):
        self.date = date
        self.days_to_expiration = self.date[11::]
        self.calls, self.puts = self.instantiate_strikes(security=security, date=date)
        self.gex = self.expiration_gamma()

    def instantiate_strikes(self, security, date):
        calls, puts = {}, {}
        for strike in security.callmap[date]:
            obj = Strike(security.callmap[date], strike, days=self.days_to_expiration)
            calls[obj.strike_price] = obj
        for strike in security.putmap[date]:
            obj = Strike(security.putmap[date], strike, days=self.days_to_expiration)
            puts[obj.strike_price] = obj
        return calls, puts

    def expiration_gamma(self):
        gamma = 0
        for strike in self.calls:
            gamma += self.calls[strike].gex
        for strike in self.puts:
            gamma += self.puts[strike].gex
        return gamma


class Strike:

    def __init__(self, dictionary, price, days):
        self.days_until_expiration = days
        self.contract = dictionary[price][0]
        self.type = self.contract['putCall']
        self.strike_price = price
        self.symbol = self.contract['symbol']
        self.iv = self.contract['volatility']
        self.volume = self.contract['totalVolume']
        self.delta = self.contract['delta']
        self.gamma = self.contract['gamma']
        self.openInterest = self.contract['openInterest']
        self.gex = 100 * self.gamma * self.openInterest
        if self.type == 'PUT':
            self.gex = -self.gex




msft = Security('$SPX.X')
for item in msft.putmap:
    print(item)

# msft.print_check(date='01-10')

# total = 0
# for expiry in msft.expirations:
#     contract_obj = msft.expirations[expiry]
#     for strike in contract_obj.calls:
#         call_obj = contract_obj.calls[strike]
#         put_obj = contract_obj.puts[strike]
#         if call_obj.strike_price == '3235.0':
#             date_strike = call_obj.gex + put_obj.gex
#             print('Date = {}, GEX = {}'.format(expiry, date_strike))
#             total += date_strike
#             print('-----new total = {}'.format(total))
# print('TOTAL = {}'.format(total))
# print('$$$ = {}'.format(total * msft.price))



# for item in msft.expirations:
#     contract = msft.expirations[item]
#     for item in contract.calls:
#         strike = contract.calls[item]
#         print(strike.symbol, strike.volume, strike.openInterest, strike.gex)
