from binance.client import Client
from binance.um_futures import UMFutures
from binance.exceptions import BinanceAPIException
import talib  # индикаторы, инфо по паттернам

import time, math
import numpy as np
import pandas as pd
# import numpy, pandas as np, pd

from config import api_key, api_secret

# pyTelegramBotAPI==4.14.0
from telebot import TeleBot
# from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# python-dotenv
import os
from dotenv import load_dotenv

load_dotenv()

################## БОТ НА БЭБКИ ##################

token = os.getenv("TOKEN")
admin_id = os.getenv("ADMIN")

bot = TeleBot(token)

################## БОТ НА БЭБКИ ##################

# создаешь клиентов
client = UMFutures(key=api_key, secret=api_secret)
sub_client = Client(api_key, api_secret)

# указываем пару, интервал для свечей
SYMBOL = 'API3USDT'
INTERVAL_1 = '15m'
# INTERVAL_2 = '5m'

# настройки индикаторов - rsi, скользящие средние
rsi_period = 14
rsi_ma_period = 5
rsi_ma_period_B = 7

USDT_VOLUME = 15

TAKE_PROFIT_LONG = 1.1
STOP_LOSS_LONG = 0.98
TAKE_PROFIT_SHORT = 0.9
STOP_LOSS_SHORT = 1.02

def get_data_15():
    """Получаем данные о закрытии свечей на 15 мин. интервале
        Возвращаемое значение:
            binary_sum (np.array):
    """

    klines = client.klines(symbol=SYMBOL, interval=INTERVAL_1, limit=200)
    return_data = []
    for each in klines:
        return_data.append(float(each[4]))
    return np.array(return_data)


# def get_data_5():
#     """Получаем данные о закрытии свечей на 5 мин. интервале"""
#     klines = client.klines(SYMBOL, interval=INTERVAL_2, limit=200)
#     return_data = []
#     for each in klines:
#         return_data.append(float(each[4]))
#     return np.array(return_data)


def get_precision(info):
    precision = None

    for item in info['symbols']:
        if item['symbol'] == SYMBOL:
            precision = item['quantityPrecision']
            # Вывод точности
            break

    if precision is not None:
        print("Symbol: {}, Quantity Precision: {}".format(SYMBOL, precision))
        text_precision = f"Symbol: {SYMBOL}, Quantity Precision: {precision}"
    else:
        print("Symbol '{}' not found in the information.".format(SYMBOL))
        text_precision = f"Symbol '{SYMBOL}' not found in the information."

    return precision


def get_current_price():
    current_price = float(client.ticker_price(symbol=SYMBOL)['price'])
    text_current_price = f'Текущая цена: {current_price}'
    print(text_current_price)
    return current_price


def get_data_conditions():
    try:
        closing_data_15 = get_data_15()
        # closing_data_5 = get_data_5()
        rsi_15 = talib.RSI(closing_data_15, rsi_period)
        rsi_ma_15 = talib.SMA(rsi_15, rsi_ma_period)
        rsi_ma_15_B = talib.SMA(rsi_15, rsi_ma_period_B)
        # rsi_5 = talib.RSI(closing_data_5, rsi_period)
        # rsi_ma_5_B = talib.SMA(rsi_5, rsi_ma_period_B)

        params = {
            'l_rsi_15': rsi_15[-2:-1],
            'l_rsi_ma_15': rsi_ma_15[-2:-1],
            'l_rsi_ma_15_B': rsi_ma_15_B[-2:-1],

            'p_rsi_15': rsi_15[-3:-2],
            'p_rsi_ma_15': rsi_ma_15[-3:-2],
            'p_rsi_ma_15_B': rsi_ma_15_B[-3:-2],

            # 'p_rsi_5': rsi_5[-3:-2],
            # 'p_rsi_ma_5_B': rsi_ma_5_B[-3:-2],
            #
            # 'l_rsi_5': rsi_5[-2:-1],
            # 'l_rsi_ma_5_B': rsi_ma_5_B[-2:-1],
        }
        return params

    except:
        time.sleep(20)
        return


def strategy():
    print('Старт')

    precision = get_precision(sub_client.futures_exchange_info())
    current_price = get_current_price()
    print('Текущая цена: ', current_price)
    order_amount = USDT_VOLUME / current_price
    qty = float("{:.{}f}".format(order_amount, precision))
    print('Qty = ', qty)

    try:
        trade_params = get_data_conditions()
        l_rsi_15 = trade_params['l_rsi_15']
        l_rsi_ma_15 = trade_params['l_rsi_ma_15']
        p_rsi_15 = trade_params['p_rsi_15']
        p_rsi_ma_15 = trade_params['p_rsi_ma_15']

    except BinanceAPIException as e:
        print(e)
        bot.send_message(admin_id, e)
        time.sleep(20)
        return

    # хранение условий - вошли в сделку
    exit, tp, sl = [False, False, False]

    # вход в лонг - покупаем-продаем
    # if current_price > 0.20:
    if (l_rsi_15 > l_rsi_ma_15 and p_rsi_15 < p_rsi_ma_15): #убраны ограничения по величине рси
        order = client.new_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=qty)
        print(f'LONG {order}')
        # bot.send_message(admin_id, 'Вход в Long')

        trades = client.get_account_trades(symbol=SYMBOL, limit=1)
        last_trade = trades[0]
        buyprice = float(last_trade['price'])

        text_long = f'Вход в Long, {SYMBOL}\nЦена покупки: {buyprice}\nTake profit (+{round(TAKE_PROFIT_LONG * 100 - 100, 1)}%): {round(buyprice * TAKE_PROFIT_LONG, 5)}\nStop loss ({STOP_LOSS_LONG * 100 - 100}%): {round(buyprice * STOP_LOSS_LONG, 5)}'
        print(text_long)
        bot.send_message(admin_id, text_long)

        open_position = True

        while open_position:
            try:
                trade_params = get_data_conditions()
                l_rsi_15 = trade_params['l_rsi_15']
                l_rsi_ma_15 = trade_params['l_rsi_ma_15']
                p_rsi_15 = trade_params['p_rsi_15']
                p_rsi_ma_15 = trade_params['p_rsi_ma_15']

                l_rsi_ma_15_B = trade_params['l_rsi_ma_15_B']
                p_rsi_ma_15_B = trade_params['p_rsi_ma_15_B']
                # l_rsi_5 = trade_params['l_rsi_5']
                # l_rsi_ma_5_B = trade_params['l_rsi_ma_5_B']
                # p_rsi_5 = trade_params['p_rsi_5']
                # p_rsi_ma_5_B = trade_params['p_rsi_ma_5_B']

                # get_current_price()
                current_price = get_current_price()

            except BinanceAPIException as e:
                print(e)
                bot.send_message(admin_id, e)
                time.sleep(20)
                continue

            except:
                bot.send_message(admin_id, 'Неизвестная ошибка')
                time.sleep(20)
                continue

            # продаем
            if not exit and (l_rsi_15 < l_rsi_ma_15_B and p_rsi_15 > p_rsi_ma_15_B):
                order = client.new_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=qty)
                exit_L_text = f'Exit Long, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_L_text)
                bot.send_message(admin_id, exit_L_text)
                exit = True
            if not tp and (current_price >= buyprice * TAKE_PROFIT_LONG):
                order = client.new_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=qty)
                exit_tpL_text = f'Exit Long Take profit, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_tpL_text)
                bot.send_message(admin_id, exit_tpL_text)
                tp = True
            if not sl and (current_price <= buyprice * STOP_LOSS_LONG):
                order = client.new_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=qty)
                exit_slL_text = f'Exit Long Stop loss, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_slL_text)
                bot.send_message(admin_id, exit_slL_text)
                sl = True
            if exit or tp or sl:
                open_position = False
                print('Сделка закрыта')
                bot.send_message(admin_id, 'Сделка закрыта')
                time.sleep(60)

            time.sleep(3)

    # вход в шорт, продаем - покупаем
    exit, tp, sl = [False, False, False]
    # if current_price > 0.20:
    if (l_rsi_15 < l_rsi_ma_15 and p_rsi_15 > p_rsi_ma_15): #убраны ограничения по величине рси
        order = client.new_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=qty)
        print(f'SHORT {order}')
        # bot.send_message(admin_id, 'Вход в Short')
        trades = client.get_account_trades(symbol=SYMBOL, limit=1)
        last_trade = trades[0]
        buyprice = float(last_trade['price'])

        text_short = f'Вход в Short, {SYMBOL}\nЦена покупки: {buyprice}\nTake profit ({TAKE_PROFIT_SHORT * 100 - 100}%): {round(buyprice * TAKE_PROFIT_SHORT, 5)}\nStop loss (+{round(STOP_LOSS_SHORT * 100 - 100, 1)}%): {round(buyprice * STOP_LOSS_SHORT, 5)}'
        print(text_short)
        bot.send_message(admin_id, text_short)

        open_position = True

        while open_position:
            try:
                trade_params = get_data_conditions()
                l_rsi_15 = trade_params['l_rsi_15']
                l_rsi_ma_15 = trade_params['l_rsi_ma_15']
                p_rsi_15 = trade_params['p_rsi_15']
                p_rsi_ma_15 = trade_params['p_rsi_ma_15']

                l_rsi_ma_15_B = trade_params['l_rsi_ma_15_B']
                p_rsi_ma_15_B = trade_params['p_rsi_ma_15_B']
                # l_rsi_5 = trade_params['l_rsi_5']
                # l_rsi_ma_5_B = trade_params['l_rsi_ma_5_B']
                # p_rsi_5 = trade_params['p_rsi_5']
                # p_rsi_ma_5_B = trade_params['p_rsi_ma_5_B']

                # отправляем инфо по цене
                current_price = get_current_price()

            except BinanceAPIException as e:
                print(e)
                bot.send_message(admin_id, e)
                time.sleep(20)
                continue

            except:
                bot.send_message(admin_id, 'Неизвестная ошибка')
                time.sleep(20)
                continue

            if not exit and (l_rsi_15 > l_rsi_ma_15_B and p_rsi_15 < p_rsi_ma_15_B):
                order = client.new_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=qty)
                exit_S_text = f'Exit Short, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_S_text)
                bot.send_message(admin_id, exit_S_text)
                exit = True
            if not tp and (current_price <= buyprice * TAKE_PROFIT_SHORT):
                order = client.new_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=qty)
                exit_tpS_text = f'Exit Short Take profit, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_tpS_text)
                bot.send_message(admin_id, exit_tpS_text)
                tp = True
            if not sl and (current_price >= buyprice * STOP_LOSS_SHORT):
                order = client.new_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=qty)
                exit_slS_text = f'Exit Short Stop loss, итог: {round(current_price * 100 / buyprice - 100, 2)}%'
                print(exit_slS_text)
                bot.send_message(admin_id, exit_slS_text)
                sl = True
            if exit or tp or sl:
                open_position = False
                bot.send_message(admin_id, 'Сделка закрыта')
                time.sleep(60)

            time.sleep(5)

    print('Нет условий для входа')
    time.sleep(60)


while True:
    strategy()
