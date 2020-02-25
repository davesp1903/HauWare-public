import scipy.stats as si
import sqlite3
import tkinter as tk
import datetime
from mpl_finance import *
import matplotlib
import matplotlib.pyplot as plt
import pytz
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import requests
import pandas as pd
import threading
import time

matplotlib.use('TkAgg')


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
        call_date_map = raw['putExpDateMap']
        for item in call_date_map:
            print(item)
            print(call_date_map[item])
            for thing in call_date_map[item]:
                print(thing, call_date_map[item][thing][0]['gamma'], call_date_map[item][thing][0]['openInterest'])
                date = item[0:10]
                strikeobj = self.expirations[date].puts[thing]
                print('From Program', strikeobj.strike_price, strikeobj.gamma, strikeobj.openInterest, strikeobj.gex)
        calls_total = 0
        for strike in self.expirations[date].calls:
            calls_total += self.expirations[date].calls[strike].gex
            print('new total = {}'.format(calls_total))
        print('-' * 50)
        for strike in self.expirations[date].puts:
            calls_total += self.expirations[date].puts[strike].gex
            print('new total = {}'.format(calls_total))


class Contract:

    def __init__(self, security, date):
        self.date = date
        self.days_to_expiration = self.trading_days_conversion(calendar_days=int(self.date[11::]))
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

    @staticmethod
    def trading_days_conversion(calendar_days):
        today = datetime.datetime.now().weekday()
        days = calendar_days

        to_subtract = 0
        count = today
        for i in range(calendar_days):
            count += 1
            if count == 7:
                count = 0
            if count in (5, 6):
                to_subtract += 1
        days -= to_subtract

        return days



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


class GammaLine:

    def __init__(self, axis, ticker):
        self.axis = axis
        self.ticker = ticker

        self.x, self.y = self.query_data()

        self.axis.plot(self.x, self.y, color='yellow')
        self.axis.set_facecolor('black')
        self.axis.grid()

    def query_data(self):
        x, y = [], []
        sql = "SELECT dollar_gamma FROM histories INNER JOIN securities ON securities.security_id" \
              " = histories.security_id WHERE securities.ticker = ? ORDER BY date"
        cwd = os.getcwd()
        path = cwd + '/GEXHISTORICAL.sqlite'
        db = sqlite3.connect(path)
        cursor = db.cursor()
        cursor.execute(sql, (self.ticker,))

        start = -30

        raw = []
        for gex_level in cursor:
            if gex_level[0] != 'N/A':
                raw.append(int(gex_level[0]))

        for gex_level in raw[-30::]:
            x.append(start)
            y.append(gex_level)
            start += 1

        return x, y

    @staticmethod
    def plot():
        plt.show()


class OptionVolumeGraph:

    def __init__(self, axis, otheraxis, symbol, sessions: list):
        self.axis = axis
        self.otheraxis = otheraxis
        self.sessions = sessions
        print(sessions)

        self.axis.patch.set_facecolor('black')
        self.axis.set_title('CALL')
        self.axis.grid(axis='x')

        self.otheraxis.patch.set_facecolor('black')
        self.otheraxis.set_title('PUT')
        self.otheraxis.grid(axis='x')

        self.symbol = symbol

        call_sessions = self.instantiate_strike_dictionaries(self.sessions)
        put_sessions = self.instantiate_strike_dictionaries(self.sessions, callput='PUT')

        cdf = pd.DataFrame(call_sessions)
        pdf = pd.DataFrame(put_sessions)

        self.offset = 0
        self.offset_p = 0

        colors = {'0': 'white', '1': '#0901ff', '2': 'red', "3": 'yellow'}

        def plot():
            for series in cdf:
                input_series = cdf[series]
                x, y = self.data_set(series=input_series)
                x = np.array(x) + self.offset
                self.axis.bar(x, y, label=series, color=colors[str(self.offset)])
                self.offset += 1

            for series in pdf:
                input_series = pdf[series]
                x, y = self.data_set(series=input_series)
                x = np.array(x) + self.offset_p
                self.otheraxis.bar(x, y, label=series, color=colors[str(self.offset_p)])
                self.offset_p += 1

            self.offset = 0
            self.offset_p = 0

        plot()

        sql = 'SELECT price FROM histories INNER JOIN securities on securities.security_id' \
              ' = histories.security_id WHERE histories.date = ? AND securities.ticker = ? ORDER BY histories.date'
        cwd = os.getcwd()
        path = cwd + '/GEXHISTORICAL.sqlite'
        db = sqlite3.connect(path)
        cursor = db.cursor()
        _, __, ___, session = get_last_session_date()
        cursor.execute(sql, (session, self.symbol,))

        current_price = float(cursor.fetchone()[0])
        cursor.close()
        db.close()

        margin = current_price * 0.10
        lower_bound, upper_bound = current_price - margin, current_price + margin

        div = round(len(np.arange(lower_bound, upper_bound))//50)

        self.axis.set_xlim(lower_bound, upper_bound)
        self.axis.set_xticks(np.arange(lower_bound, upper_bound, div))
        self.axis.tick_params(axis='x', labelrotation=40, labelsize='small')
        self.axis.legend()

        self.otheraxis.set_xlim(lower_bound, upper_bound)
        self.otheraxis.set_xticks(np.arange(lower_bound, upper_bound, div))
        self.otheraxis.tick_params(axis='x', labelrotation=40, labelsize='small')
        self.otheraxis.legend()

    @staticmethod
    def data_set(series):
        x, y = [], []
        strikes = series.index
        print(series.index)
        for strike in strikes:
            xs, ys = strike, series.loc[strike]
            x.append(float(xs))
            y.append(float(ys))

        return x, y

    def instantiate_strike_dictionaries(self, sessions: list, callput='CALL'):

        callput = callput.upper()
        _, __, ___, date2 = get_last_session_date()
        date1 = self.get_previous_day(date2)
        print(date1, date2)
        cwd = os.getcwd()
        database = cwd + "/GEXHISTORICAL.sqlite"

        def indiv_dictionary(date):
            sql = """SELECT strike_price, volume FROM chains INNER JOIN securities on
                    securities.security_id = chains.security_id WHERE securities.ticker
                     = ? AND chains.date = ? AND chains.type = ?
                     ORDER BY chains.date"""
            db = sqlite3.connect(database)
            cursor = db.cursor()

            dictionary = {}

            cursor.execute(sql, (self.symbol, date, callput))
            for strike, volume in cursor:
                if float(strike) not in dictionary.keys():
                    dictionary[float(strike)] = volume
                else:
                    dictionary[float(strike)] += volume
            cursor.close()
            db.close()
            return dictionary

        return_sets = {}
        for session in sessions:
            return_sets[session] = indiv_dictionary(session)

        return return_sets

    def get_previous_day(self, date):
        year, month, day = date.split('-')
        new_day = int(day) - 1

        if new_day <= 0:
            new_month = self.get_previous_month(month)
            if new_month in ('9', '4', '6', '11'):
                new_day = '30'
            else:
                if month == '2':
                    new_day = '28'
                else:
                    new_day = '31'
            if new_month == '0':
                new_year = str(int(year) - 1)
            else:
                new_year = year
        else:
            new_day = str(new_day)
            if int(new_day) < 10:
                new_day = '0' + new_day
            new_month = month
            new_year = year
        previous = new_year + '-' + new_month + '-' + new_day

        if datetime.date(int(new_year), int(new_month), int(new_day)).weekday() in [5, 6]:
            return self.get_previous_day(previous)
        else:
            return previous

    @staticmethod
    def get_previous_month(m):
        if m == '1':
            previous_month = '12'
        else:
            previous_month = str((int(m) - 1))

        if int(previous_month) < 10:
            previous_month = '0' + previous_month
        return previous_month

    @staticmethod
    def show():
        plt.show()


class StrikeGraph:

    def __init__(self, axis, security_object, sharesdollar='dollar'):
        self.security = security_object
        self.type = sharesdollar
        self.price = self.security.price
        self.x, self.y = self.instantiate_strike_gamma_dic()

        self.axis = axis

        self.axis.bar(self.x, self.y, color='#0971ff')
        self.axis.patch.set_facecolor('white')
        self.axis.set_title('Gamma by Strike: {}'.format(self.security.symbol))
        self.axis.set_ylabel('GEX')
        self.axis.set_xlabel('Strike')
        self.axis.grid(axis='y')

        current_price = self.price
        margin = current_price * 0.10
        lower_bound, upper_bound = current_price - margin, current_price + margin

        self.axis.set_xlim(lower_bound, upper_bound)

        length = len(np.arange(round(lower_bound), round(upper_bound), 1.0))
        margin = float(length//50)

        self.axis.set_xticks(np.arange(lower_bound, upper_bound, margin))
        self.axis.tick_params(axis='x', labelrotation=40, labelsize='small')

    def instantiate_strike_gamma_dic(self):
        strike_gamma = {}
        if market_is_open() is True:
            print('OPEN')
            for exp in self.security.expirations:
                contract_ojbect = self.security.expirations[exp]
                for strikeprice in contract_ojbect.calls:
                    call_object = contract_ojbect.calls[strikeprice]
                    put_object = contract_ojbect.puts[strikeprice]
                    total = call_object.gex + put_object.gex
                    total_dollars = total * self.security.price
                    try:
                        strike_gamma[strikeprice] += total_dollars
                    except KeyError:
                        strike_gamma[strikeprice] = total_dollars

        else:
            print('CLOSED')
            _, __, ___, session = get_last_session_date()
            sql = """SELECT strike_price, dollar_gamma FROM chains INNER JOIN securities on securities.security_id
             = chains.security_id
                    WHERE chains.date = ? AND securities.ticker = ? ORDER BY chains.strike_price"""
            cwd = os.getcwd()
            path = cwd + '/GEXHISTORICAL.sqlite'
            db = sqlite3.connect(path)
            cursor = db.cursor()
            cursor.execute(sql, (session, self.security.symbol))
            for strikeprice, gex in cursor:
                print(strikeprice, gex)
                try:
                    strike_gamma[strikeprice] += gex
                except KeyError:
                    strike_gamma[strikeprice] = gex
            cursor.close()
            db.close()
        points = []
        for key in strike_gamma:
            tup = key, strike_gamma[key]
            print(tup)
            points.append(tup)
        x, y = [], []
        for point in points:
            x.append((float(point[0])))
            y.append((float(point[1])))
        return x, y

    @staticmethod
    def show():
        plt.show()


class ExpGammaGraph:

    def __init__(self, axis, securityobj, length=500):
        self.axis = axis
        self.security = securityobj
        self.x, self.y = [], []
        for i in range(10, length, 1):
            print('{} days out: {:15}'.format(i, self.security.custom_gamma(i)[1]))
            self.x.append(i)
            self.y.append(self.security.custom_gamma(i)[1])
        self.axis.plot(self.x, self.y)
        self.axis.grid()
        self.axis.set_title('Gamma Expiry')

    def show(self):
        plt.plot(self.x, self.y)
        plt.grid()
        plt.title('$ GEX $ as a function of days until expiration: {}'.format(self.security.symbol))
        plt.xlabel('Days until Exp')
        plt.ylabel('Gamma $')
        plt.show()


class GammaDistribution:

    def __init__(self, t=1, gex='ALL', symbol='SPX', range_=False, lower=None, upper=None):
        self.time = t
        self.gex = gex
        self.symbol = symbol

        if range_ is True:
            self.lower, self.upper = lower, upper
            self.type = 'range'
            self.Xs, self.Ys, self.data_points = self.query_data()

        else:
            if self.gex == 'ALL':
                self.type = 'scatter'
                self.Xs, self.Ys, self.data_points = self.query_data()
            else:
                self.type = 'histogram'
                self.Xs, self.Ys, self.data_points, self.margin = self.query_data()

    def query_data(self):
        raw_points = []
        x, y, data_points = [], [], []
        cwd = os.getcwd()
        database = cwd + '/GEXHISTORICAL.sqlite'
        db = sqlite3.connect(database)
        sql_statement = 'SELECT dollar_gamma, price FROM histories INNER JOIN securities on securities.security_id' \
                        ' = histories.security_id WHERE securities.ticker = ? ORDER BY date'
        cursor = db.cursor()
        sym = self.symbol
        if sym == 'SPY':
            sym = '$SPX.X'
        cursor.execute(sql_statement, (sym,))

        for X, Y in cursor:
            try:
                raw_points.append(tuple([float(X), float(Y)]))
            except ValueError:
                raw_points.append(tuple([X, Y]))

        if self.type == 'scatter':
            for point in raw_points:
                try:
                    index = raw_points.index(point)
                    future_point = raw_points[index + self.time]
                    if point[0] not in [0, 'N/A'] and future_point[0] not in [0, 'N/A']:
                        percentage_move = ((future_point[1] - point[1]) / point[1]) * 100
                        y.append(percentage_move)
                        x.append(point[0])
                        data_points.append([point[0], percentage_move])
                    # print(point[0], percentage_move)
                except IndexError:
                    continue
            return x, y, data_points
        elif self.type == 'histogram':

            margin = 0.15
            while len(data_points) < 30:
                margin += 0.01
                upperbound, lowerbound = self.gex + (self.gex * margin), self.gex - (self.gex * margin)
                x, y, data_points = [], [], []
                for point in raw_points:
                    tx, ty = point[0], point[1]
                    test = False
                    if ty not in [0, 'N/A'] and tx not in [0, 'N/A']:
                        if self.gex > 0:
                            if tx <= upperbound and tx >= lowerbound:
                                test = True
                        if self.gex < 0:
                            if tx >= upperbound and tx <= lowerbound:
                                test = True
                    if test is True:
                        try:
                            index = raw_points.index(point)
                            future_point = raw_points[index + self.time]
                            if ty not in [0, 'N/A'] and future_point[1] not in [0, 'N/A']:
                                percentage_move = ((future_point[1] - ty) / ty) * 100
                                y.append(percentage_move)
                                x.append(tx)
                                data_points.append([tx, percentage_move])
                        except IndexError:
                            continue
        elif self.type == 'range':
            print('RANGE')

            x, y, data_points = [], [], []
            for point in raw_points:
                print(point)
                if 'N/A' not in point:
                    if self.lower <= point[0] <= self.upper:
                        print('SCORE')
                        try:
                            future_point = raw_points[raw_points.index(point) + self.time]
                        except IndexError:
                            continue

                        if 'N/A' not in future_point:
                            tx, ty = point[0], point[1]
                            fx, fy = future_point[0], future_point[1]
                            percentage_move = ((fy - ty)/ty) * 100
                            x.append(tx)
                            y.append(percentage_move)
                            data_points.append([tx, percentage_move])

            return x, y, data_points

        cursor.close()
        db.close()
        return x, y, data_points, margin

    def show(self, axis, bins=100, tkint=False):
        if self.type == 'scatter':
            axis.scatter(self.Xs, self.Ys, color='black')
            axis.grid(axis='y')

        elif self.type == 'histogram':
            axis.hist(self.Ys, bins=bins, color='black')
            axis.set_title('Distribution of Returns: GEX: {} +/- {}% (N = {})'.format(
                self.gex, round((self.margin * 100)), len(self.data_points)))
            axis.set_ylabel('Number of Observations')
            axis.set_xlabel('Percentage Return')
            axis.grid(axis='x')

        elif self.type == 'range':
            axis.hist(self.Ys, bins=bins, color='black')
            axis.set_title('Distribution of {}-day Returns: GEX {} - {} (N={})'.format(self.time, self.lower,
                                                                                       self.upper,
                                                                                       len(self.data_points)))
            axis.set_ylabel('Number of Observations')
            axis.set_xlabel('Percentage Return')
            axis.grid(axis='x')

        if tkint is False:
            plt.show()


class Volatility:

    def __init__(self, spot, strike_obj: Strike, distribution: GammaDistribution, r=0.02, callput='call'):
        self.S = spot
        self.K = float(strike_obj.strike_price)
        self.r = r
        self.percent_to_strike = (self.K - self.S) / self.S * 100
        self.callPut = callput
        if self.callPut == 'call':
            if self.percent_to_strike > 0:
                self.itm = False
            else:
                self.itm = True
        else:
            if self.percent_to_strike < 0:
                self.itm = False
            else:
                self.itm = True
        print('{}'.format(self.callPut), 'ITM = {}'.format(self.itm), '|', '{}'.format(self.percent_to_strike))
        self.T = float(strike_obj.days_until_expiration)/263
        self.iv = strike_obj.iv
        self.distribution = distribution

    def get_gxv(self):
        print("STRIKE = {}".format(self.K))
        option_mean_return = self.option_mean(self.distribution.Ys, self.K, self.percent_to_strike, itm=self.itm)
        print('OPTION MEAN: {}'.format(option_mean_return))
        money_ness = self.moneyness(self. distribution.Ys, self.percent_to_strike, itm=self.itm)
        print('MONEYNESS: {}'.format(money_ness))
        fair_price = option_mean_return * money_ness
        print('FairPrince: {}'.format(fair_price))
        gxv = self.iv_from_black_sholes(fair_price, s=self.S, k=self.K, t=self.T, r=self.r, _type=self.callPut)
        print('GXV = {}'.format(gxv))
        print('-' * 50)
        return gxv

    def get_gxv_recursion(self):
        print("STRIKE = {}".format(self.K))
        option_mean_return = self.option_mean(self.distribution.Ys, self.K, self.percent_to_strike, itm=self.itm)
        print('OPTION MEAN: {}'.format(option_mean_return))
        money_ness = self.moneyness(self. distribution.Ys, self.percent_to_strike, itm=self.itm)
        print('MONEYNESS: {}'.format(money_ness))
        fair_price = option_mean_return * money_ness
        print('FairPrince: {}'.format(fair_price))
        gxv = self.iv_recursion(fair_price, s=self.S, k=self.K, t=self.T, r=self.r, _type=self.callPut)
        print('GXV = {}'.format(gxv))
        print('-' * 300)
        return gxv

    @staticmethod
    def black_sholes(s, k, t, sigma, r=0.02, ):

        d1 = (np.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        d2 = (np.log(s / k) + (r - 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))

        call = (s * si.norm.cdf(d1, 0.0, 1.0) - k * np.exp(-r * t) * si.norm.cdf(d2, 0.0, 1.0))
        put = (k * np.exp(-r * t) * si.norm.cdf(-d2, 0.0, 1.0) - s * si.norm.cdf(-d1, 0.0, 1.0))

        return call, put, sigma

    def iv_from_black_sholes(self, option_price, s, k, t, r=0.02, _type='call'):

        sigma = 0.001
        call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        if _type == 'call':
            while option_price > call:
                sigma += 0.0001
                call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        else:
            while option_price > put:
                sigma += 0.0001
                call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        return sigma

    def option_mean(self, listed, strike_price, percentage, itm=False):
        security_at = self.S
        money = []
        if itm is False:
            for datum in listed:
                if percentage >= 0:
                    test = datum >= percentage
                else:
                    test = datum <= percentage
                if test is True:
                    dollarvalue = abs((((datum/100) * security_at) + security_at) - strike_price)
                    money.append(dollarvalue)
        elif itm is True:
            for datum in listed:
                if percentage <= 0:
                    test = datum >= percentage
                else:
                    test = datum <= percentage
                if test is True:
                    dollarvalue = abs((((datum/100) * security_at) + security_at) - strike_price)
                    money.append(dollarvalue)
        if len(money) > 0:
            mean = np.mean(money)
        else:
            mean = 0
        return mean

    @staticmethod
    def moneyness(listed, threshold, itm=False):
        total, observed = len(listed), []
        if itm is False:
            if threshold > 0:
                for item in listed:
                    if item >= threshold:
                        observed.append(item)
            elif threshold < 0:
                for item in listed:
                    if item <= threshold:
                        observed.append(item)
            moneyness = len(observed)/total

        elif itm is True:
            percentage_to_broke = threshold
            if percentage_to_broke < 0:
                for item in listed:
                    if item <= percentage_to_broke:
                        observed.append(item)
            elif percentage_to_broke > 0:
                for item in listed:
                    if item >= percentage_to_broke:
                        observed.append(listed)
            moneyness = 1 - (len(observed)/total)

        return moneyness

    def iv_recursion(self, option_price, s, k, t, r=0.02, _type='call'):
        sigma_range = range(100000)

        def search(option_price_to_find, rang):
            print('-' * 50)
            print(option_price_to_find)
            rang1 = rang
            midpoint = len(rang1) // 2

            print('R: ({}, {})'.format(rang1[0], rang1[-1]))
            print('MIDPOINT = {}'.format(midpoint))
            upper = rang1[midpoint::]
            lower = rang1[0:midpoint]
            try:
                print('UPPER" ({}, {})'.format(upper[0], upper[-1]))
                print('LOWER: ({}, {})'.format(lower[0], lower[-1]))
            except IndexError:
                pass

            test_sigma = rang1[midpoint]
            print('TEST SIGMA = {}'.format(test_sigma))

            call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=test_sigma / 10000)

            if option_price_to_find == 0.0:
                return 0.00

            if midpoint == 0:
                print('RETURNING END OF RECURSION')
                return sigma

            print(call, put, sigma)

            if _type == 'call':

                if call == option_price_to_find:
                    print('RETURNING FOUND EQUIVALENT')
                    return sigma
                elif call < option_price_to_find:
                    return search(option_price_to_find, upper)
                elif call > option_price_to_find:
                    return search(option_price_to_find, lower)
            else:

                if put == option_price_to_find:
                    print('RETURNING FOUND EQUIVALENT')
                    return sigma
                elif put < option_price_to_find:
                    return search(option_price_to_find, upper)
                elif put > option_price_to_find:
                    return search(option_price_to_find, lower)

        gxv = search(option_price, sigma_range)
        print('GXV = {}'.format(gxv))
        return gxv


class IvGraph:

    def __init__(self, securityobj, exp, axis, call_color='#248d6b', put_color='#df5966', mw=1, ms='-', gw=4,
                 gs='-', bc='#e3e3e3'):

        current_price = securityobj.price
        margin = current_price * 0.05
        lower_bound, upper_bound = current_price - margin, current_price + margin

        self.security = securityobj
        self.exp = exp
        self.axis = axis

        self.marketCalls, self.marketPuts = self.market_curves()
        self.marketCalls, self.marketPuts = self.scrape(self.marketCalls, lower_bound, upper_bound), self.scrape(
            self.marketPuts, lower_bound, upper_bound)

        self.gxvCalls, self.gxvPuts, self.distribution = self.gxv_curves()
        self.gxvCalls, self.gxvPuts = self.scrape(self.gxvCalls, lower_bound, upper_bound), self.scrape(
            self.gxvPuts, lower_bound, upper_bound)

        self.mcXs, self.mcYs = self.split(self.marketCalls)
        self.mpXs, self.mpYs = self.split(self.marketPuts)

        self.gammaCallXs, self.gammaCallYs = self.split(self.gxvCalls)
        self.gammaPutXs, self.gammaPutYs = self.split(self.gxvPuts)

        self.axis.plot(self.mpXs, self.mpYs, color=put_color, alpha=0.5, lw=mw, linestyle=ms, label="Market Puts")
        self.axis.plot(self.mcXs, self.mcYs, color=call_color, alpha=0.5, lw=mw, linestyle=ms, label='Market Calls')

        self.axis.plot(self.gammaCallXs, self.gammaCallYs, color=call_color, lw=gw, linestyle=gs, label='GXV Calls')
        self.axis.plot(self.gammaPutXs, self.gammaPutYs, color=put_color, lw=gw, linestyle=gs, label='GXV Puts')

        self.axis.set_title('{} Volatility Curves {}'.format(self.security.symbol, self.exp))
        self.axis.set_ylabel('Implied Volatility')
        self.axis.set_xlabel('Strike')
        self.axis.grid()
        self.axis.patch.set_facecolor(bc)
        self.axis.legend()

        for item in self.gxvCalls:
            print(item)

        self.axis.set_xlim(lower_bound, upper_bound)

    def market_curves(self):
        calls, puts = [], []
        for contract in self.security.expirations:

            if self.exp in contract:
                contractobj = self.security.expirations[contract]
                for strike in contractobj.calls:
                    strikeobj = contractobj.calls[strike]
                    calls.append([float(strikeobj.strike_price), strikeobj.iv])
                for strike in contractobj.puts:
                    strikeobj = contractobj.puts[strike]
                    puts.append([float(strikeobj.strike_price), strikeobj.iv])

        return calls, puts

    def gxv_curves(self):
        calls, puts = [], []
        for contract in self.security.expirations:
            if self.exp in contract:
                contract_obj = self.security.expirations[contract]
                print(contract)
            else:
                print('not_found error', self.exp, contract)

        T = int(contract_obj.days_to_expiration)
        gammaexposure = self.security.dollar_gamma
        if self.security.symbol == 'SPY' or self.security.symbol == '$SPX.X':
            if market_is_open() is True:
                gammaexposure = Security('$SPX.X').dollar_gamma
            else:
                cwd = os.getcwd()
                database = cwd + '/GEXHISTORICAL.sqlite'
                db = sqlite3.connect(database)
                cursor = db.cursor()
                _, __, ___, last_date = get_last_session_date()
                print(last_date)
                sql = """SELECT dollar_gamma FROM histories INNER JOIN securities
                     on securities.security_id = histories.security_id WHERE securities.ticker
                      = '$SPX.X' AND date = ?"""
                cursor.execute(sql, (last_date,))
                for item in cursor:
                    print(item, type(item))
                    gammaexposure = item[0]
        distribution = GammaDistribution(t=T, gex=gammaexposure, symbol=self.security.symbol)

        for strike in contract_obj.calls:
            print(strike)
            strike_obj = contract_obj.calls[strike]
            gxv = Volatility(spot=self.security.price, strike_obj=strike_obj, distribution=distribution,
                             callput='call').get_gxv_recursion()
            print(gxv)
            if gxv < 0.01:
                gxv = 0
            if gxv > .001:
                calls.append([float(strike_obj.strike_price), 100 * gxv])

        for strike in contract_obj.puts:
            print(strike)
            strike_obj = contract_obj.puts[strike]
            gxv = Volatility(spot=self.security.price, strike_obj=strike_obj, distribution=distribution,
                             callput='put').get_gxv_recursion()
            print(gxv)
            if gxv < 0.01:
                gxv = 0
            if gxv > .001:
                puts.append([float(strike_obj.strike_price), 100 * gxv])
        return calls, puts, distribution

    @staticmethod
    def scrape(line, minimum, maximum):
        new_line = []

        for point in line:
            x, y = point[0], point[1]
            if minimum <= x <= maximum:
                new_line.append(point)
        return new_line

    @staticmethod
    def split(line):
        x, y = [], []
        for point in line:
            if point[1] != 5.0:
                x.append(point[0])
                y.append(point[1])
        return x, y

    @staticmethod
    def black_sholes(s, k, t, sigma, r=0.02, ):

        d1 = (np.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        d2 = (np.log(s / k) + (r - 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))

        call = (s * si.norm.cdf(d1, 0.0, 1.0) - k * np.exp(-r * t) * si.norm.cdf(d2, 0.0, 1.0))
        put = (k * np.exp(-r * t) * si.norm.cdf(-d2, 0.0, 1.0) - s * si.norm.cdf(-d1, 0.0, 1.0))

        return call, put, sigma

    def iv_from_black_sholes(self, option_price, s, k, t, r=0.02, _type='call'):
        sigma = 0.0001
        call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        if _type == 'call':
            while option_price > call:
                sigma += 0.0001
                call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        else:
            while option_price > put:
                sigma += 0.0001
                call, put, sigma = self.black_sholes(s=s, k=k, t=t, sigma=sigma, r=r)
        return sigma

    @staticmethod
    def show():
        plt.show()


fig1 = plt.figure()
ax1 = fig1.add_subplot(211)
ax12 = fig1.add_subplot(212)

fig2 = plt.figure()
ax2 = fig2.add_subplot()

fig4, ax4 = plt.subplots()
fig5, ax5 = plt.subplots()
fig6, ax6 = plt.subplots()
fig7, ax7 = plt.subplots()
fig8 = plt.figure()
ax8 = fig8.add_subplot(211)
ax9 = fig8.add_subplot(212)

dist_fig, dist_ax = plt.subplots()

gamma_fig = plt.figure()
gax = gamma_fig.add_subplot()


last = '$SPX.X'


def get_last_session_date():

    def get_previous_month(m):
        if m == '1':
            previous_month = '12'
        else:
            previous_month = str((int(m) - 1))
        return previous_month

    timezone = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(tz=timezone)
    year = str(now.year)
    month = str(now.month)
    day = now.day
    day_of_the_week = now.weekday()
    # market_open = now.replace(hour=9, minute=0, second=0)
    market_close = now.replace(hour=16, minute=0, second=0)
    if now < market_close:
        day -= 1
        day_of_the_week -= 1
        if day_of_the_week == -1:
            day_of_the_week = 6

    # this method differs from the similar method in the DarkIndex class.
    # This method will return today's date, provided it is not the weekend, and the market has closed.
    if day_of_the_week == 5:
        day -= 1
    elif day_of_the_week == 6:
        day -= 2
    if day <= 0 and month in ('5', '7', '10', '12'):
        day = day + 30
        month = get_previous_month(month)
    elif day <= 0 and month not in ('5', '7', '10', '12', '3'):
        day = day + 31
        month = get_previous_month(month)
    elif day <= 0 and month == '3':
        day = day + 28
        month = get_previous_month(month)

    day = str(day)

    if int(month) < 10:
        month = '0' + month
    if int(day) < 10:
        day = '0' + day
    formatted_date = year + '-' + month + '-' + day
    return year, month, day, formatted_date


def market_is_open():
    tz = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(tz=tz)
    if 0 <= now.weekday() <= 4:
        if 10 <= now.hour <= 15:

            market_open = True
        elif now.hour == 9:

            if now.minute >= 30:
                market_open = True
            else:
                market_open = False
        elif now.hour == 16:

            if now.minute <= 15:
                market_open = True
            else:
                market_open = False
        else:

            market_open = False
    else:

        market_open = False
    return market_open


class HauVolatilityApp(tk.Toplevel):

    def __init__(self, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, **kwargs)
        self.title('HauWare')
        container = tk.Frame(self)
        container.pack(side='top', fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.geometry('200x375')
        self.frames = {}

        for F in (LivePage, GxvPage, ChainDataPage, DistributionPage, OptionVolumePage, GexInfoPage, DatabasePage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky='nsew')

        self.sizes = {LivePage: '200x375', GxvPage: '750x600', ChainDataPage: '1300x400', DistributionPage: '800x300',
                      OptionVolumePage: '1300x700', GexInfoPage: '1100x500', DatabasePage: '400x700'}
        self.show_frame(LivePage)

    def show_frame(self, container):
        frame = self.frames[container]
        self.geometry(self.sizes[container])
        frame.tkraise()


class LivePage(tk.Frame):

    def __init__(self, parent, controller):

        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text='HauWare v~2.0.2',)

        self.button_frame = tk.Frame(self)
        self.button_frame.pack()

        image = tk.PhotoImage(file='Zoomed.png')
        self.live_gex = tk.Label(self.button_frame, text='GEX: ....')

        image_label = tk.Label(self.button_frame, image=image)
        image_label.image = image

        self.live_gex.grid(row=0, column=0)
        image_label.grid(row=1, column=0)

        button = tk.Button(self.button_frame, text='GXV VERTICAL SKEW', command=lambda: controller.show_frame(GxvPage),
                           height=1, width=17)
        button2 = tk.Button(self.button_frame, text='OPTION CHAINS',
                            command=lambda: controller.show_frame(ChainDataPage), height=1, width=17)
        button3 = tk.Button(self.button_frame, text='DISTRIBUTION',
                            command=lambda: controller.show_frame(DistributionPage), height=1, width=17)

        button4 = tk.Button(self.button_frame, text='OPTION VOLUME', command=lambda:
                            controller.show_frame(OptionVolumePage), height=1, width=17)
        button5 = tk.Button(self.button_frame, text='ANALYZE GEX', command=lambda: controller.show_frame(GexInfoPage),
                            height=1, width=17)
        button6 = tk.Button(self.button_frame, text='DATABASE', command=lambda: controller.show_frame(DatabasePage),
                            height=1, width=17)

        self.go_live = tk.Button(self.button_frame, text='GO LIVE', command=self.update_gex)

        self.go_live.grid(row=2, column=0)
        button5.grid(row=3, column=0)
        button.grid(row=4, column=0)
        button2.grid(row=5, column=0)
        button3.grid(row=6, column=0)
        button4.grid(row=7, column=0)
        button6.grid(row=8, column=0)

        label.pack(padx=10, pady=10)

    @staticmethod
    def request_td_price_history(symbol):
        # now = datetime.datetime.now().timestamp()
        # start = now - 86400
        endpoint = 'https://api.tdameritrade.com/v1/marketdata/{}/pricehistory'.format(symbol)
        accesskey = 'RJGZGRIGBKYCFJEYJBI6LPFSY6OGPCYF'
        payload = {'apikey': accesskey,
                   'periodType': 'day',
                   'period': '1',
                   'frequencyType': 'minute',
                   'frequency': '1',
                   }
        content = requests.get(url=endpoint, params=payload)
        data = content.json()
        return data

    def set_gex_label(self, value):
        self.live_gex.configure(text=value)

    def update_gex(self):
        self.go_live.destroy()

        def commify(string):
            string = str(string)
            try:
                dollars, cents = string.split('.')
            except ValueError:
                dollars, cents = string, '00'
            new_string = ''
            for character in reversed(dollars):
                new_string += character
                test_string = ''
                for char in new_string:
                    if char != ',':
                        test_string += char
                if len(test_string) % 3 == 0:
                    new_string += ','
            returnable = ''
            for char in reversed(new_string):
                returnable += char
            returnable = returnable + '.' + cents
            if returnable[0] == ',':
                returnable = returnable[1::]

            return returnable

        if market_is_open() is True:

            self.set_gex_label(value='GEX: ${}'.format(commify(Security('$SPX.X').dollar_gamma)))

            def sub_thread():

                while True:
                    time.sleep(2)
                    try:
                        self.set_gex_label(value='GEX: ${}'.format(commify(Security('$SPX.X').dollar_gamma)))
                    except TypeError:
                        pass

            sub_thread = threading.Thread(target=sub_thread)
            sub_thread.start()

        else:
            cwd = os.getcwd()
            database = cwd + '/GEXHISTORICAL.sqlite'
            db = sqlite3.connect(database)
            cursor = db.cursor()
            _, __, ___, last_date = get_last_session_date()
            print(last_date)
            sql = """SELECT dollar_gamma FROM histories INNER JOIN securities
                 on securities.security_id = histories.security_id WHERE securities.ticker = '$SPX.X' AND date = ?"""
            cursor.execute(sql, (last_date,))
            item = cursor.fetchone()
            gex = item[0]

            self.set_gex_label(value='GEX: ${}'.format(commify(gex) + '(C)'))
            cursor.close()
            db.close()


class GxvPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        button_frame = tk.Frame(self)
        button_frame.pack()

        custom_frame = tk.Frame(self)
        custom_frame.pack()

        button = tk.Button(button_frame, text='Home', command=lambda: self.home_command(control=controller))
        button.grid(row=0, column=0)

        self.var1 = tk.IntVar()
        custom_check = tk.Checkbutton(custom_frame, text='Customize', variable=self.var1)
        custom_check.grid(row=0, column=0)

        self.market_style = tk.Entry(custom_frame, width=4, text='MSty')
        self.market_width = tk.Entry(custom_frame, width=4)
        self.gamma_style = tk.Entry(custom_frame, width=4)
        self.gamma_width = tk.Entry(custom_frame, width=4)
        self.put_color = tk.Entry(custom_frame, width=7)
        self.call_color = tk.Entry(custom_frame, width=7)
        self.background = tk.Entry(custom_frame, width=7)

        market_style_label = tk.Label(custom_frame, text='MS:')
        market_style_label.grid(row=0, column=1)
        self.market_style.grid(row=0, column=2)

        market_width_label = tk.Label(custom_frame, text='MW:')
        market_width_label.grid(row=0, column=3)
        self.market_width.grid(row=0, column=4)

        gamma_style_label = tk.Label(custom_frame, text='GS:')
        gamma_style_label.grid(row=0, column=5)
        self.gamma_style.grid(row=0, column=6)

        gamma_width_label = tk.Label(custom_frame, text='GW:')
        gamma_width_label.grid(row=0, column=7)
        self.gamma_width.grid(row=0, column=8)

        call_color_label = tk.Label(custom_frame, text='CC:')
        call_color_label.grid(row=0, column=9)
        self.call_color.grid(row=0, column=10)

        put_color_label = tk.Label(custom_frame, text='PC:')
        put_color_label.grid(row=0, column=11)
        self.put_color.grid(row=0, column=12)

        background_label = tk.Label(custom_frame, text='BG:')
        background_label.grid(row=0, column=13)
        self.background.grid(row=0, column=14)

        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')

        self.security_entry = tk.Entry(button_frame)
        self.date = tk.Entry(button_frame)
        self.go_button = tk.Button(button_frame, text='Graph', command=self.graph)

        self.security_entry.grid(row=0, column=1)
        self.date.grid(row=0, column=2)
        self.go_button.grid(row=0, column=3)

    def home_command(self, control):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)

    def graph(self):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')

        ax2.clear()

        ticker = self.security_entry.get()
        date = self.date.get()

        security_obj = Security(ticker)
        if security_obj.symbol == 'SPY':
            alternate_obj = Security('$SPX.X')
        else:
            alternate_obj = security_obj

        contracts = []
        for contract in security_obj.expirations:
            contracts.append(contract)

        for number in contracts:
            if date in number:
                index = contracts.index(number)

        if self.var1.get() == 0:
            IvGraph(axis=ax2, exp=date, securityobj=security_obj)
        else:
            IvGraph(axis=ax2, exp=date, securityobj=security_obj, call_color=self.call_color.get(),
                    put_color=self.put_color.get(), mw=int(self.market_width.get()), ms=self.market_style.get(),
                    gs=self.gamma_style.get(), gw=int(self.gamma_width.get()), bc=self.background.get())

        canvas = FigureCanvasTkAgg(figure=fig2, master=self.graph_frame)
        canvas.get_tk_widget().pack(fill='both', expand='true')
        canvas.draw()

        toolbar = NavigationToolbar2Tk(canvas, self.graph_frame)
        toolbar.update()
        canvas._tkcanvas.pack()


class ChainDataPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        button_frame = tk.Frame(self)
        button_frame.pack()

        self.security_entry = tk.Entry(button_frame)
        self.date_entry = tk.Entry(button_frame)

        self.marketOpen = market_is_open()

        self.list_frame = tk.Frame(self)
        self.list_frame.pack()

        button = tk.Button(button_frame, text='Home', command=lambda: self.home_command(control=controller))

        command_button = tk.Button(button_frame, text='Populate', command=self.populate)

        self.gex_label = tk.Label(button_frame, text='GEX')

        button.grid(row=0, column=0)
        self.security_entry.grid(row=0, column=1)
        self.date_entry.grid(row=0, column=2)
        command_button.grid(row=0, column=3)

    def home_command(self, control):
        self.list_frame.destroy()
        self.list_frame = tk.Frame(self)
        self.list_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)

    def populate(self):
        self.list_frame.destroy()
        self.list_frame = tk.Frame(self)
        self.list_frame.pack()

        ticker = self.security_entry.get()

        security = Security(ticker)
        self.gex = security.dollar_gamma
        if security.symbol == 'SPY' or security.symbol == '$SPX.X':
            if self.marketOpen is True:
                self.gex = Security('$SPX.X').dollar_gamma
            else:
                cwd = os.getcwd()
                database = cwd + '/GEXHISTORICAL.sqlite'
                db = sqlite3.connect(database)
                cursor = db.cursor()
                _, __, ___, last_date = get_last_session_date()
                print(last_date)
                sql = """SELECT dollar_gamma FROM histories INNER JOIN securities
                 on securities.security_id = histories.security_id WHERE securities.ticker = '$SPX.X' AND date = ?"""
                cursor.execute(sql, (last_date,))
                for item in cursor:
                    self.gex = item[0]

        for date in security.expirations:
            if self.date_entry.get() in date:
                contract_obj = security.expirations[date]

        price = security.price
        lowest = 100
        loweset_strike = 100
        for item in contract_obj.calls.keys():
            difference = abs(float(item)-price)
            if difference < lowest:
                lowest = difference
                loweset_strike = item

        key_list = sorted(contract_obj.calls.keys())
        middle = key_list.index(loweset_strike)
        lower, upper = middle - 21, middle + 19
        key_list = key_list[lower:upper]

        rows = []

        for strike in key_list:
            call_obj = contract_obj.calls[strike]
            put_obj = contract_obj.puts[strike]
            one = tk.Label(self.list_frame, text=round(call_obj.iv, 2), borderwidth=1, relief='sunken', width=6)
            two = tk.Label(self.list_frame, text=round(100 * Volatility(security.price, call_obj, distribution=GammaDistribution(t=int(call_obj.days_until_expiration), gex=self.gex, symbol=security.symbol)).get_gxv_recursion(), 2), borderwidth=1, relief='sunken', width=6)
            three = tk.Label(self.list_frame, text=call_obj.strike_price, borderwidth=3, relief='sunken', width=6)
            four = tk.Label(self.list_frame, text=round(put_obj.iv, 2), borderwidth=1, relief='sunken', width=6)
            five = tk.Label(self.list_frame, text=round(100 * Volatility(security.price, put_obj, distribution=GammaDistribution(t=int(put_obj.days_until_expiration), gex=self.gex, symbol=security.symbol), callput='put').get_gxv_recursion(), 2), borderwidth=1, relief='sunken', width=6)
            row = (one, two, three, four, five)
            rows.append(row)

        set_1 = rows[0:10]
        set_2 = rows[10:20]
        set_3 = rows[20:30]
        set_4 = rows[30:40]

        call_label_1 = tk.Label(self.list_frame, text='CALL', borderwidth=3, relief='sunken', width=13,
                                background='green')
        call_label_2 = tk.Label(self.list_frame, text='CALL', borderwidth=3, relief='sunken', width=13,
                                background='green')
        call_label_3 = tk.Label(self.list_frame, text='CALL', borderwidth=3, relief='sunken', width=13,
                                background='green')
        call_label_4 = tk.Label(self.list_frame, text='CALL', borderwidth=3, relief='sunken', width=13,
                                background='green')

        put_label_1 = tk.Label(self.list_frame, text='PUT', borderwidth=3, relief='sunken', width=13, background='red')
        put_label_2 = tk.Label(self.list_frame, text='PUT', borderwidth=3, relief='sunken', width=13, background='red')
        put_label_3 = tk.Label(self.list_frame, text='PUT', borderwidth=3, relief='sunken', width=13, background='red')
        put_label_4 = tk.Label(self.list_frame, text='PUT', borderwidth=3, relief='sunken', width=13, background='red')

        strike_label_1 = tk.Label(self.list_frame, text='STRIKE', borderwidth=3, relief='sunken')
        strike_label_2 = tk.Label(self.list_frame, text='STRIKE', borderwidth=3, relief='sunken')
        strike_label_3 = tk.Label(self.list_frame, text='STRIKE', borderwidth=3, relief='sunken')
        strike_label_4 = tk.Label(self.list_frame, text='STRIKE', borderwidth=3, relief='sunken')

        rowstart = 1
        columnstart = 0

        for i in range(4):
            tk.Label(self.list_frame, text='IV', borderwidth=3, relief='sunken', width=6).grid(row=rowstart,
                                                                                               column=columnstart)
            tk.Label(self.list_frame, text='GXV', borderwidth=3, relief='sunken', width=6).grid(row=rowstart,
                                                                                                column=columnstart+1)
            tk.Label(self.list_frame, text='Price', borderwidth=3, relief='sunken', width=6).grid(row=rowstart,
                                                                                                  column=columnstart+2)
            tk.Label(self.list_frame, text='IV', borderwidth=3, relief='sunken', width=6).grid(row=rowstart,
                                                                                               column=columnstart+3)
            tk.Label(self.list_frame, text='GXV', borderwidth=3, relief='sunken', width=6).grid(row=rowstart,
                                                                                                column=columnstart+4)
            columnstart += 5

        call_label_1.grid(row=0, column=0, columnspan=2)
        strike_label_1.grid(row=0, column=2, columnspan=1)
        put_label_1.grid(row=0, column=3, columnspan=2)

        call_label_2.grid(row=0, column=5, columnspan=2)
        strike_label_2.grid(row=0, column=7, columnspan=1)
        put_label_2.grid(row=0, column=8, columnspan=2)

        call_label_3.grid(row=0, column=10, columnspan=2)
        strike_label_3.grid(row=0, column=12, columnspan=1)
        put_label_3.grid(row=0, column=13, columnspan=2)

        call_label_4.grid(row=0, column=15, columnspan=2)
        strike_label_4.grid(row=0, column=17, columnspan=1)
        put_label_4.grid(row=0, column=18, columnspan=2)

        rstart = 2
        for row in set_1:
            cstart = 0

            for item in row:
                item.grid(column=cstart, row=rstart)
                cstart += 1
            rstart += 1

        rstart = 2
        for row in set_2:
            cstart = 5

            for item in row:
                item.grid(column=cstart, row=rstart)
                cstart += 1
            rstart += 1

        rstart = 2
        for row in set_3:
            cstart = 10

            for item in row:
                item.grid(column=cstart, row=rstart)
                cstart += 1
            rstart += 1

        rstart = 2
        for row in set_4:
            cstart = 15

            for item in row:
                item.grid(column=cstart, row=rstart)
                cstart += 1
            rstart += 1

        self.gex_label.configure(text='GEX = {}'.format(self.gex))
        self.gex_label.grid(row=0, column=6)


class DistributionPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text='Distributions')
        label.pack()

        button_frame = tk.Frame(self)
        button_frame.pack(side='top')

        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(side='bottom', fill='both', expand='true')

        self.security_box = tk.Entry(button_frame, text="$SPX.X")

        self.gamma_box = tk.Entry(button_frame)
        self.time_box = tk.Entry(button_frame, width=5)
        self.bins_box = tk.Entry(button_frame, text='100', width=5)

        button = tk.Button(button_frame, text='Home', command=lambda: self.home_command(control=controller))
        button2 = tk.Button(button_frame, text='Graph', command=self.graph)

        button.grid(row=0, column=0)
        self.security_box.grid(row=0, column=1)
        self.gamma_box.grid(row=0, column=2)
        self.time_box.grid(row=0, column=3)
        button2.grid(row=0, column=4)
        self.bins_box.grid(row=0, column=5)

    def home_command(self, control):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)

    def graph(self):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(side='bottom', fill='both', expand='true')
        dist_ax.clear()

        gex = self.gamma_box.get()

        if gex != 'ALL':
            bins = int(self.bins_box.get())
        else:
            bins = 100

        gex = self.gamma_box.get()

        if '>' not in gex:
            if gex != 'ALL':
                gex = int(gex)
            distribution = GammaDistribution(t=int(self.time_box.get()), gex=gex, symbol=self.security_box.get())

        else:
            lower, upper = gex.split('>')
            lower, upper = int(lower), int(upper)
            distribution = GammaDistribution(t=int(self.time_box.get()), symbol=self.security_box.get(), gex=gex,
                                             range_=True, lower=lower, upper=upper)

        distribution.show(dist_ax, tkint=True, bins=bins)

        canvas = FigureCanvasTkAgg(figure=dist_fig, master=self.graph_frame)
        canvas.get_tk_widget().pack(fill='both', expand='true')
        canvas.draw()

        toolbar = NavigationToolbar2Tk(canvas, self.graph_frame)
        toolbar.update()
        canvas._tkcanvas.pack()


class OptionVolumePage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text='OPTION VOLUME DAY TO DAY')
        label.pack()

        button_frame = tk.Frame(self)
        button_frame.pack()

        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')

        back_button = tk.Button(button_frame, text="Home",
                                command=lambda: self.home_command(control=controller))
        self.entry_box = tk.Entry(button_frame)
        command_button = tk.Button(button_frame, text='Graph', command=self.graph)

        # check boxes
        _, __, ___, last_session = get_last_session_date()
        one_day_ago = self.get_previous_day(last_session)
        two_days_ago = self.get_previous_day(one_day_ago)
        three_days_ago = self.get_previous_day(two_days_ago)

        var1 = tk.IntVar()
        var2 = tk.IntVar()
        var3 = tk.IntVar()
        var4 = tk.IntVar()

        self.checkbox1 = tk.Checkbutton(master=button_frame, text=last_session, variable=var1)
        self.checkbox2 = tk.Checkbutton(master=button_frame, text=one_day_ago, variable=var2)
        self.checkbox3 = tk.Checkbutton(master=button_frame, text=two_days_ago, variable=var3)
        self.checkbox4 = tk.Checkbutton(master=button_frame, text=three_days_ago, variable=var4)

        self.check_list = {last_session: var1, one_day_ago: var2, two_days_ago: var3, three_days_ago: var4}

        back_button.grid(row=0, column=0)
        self.entry_box.grid(row=0, column=1)
        command_button.grid(row=0, column=2)

        self.checkbox1.grid(row=0, column=3)
        self.checkbox2.grid(row=0, column=4)
        self.checkbox3.grid(row=0, column=5)
        self.checkbox4.grid(row=0, column=6)

    def home_command(self, control):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)

    def graph(self):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')
        ax8.clear()
        ax9.clear()

        sessions_list = []

        for check in self.check_list:
            if self.check_list[check].get() == 1:
                sessions_list.append(check)

        symbol = self.entry_box.get()
        OptionVolumeGraph(axis=ax8, otheraxis=ax9, symbol=symbol, sessions=sessions_list)

        fig8.tight_layout()

        canvas = FigureCanvasTkAgg(figure=fig8, master=self.graph_frame)
        canvas.get_tk_widget().pack(fill='both', expand='true')
        canvas.draw()


        toolbar = NavigationToolbar2Tk(canvas, self.graph_frame)
        toolbar.update()
        canvas._tkcanvas.pack()

    def get_previous_day(self, date):
        year, month, day = date.split('-')
        new_day = int(day) - 1

        if new_day <= 0:
            new_month = self.get_previous_month(month)
            if new_month in ('9', '4', '6', '11'):
                new_day = '30'
            else:
                if month == '2':
                    new_day = '28'
                else:
                    new_day = '31'
            if new_month == '0':
                new_year = str(int(year) - 1)
            else:
                new_year = year
        else:
            new_day = str(new_day)
            if int(new_day) < 10:
                new_day = '0' + new_day
            new_month = month
            new_year = year
        previous = new_year + '-' + new_month + '-' + new_day

        if datetime.date(int(new_year), int(new_month), int(new_day)).weekday() in [5, 6]:
            return self.get_previous_day(previous)
        else:
            return previous

    @staticmethod
    def get_previous_month(m):
        if m == '1':
            previous_month = '12'
        else:
            previous_month = str((int(m) - 1))

        if int(previous_month) < 10:
            previous_month = '0' + previous_month

        return previous_month


class GexInfoPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        button_frame = tk.Frame(self)
        button_frame.pack()

        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')

        back_button = tk.Button(button_frame, text='Home', command=lambda: self.home_command(control=controller))
        self.security_entry = tk.Entry(button_frame)
        graph_button = tk.Button(button_frame, text='Graph', command=self.graph)

        back_button.grid(row=0, column=0)
        self.security_entry.grid(row=0, column=1)
        graph_button.grid(row=0, column=2)

        self.var1, self.var2 = tk.IntVar(), tk.IntVar()
        line_check = tk.Checkbutton(master=button_frame, variable=self.var1)
        strike_check = tk.Checkbutton(master=button_frame, variable=self.var2)

        line_label = tk.Label(button_frame, text='GEX Historical')
        strike_label = tk.Label(button_frame, text='GEX by Strike')

        line_label.grid(row=0, column=3)
        line_check.grid(row=0, column=4)
        strike_label.grid(row=0, column=5)
        strike_check.grid(row=0, column=6)

    def graph(self):
        gax.clear()
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')

        if self.var1.get() == 1:
            GammaLine(gax, ticker=self.security_entry.get())
        elif self.var2.get() == 1:
            StrikeGraph(axis=gax, security_object=Security(self.security_entry.get()))

        gamma_fig.tight_layout()

        canvas = FigureCanvasTkAgg(figure=gamma_fig, master=self.graph_frame)
        canvas.get_tk_widget().pack(fill='both', expand='true')
        canvas.draw()

        toolbar = NavigationToolbar2Tk(canvas, self.graph_frame)
        toolbar.update()
        canvas._tkcanvas.pack()

    def home_command(self, control):
        self.graph_frame.destroy()
        self.graph_frame = tk.Frame(self)
        self.graph_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)


class DatabasePage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        button_frame = tk.Frame(self)
        button_frame.pack()

        self.list_frame = tk.Frame(self)
        self.list_frame.pack(fill='both', expand='True')

        home_button = tk.Button(button_frame, text='Home', command=lambda: self.home_command(control=controller))
        home_button.grid(row=0, column=0)
        self.security_entry = tk.Entry(button_frame)
        self.security_entry.grid(row=0, column=1)
        chains_button = tk.Button(button_frame, text='Chains', command=self.chains_command)
        chains_button.grid(row=0, column=2)
        histories_button = tk.Button(button_frame, text='Histories', command=self.histories_command)
        histories_button.grid(row=0, column=3)

        self.list_box = tk.Listbox(self.list_frame)
        self.list_box.pack(fill='both', expand='True')

    def home_command(self, control):
        self.list_frame.destroy()
        self.list_frame = tk.Frame(self)
        self.list_frame.pack(fill='both', expand='true')
        control.show_frame(LivePage)

    def chains_command(self):
        self.list_box.destroy()
        self.list_box = tk.Listbox(self.list_frame)
        self.list_box.pack(fill='both', expand='True')

        security = self.security_entry.get()
        cwd = os.getcwd()
        database = cwd + '/GEXHISTORICAL.sqlite'
        db = sqlite3.connect(database)
        cursor = db.cursor()
        sql = """SELECT * FROM chains INNER JOIN securities
                 on securities.security_id = chains.security_id WHERE securities.ticker = ? ORDER BY date"""

        cursor.execute(sql, (security,))
        for row in cursor:
            item = ''
            for element in row:
                item += str(element)
                item += '|'
            self.list_box.insert('end', item)
            self.list_box.insert('end', ('-' * 60))

        cursor.close()
        db.close()

    def histories_command(self):
        self.list_box.destroy()
        self.list_box = tk.Listbox(self.list_frame)
        self.list_box.pack(fill='both', expand='True')

        security = self.security_entry.get()
        cwd = os.getcwd()
        database = cwd + '/GEXHISTORICAL.sqlite'
        db = sqlite3.connect(database)
        cursor = db.cursor()
        sql = """SELECT * FROM histories INNER JOIN securities
                 on securities.security_id = histories.security_id WHERE securities.ticker = ? ORDER by date"""

        cursor.execute(sql, (security,))
        for row in cursor:
            item = ''
            for element in row:
                item += str(element)
                item += '|'
            self.list_box.insert('end', item)
            self.list_box.insert('end', ('-' * 60))

        cursor.close()
        db.close()


application = HauVolatilityApp()
application.mainloop()
