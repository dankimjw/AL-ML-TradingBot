import TradePlatform as tp
import Utilities as ut
import json
import numpy as np
import pandas as pd
import time
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus,QueryOrderStatus
import uuid
import requests
import datetime as dt
import importlib
import DataCollector
import Model as advisor
import sys

# -------- For testing on local machine ------------
# try:
#     with open('app-keys.json') as data_file:
#         data = json.load(data_file)
#     KEY_ID = data['API_KEY_ID']
#     SECRET_KEY = data['SECRET_KEY']
#     BASE_URL = "https://paper-api.alpaca.markets"
# except FileNotFoundError:
#     print("BotTrader.py: app-keys.json not found")
#---- For streamlit cloud ----
# KEY_ID = st.secrets["API_KEY_ID"]
# SECRET_KEY = st.secrets["SECRET_KEY"]

utils = ut.Utilities()

class BotTrader:
    # def __init__(self, model):
    def __init__(self, KEY_ID, SECRET_KEY):
        # self.model = model
        self.trade_account = tp.TradeAccount(KEY_ID, SECRET_KEY)
        self.utils = ut.Utilities()
        # Assumption of % of cash to trade
        self.pct_of_cash = 0.1
        # Max amount of cash available per 1 trade depending on pct_of_cash
        # value of -1 means there are is no more cash available to make additional buy orders
        self.max_trade_usd = 0
        self.buy_qty = 1
        self.buy_usd = 0
        self.sell_qty = 1
        self.current_sell_price = 0
        self.current_buy_price = 0
        self.prev_buy_price = 0
        self.avg_entry_price = 0
        # Flag to communicate whether buy or sell order was executed
        self.trade_executed = 1
        # Keep track of the number of orders created
        # Total cash paper account begins with and does not change
        self.original_start_cash = 100000
        # Total cash paper account begins with without any positions
        # Gets updated if all positions are liquidated for cash
        self.start_cash = 100000
        # Max % of cash useable for consecutive buy orders
        self.cash_threshold = 0.25
        # Current % of total cash used to trade
        self.cash_used = 0
        self.pct_cash_used = 0
        # Cash threshold flag
        self.cash_threshold_reached = False
        # If sell_qty is greater than the quantity of bitcoin remaining in portfolio,
        # execute_sell will look for the liquidate_at_sell flag to liquidate all remaining BTC quantities.
        self.liquidate_at_sell = True
        # self.time_interval_units = "Minutes"
        # self.time_interval = 1
        self.log_df:pd.DataFrame
        # Flag for running or stopping the bot
        self.run_bot = False
        # Maximum price decline before liquidating positions
        self.max_price_decline = -0.1
        # Trade time interval units as a string
        # Options: seconds, minutes, hours
        self.trade_time_units = 'seconds'
        # Trade time interval as a number
        self.trade_time_interval = 5
        # Train time interval
        self.train_time_interval = 10
        # Interval count tracker
        self.interval_count = 0
        # Interrupt running bot
        self.interrupt_bot = False

    def update_trade_time_units(self, trade_time_units):
        self.trade_time_units = trade_time_units

    def update_trade_time_interval(self, trade_time_interval):
        self.trade_time_interval = trade_time_interval

    def update_train_time_interval(self, train_time_interval):
        self.train_time_interval = train_time_interval

    def update_cash_threshold(self, cash_threshold):
        # Maximum percentage of cash that can be deployed for total positions
        self.cash_threshold = cash_threshold

    def update_decline_threshold(self, decline_threshold):
        # Maximum percentage of value decline that can be tolerated before liquidating all positions.
        self.max_price_decline = decline_threshold

    def check_price_decline(self):
        pct_decline = (self.current_sell_price  - self.prev_buy_price)/ self.prev_buy_price
        print("--------------------------------------------------------------------------")
        if (pct_decline < 0 and pct_decline <= self.max_price_decline) and self.trade_account.number_of_positions == 1:
            print(" ✂✂ Position declined [", pct_decline, "] which is more than the max price decline threshold [",
                  self.max_price_decline, "] ✂✂")
            print(" ✂ Liquidating all positions. ✂")
            self.liquidate_postions()
            print("--------------------------------------------------------------------------")
            return 0
        else:
            print(" ✂ No position liquidation necessary: % change is [", pct_decline*100, "] ✂")
            print("--------------------------------------------------------------------------")
            return 1

    def update_advisor(self):
        print("【 ☆ Rebuilding/Training Model with updated market data ☆ 】")
        # Reload the module to execute rebuilding/training the model with updated data
        importlib.reload(DataCollector)
        importlib.reload(advisor)
        print("【 Predicted Price: ", advisor.pred_price, "】")
        tomorrows_pred_price = advisor.pred_price[0][0]
        # Reset the start time.
        train_start_time = dt.datetime.now()

    def calc_cash_traded(self):
        # Updates account information
        self.trade_account.get_account_info()
        # Calculates the amount of cash used
        self.trade_account.get_positions()
        positions = self.trade_account.number_of_positions
        print("Number of POSITIONS: ", positions)
        self.cash_threshold_reached = False
        if positions == 0:
            # Starting cash needs to be updated since there are no positions held in the portfolio
            # starting cash needs to be reset to the current total cash after selling all positions
            self.start_cash = self.trade_account.cash
            self.cash_threshold_reached = False
            self.pct_cash_used = 0
            print("~~ Percent_cash_used reset ~~")
        else:
            # Calculated the total cash used
            cash_val = self.start_cash - self.trade_account.cash
            self.cash_used = self.utils.truncate_val(cash_val, decimals=2)
            # Calculate the % of total cash used
            cash_pct_val = self.cash_used / self.start_cash
            self.pct_cash_used = self.utils.truncate_val(cash_pct_val, decimals=6)
            # % of cash used plus a round up of 0.1%
            # Ex) 24.93% of cash used would result in
            pct_cash_used = self.pct_cash_used + 0.001
            print("Percent_cash_used: ", self.pct_cash_used)
            print("% Cash Threshold: ", self.cash_threshold)
            print("% cash used (rounded up 0.01): ", pct_cash_used)
            if pct_cash_used >= self.cash_threshold:
                self.cash_threshold_reached = True
                print("Cash threshold % reached: ", self.pct_cash_used)
                print("cash threshold reached? ", self.cash_threshold_reached)
            else:
                self.cash_threshold_reached = False
                print("cash threshold reached? ", self.cash_threshold_reached)
            return 0

    def reset_log(self):
        self.log_df = pd.DataFrame(columns=['order_date','trade_side',
                                            'predict_date', 'predicted_price', 'trade_price', 'trade_qty'])
    def update_orders(self):
        # Retrieves the most recent sell and buy orders and parses the df's and combines them into
        # a single dataframe.
        sell_orders = self.trade_account.get_orders("ALL", "SELL")
        buy_orders = self.trade_account.get_orders("ALL", "BUY")
        # Create the orders dataframes
        sell_order_df = self.utils.parse_orders(sell_orders)
        buy_order_df = self.utils.parse_orders(buy_orders)
        # # Combine the sell and buy order dataframes
        orders_df = pd.concat([sell_order_df, buy_order_df])
        orders_df.sort_values(by=['created_at'], ascending=False, inplace=True)
        orders_df.reset_index(inplace=True)
        orders_df.drop(columns='index',inplace=True)
        # print(orders_df)
        return orders_df

    def parse_order_side(self, temp_df_row):
        # Creates a new column for order side with respective Buy or Sell string mapping.
        if temp_df_row == 'OrderSide.BUY':
            order_side = "Buy"
            # print("Order_side is buy: ", order_side)
            return order_side
        else:
            order_side = "Sell"
            # print("Order_side is sell: ", order_side)
            return order_side

    def update_orders_log(self, predicted_price=0):
        # Saves the most recent trade into a log dataframe
        orders_df = self.update_orders()
        # Create Amount column to show the dollar amount spent on the specific order
        orders_df['Amount'] = orders_df['qty'] * orders_df['filled_avg_price']
        orders_df['trade_side'] = orders_df['side'].map(self.parse_order_side)
        orders_df.iloc[[0]]['Predicted_Price'] = predicted_price
        self.log_df = orders_df.copy()
        return orders_df

    def update_pct_of_cash(self, pct):
        if pct > 1:
            print('Percent value must be less than 1 and in decimal form')
        else:
            # pct must be less than 1 (100%)
            self.pct_of_cash = float(pct)
            print("-- pct_of_cash updated: -- ", self.pct_of_cash)

    def update_prices(self):
        """Retrieves both sell and buy prices
          Args:
              None

          Returns:
              List of order objects with attributes
                filled_at, filled_avg_price, qty
          """
        quote = self.trade_account.get_crypto_quote()
        self.current_buy_price = float(quote['BTC/USD'].bid_price)
        self.current_sell_price = float(quote['BTC/USD'].ask_price)
        print("-- BTC prices updated --")

    def calculate_trade_qty(self):
        """Calculates how much to buy or sell depending on how much cash is remaining in the account
          Args:
              None

          Returns:
              List of order objects with attributes
                filled_at, filled_avg_price, qty
          """
        # 1 API call
        # Get crypto quotes
        self.update_prices()
        # if remaining % of cash utilizable < pct_of_cash, then use the smaller of the two
        remain_cash_utilizable = self.cash_threshold - self.pct_cash_used
        new_pct_cash = min(remain_cash_utilizable, self.pct_of_cash)
        print("✎ % of Cash used for current trade: ", new_pct_cash, "✎")
        available_cash_per_trade = self.trade_account.cash * new_pct_cash
        # available_cash_per_trade = self.trade_account.cash * self.pct_of_cash
        # Alpaca requires a trade to be at least 1 USD
        print("≓≓ Available cash per trade: ≓≓", available_cash_per_trade, "≓≓")
        if available_cash_per_trade >= 1:
            self.max_trade_usd = available_cash_per_trade
            # Quantity of BTC depending on cash available per 1 trade and current buy price of 1 BTC
            buy_val = self.max_trade_usd / self.current_buy_price
            self.buy_qty = self.utils.truncate_val(buy_val, decimals=9)
            self.sell_qty = self.buy_qty
            print("✎✎ Recalculated trade qty: [", self.buy_qty, "] ✎✎")
        else:
            # Value of -1 means there are is no more cash available to make additional buy orders
            self.max_buy_usd = -1
            print("☂☂☂ Not enough cash ☂☂☂☂")

    def update_account_info(self):
        # 4 API calls
        # Get recent account information
        self.trade_account.get_account_info()
        # Get recent buy and sell orders
        self.trade_account.update_recent_orders()
        # Get all open positions
        positions = self.trade_account.get_positions()
        num_positions = self.trade_account.number_of_positions
        if num_positions != 0:
            self.avg_entry_price = float(positions[0].avg_entry_price)
        # Update previous buy price
        self.prev_buy_price = float(self.trade_account.prev_buy_order.filled_avg_price)
        print("-- Updated account info --")

    def print_positions(self):
        # Update positions
        position_vals = self.trade_account.get_positions()
        if position_vals == 0:
            # print("--- No Current Positions ---")
            return 0
        else:
            # Prints out current portfolio position values
            print("Current BTC Price: ", self.trade_account.positions["current_btc_price"])
            print("Current BTC quantity in portfolio: ", self.trade_account.positions["qty"])
            print("Current BTC market value in portfolio: ", self.trade_account.positions["market_value"])
            print("Avg. entry price of portfolio: ", self.trade_account.positions["avg_entry_price"])

    def execute_manual_trade(self, trade_type):
        """Executes a buy or sell for manual testing.
          Total 6 API calls
          Args:
              None
          Returns:
              List of order objects with attributes
                filled_at, filled_avg_price, qty
          """
        # Update recent orders and account information (5 API calls)
        self.update_account_info()
        self.calculate_trade_qty()
        print("NUM POSITIONS!!!!: ", self.trade_account.number_of_positions )
        # Check if we have a non-zero BTC quantity to sell.
        if trade_type == "Sell":
            if self.trade_account.number_of_positions != 0:
                # Simplified Sell order
                self.liquidate_postions()
                self.trade_account.prev_order_is_sell = True
                return self.trade_account.portfolio_btc_qty
            else:
                # No BTC coin quantity to sell
                return -1

        if trade_type == "Buy" and self.max_trade_usd != -1:
            # Account has enough cash to make a buy order
            if (self.trade_account.cash - self.current_buy_price >= 0):
                self.trade_account.buy_crypto(self.buy_qty)
                self.trade_account.prev_order_is_sell = False
                return self.buy_qty
        # Not enough cash to buy additional BTC
        else:
            return -1

    def execute_buy(self, predicted_price):
        """Executes a buy order depending on previous buy price, current cash balance.
          Total 6 API calls
          Args:
              None
          Returns:
            0 if buy order is executed
            1 if buy order is not executed
          """
        print("--------------------------------------------------------------------------")
        # Update recent orders and account information (5 API calls)
        # self.update_account_info()
        # self.calculate_trade_qty()
        # self.calc_cash_traded()
        # max_buy_usd will be -1 if there isn't enough cash to make another BTC buy order
        if self.max_trade_usd == -1:
            print("!!Max trade usd = -1 Not enough cash remaining to make additional trades.")
            print("--------------------------------------------------------------------------")
            return 1
        else:
            self.prev_buy_price = float(self.trade_account.prev_buy_order.filled_avg_price)

        if self.cash_threshold_reached == True:
            print("!!Cash trade threshold reached maximum % at ", self.pct_cash_used)
            print("--------------------------------------------------------------------------")
            return 1

        # Initial check if the trading account has enough cash to buy additional coins
        if (self.trade_account.cash - self.current_buy_price >= 0) or self.trade_account.prev_order_is_sell or self.cash_threshold == False:
                print("-- [Buying Decision] current buy price: ", self.current_buy_price)
                # Prices must be upward trending
                if self.current_buy_price < predicted_price and self.prev_buy_price < predicted_price:
                    print("-- ↗↗ Price trend is upward ↗↗--")
                    # If the prices are predicted to rise, we buy if the buy price is lower than our previous buy price
                    if self.prev_buy_price == 0 or (self.current_buy_price < self.prev_buy_price) or \
                            (self.current_buy_price < self.avg_entry_price) or\
                            ((self.current_buy_price < self.current_sell_price) and (self.prev_buy_price < self.current_sell_price)):
                        print("--- [BUYING] $", self.max_trade_usd, " equaling ",  self.buy_qty, " of bitcoin (BTC). ----")
                        # self.trade_account.btc_amount += self.trade_amount / self.account.btc_price
                        # self.account.usd_balance -= self.trade_amount
                        # 1 API Calls
                        self.trade_account.buy_crypto(self.buy_qty)
                        self.trade_account.prev_order_is_sell = False
                        print("--------------------------------------------------------------------------")
                        return 0
                    else:
                        print("--↘↘ ** Not worth buying more BTC at the moment ** ↘↘--")
                        print("--------------------------------------------------------------------------")
                        return 1
        else:
            print("-- !! Not enough cash (USD) remaining in your account with at least", self.trade_account.cash, " to buy ",
                      self.buy_qty," of BTC. !! --")
            print("--------------------------------------------------------------------------")
            return 1

    def execute_sell(self):
        """Executes a sell order depending on previous buy price, current BTC quantity balance,

          Total 6 API calls
          Args:
              None

          Returns:
            0 if sell order is executed
            1 if sell order is not executed
          """
        print("--------------------------------------------------------------------------")
        # Update recent orders and account information (5 API calls)
        # self.update_account_info()
        # self.calculate_trade_qty()
        self.prev_buy_price = float(self.trade_account.prev_buy_order.filled_avg_price)
        # 1 API call
        if self.trade_account.portfolio_btc_qty - self.sell_qty >= 0:
            # print("1st sell check passed: current portfolio quantity > sell quantity ")
            if self.current_sell_price > self.prev_buy_price:  # Is it profitable?
                print("---- [Selling] $", self.max_trade_usd, " equaling ",  self.sell_qty, " of bitcoin (BTC). ----")
                self.trade_account.sell_crypto(self.sell_qty)
                self.trade_account.prev_order_is_sell = True
                print("--------------------------------------------------------------------------")
                return 0
            else:
                print("-- ** Not worth selling more BTC at the moment ** --")
                print("--------------------------------------------------------------------------")
                return 1
        else:
            if self.liquidate_at_sell == True:
                if (self.trade_account.portfolio_btc_qty > 0) and (self.current_sell_price > self.prev_buy_price):
                    print("---- Not enough BTC quantity to sell ", self.sell_qty," ----")
                    print("Liquidating remaining BTC quantity in portfolio: ", self.trade_account.portfolio_btc_qty)
                    self.liquidate_postions()
                    self.trade_account.prev_order_is_sell = True
                    print("--------------------------------------------------------------------------")
                    return 0
                else:
                    print("-- ** [Liqudate_at_sell = True] Not enough BTC quantity in portfolio: ",
                          self.trade_account.portfolio_btc_qty," BTC ** --")
                    print("--------------------------------------------------------------------------")
                    return 1
            else:
                print("-- !! Not enough BTC quantity remaining in your account: ", self.trade_account.portfolio_btc_qty,
                      " to sell. !! --")
                print("--------------------------------------------------------------------------")

                return 1

    def liquidate_postions(self):
        """Executes a sell order on remaining BTC quantity depending on previous buy price, current cash balance,
        and sell_qty.
          Total 6 API calls
          Args:
              None
          """
        # 4 API calls
        print("--------------------------------------------------------------------------")
        self.update_account_info()
        # self.calculate_trade_qty()
        total_btc_qty = self.trade_account.portfolio_btc_qty
        self.trade_account.sell_crypto(total_btc_qty)
        print("- Remaining BTC quantity ", total_btc_qty ," in portfolio sold. -")
        print("--------------------------------------------------------------------------")

    # Code starts with current time
    def set_interval(self, time_units: str, trade_time_interval: int):
        """ Returns time_interval as a timedelta object and the calculated sleep interval in total seconds
            Args:
                time_units (str): "minutes", "hours", "seconds"
                trade_time_interval (int): number of minutes, hours, or seconds to wait to make the next trade execution
            Returns:
                time_interval: datetime timedelta object with the respect time interval set
                sleep_interval: total seconds per trade interval to use in a sleep timer
        """
        if time_units == "minutes":
            time_interval = dt.timedelta(minutes=trade_time_interval)
            # 60 seconds per 1 minute
            sleep_interval = 60 * trade_time_interval
        elif time_units == "hours":
            time_interval = dt.timedelta(hours=trade_time_interval)
            # 60 minutes per hour, 60 seconds per minute
            sleep_interval = 60 * 60 * trade_time_interval
        # Used for testing purposes but not used in the user side app
        elif time_units == "seconds":
            time_interval = dt.timedelta(seconds=trade_time_interval)
            sleep_interval = trade_time_interval
        else:
            print("Not a valid time interval: seconds, minutes, hours")
            return 1

        return time_interval, sleep_interval

    def set_total_time(self, time_units: str, total_trade_time: int):
        """ Returns total  as a timedelta object and the calculated sleep interval in total seconds
            Args:
                time_units (str): "minutes", "hours", "seconds"
                trade_time_interval (int): number of minutes, hours, or seconds to wait to make the next trade execution
            Returns:
                time_interval: datetime timedelta object with the respect time interval set
        """
        if time_units == "minutes":
            total_time = dt.timedelta(minutes=total_trade_time)
        elif time_units == "hours":
            total_time = dt.timedelta(hours=total_trade_time)
        # Used for testing purposes but not used in the user side app
        elif time_units == "seconds":
            total_time = dt.timedelta(seconds=total_trade_time)
        else:
            print("Not a valid time interval: seconds, minutes, hours")
        return total_time

    def calculate_time_lapsed(self, time_to_compare):
        # Calculates the total time delta between the current time now and the start time
        # returns the total time delta
        time_lapsed = dt.datetime.now() - time_to_compare
        return time_lapsed

    def set_run_bot(self, run_bot: bool):
        # Sets the flag to run/stop the bot
        self.run_bot = run_bot

    def set_run_flag(self, start_bot:False):
        # Sets the run_bot flag to either True or False
        # False will lead to the run_bot_trader aborting
        self.run_bot = start_bot

    def set_interrupt_flag(self, interrupt:False):
        self.interrupt_bot = interrupt

    def check_interrupt_flag(self):
        # Interrupt the bot
        if self.interrupt_bot != False:
            return 0
        else:
            # Don't interrupt the bot
            return 1

    def run_bot_trader(self, test_flag=False, trade_time_units='seconds', trade_time_interval=None,
                       train_time_interval=None, total_run_time=None):
        # Choose the time units and the time interval
        # These are obtained from STREAMLIT front end user choices
        # if testing, then use very short intervals
        if test_flag == True:
            print("♔ ★★ Running bot trader in TEST MODE ★★ ♔")
            trade_time_units = "seconds"
            trade_time_interval = 5
            # Obtain the proper datetime delta object and calculated sleep seconds
            time_interval, sleep_interval = self.set_interval(trade_time_units, trade_time_interval)

            # Choose the time units and the time interval
            # These are obtained from STREAMLIT front end user choices
            # How often do you want to update the model?
            train_time_units = "seconds"
            train_time_interval = 10
            # Obtain the proper datetime delta object and calculated sleep seconds
            train_interval, train_sleep_interval = self.set_interval(train_time_units, train_time_interval)

            # Optional total run time of the trading bot
            # These are obtained from streamlit front end user choices
            total_run_time = 20
            total_run_time_units = "seconds"
            total_time = self.set_total_time(total_run_time_units, total_run_time)
            # total_time = dt.timedelta(seconds=total_run_time)
            print("Total TIME: ", total_time)

        else:
            # If the trading interval is in seconds, then training and total time intervals should be the same
            # time units.
            print("〔 ✦✦ Running bot trader with custom time intervals! ✦✦〕")
            train_time_units = trade_time_units
            total_run_time_units = trade_time_units

            trade_time_interval = trade_time_interval if trade_time_interval != None else 5
            # Obtain the proper datetime delta object and calculated sleep seconds
            time_interval, sleep_interval = self.set_interval(trade_time_units, trade_time_interval)

            # Choose the time units and the time interval
            # These are obtained from STREAMLIT front end user choices
            # How often do you want to update the model?
            train_time_interval = train_time_interval if train_time_interval != None else 10
            # Obtain the proper datetime delta object and calculated sleep seconds
            train_interval, train_sleep_interval = self.set_interval(train_time_units, train_time_interval)

            # Optional total run time of the trading bot
            # These are obtained from streamlit front end user choices
            total_run_time = total_run_time if total_run_time != None else 86400
            total_time = self.set_total_time(total_run_time_units, total_run_time)
            # total_time = dt.timedelta(seconds=total_run_time)
            print("Total TIME: ", total_time)

        # # BUTTON from front end will set this
        # self.set_run_bot(True)

        # Code starts with current time
        interval_start_time = dt.datetime.now()
        bot_start_time = dt.datetime.now()
        # Keeps track of how much time passed between the last model training time
        train_start_time = dt.datetime.now()

        # Keeps track of how much time passed between the last model training time
        train_time_lapsed = self.calculate_time_lapsed(train_start_time)
        # Keeps track of how much time passed within the current time interval
        interval_time_lapsed = self.calculate_time_lapsed(interval_start_time)
        # Keeps track of total time passed overall
        total_time_lapsed = self.calculate_time_lapsed(dt.datetime.now())
        print("time_lapsed: ", interval_time_lapsed)

        # Retrieve predicted price
        tomorrows_pred_price = advisor.tomorrows_prediction(advisor.model)[0][0]
        interval_count = 1

        while self.run_bot == True:
            # Keeps track of how much time passed within the current time interval
            interval_time_lapsed = self.calculate_time_lapsed(interval_start_time)
            train_time_lapsed = self.calculate_time_lapsed(train_start_time)
            print(interval_time_lapsed, " vs ", time_interval)
            print("✔ [Current interval] -- [", interval_count, "] ✔")
            # --------------------- Trade Decision ---------------------
            # Is the interval time delta exceeded or
            # time_interval never resets
            if interval_time_lapsed >= time_interval:
                # print(interval_time_lapsed, " vs ", time_interval)
                print("✓ ", time_interval, " seconds passed!")
                # print(interval_time_lapsed, " vs ", time_interval)
                # reset start_time for next interval
                print("➤ Buy/Sell advisor.pred_price: ", tomorrows_pred_price)
                # ------ Execute Buy/ Sell ------
                # Update required account information
                print("➤ Updating account information and preparing for trade decision/execution.")
                self.update_account_info()
                self.calc_cash_traded()
                self.calculate_trade_qty()
                print("➤ Market Buy Price: ", self.current_buy_price, " vs. predicted ", tomorrows_pred_price)
                print("➤ Prev buy price: ", self.prev_buy_price)
                print("➤ Market Sell Price: ", self.current_sell_price)
                # Buy lower than predicted price
                if self.current_buy_price <= tomorrows_pred_price:
                    print("➤ Executing buy function")
                    self.trade_executed = self.execute_buy(tomorrows_pred_price)
                    print("➤ Buy executed? ", "Yes" if self.trade_executed == 0 else "No")
                    # if bot.trade_executed == 0:
                    #     bot.save_trade_log(tomorrows_pred_price)
                    #     # Reset trade_executed flag
                    #     bot.trade_executed = -1
                    if self.trade_executed != 0:
                        # If no buy order was executed because of a lack of cash or the cash utilization threshold is met
                        # check if it is worth it to take a profit by selling off BTC.
                        print("➤ No buy trade executed. Checking if current sell_price > previous buy price")
                        if self.current_sell_price > self.prev_buy_price or self.current_sell_price > self.avg_entry_price:
                            print("➤ Current sell price is greater than previous buy price. Attempting to sell.")
                            self.trade_executed = self.execute_sell()
                            print("➤ Sell executed? ", "Yes" if self.trade_executed == 0 else "No")
                            # if bot.trade_executed == 0:
                            #     bot.save_trade_log(tomorrows_pred_price)
                            #     # Reset trade_executed flag
                            #     bot.trade_executed = -1
                        else:
                            print("➤ No sell trade executed. Current sell price [", self.current_sell_price, "]",
                                  " is less than previous buy price[",
                                  self.prev_buy_price, "].")
                else:
                    # Sell higher than predicted price
                    print("⇨ Sell price is higher than predicted price ")
                    print("⇨ Sell Price: ", self.current_sell_price, " vs. predicted ", tomorrows_pred_price)
                    print("⇨ Prev buy price: ", self.prev_buy_price)
                    if self.current_sell_price > tomorrows_pred_price:
                        print("⇨ Attemping to execute sell function")
                        if self.trade_account.number_of_positions != 0:
                            self.trade_executed = self.execute_sell()
                        else:
                            self.trade_executed = -1
                    print("➤ Sell executed? ", "Yes" if self.trade_executed == 0 else "No")
                    interval_start_time = dt.datetime.now()

                # goes directly here if buy is executed
                # Allow the Alapaca data to be updated
                print("✎✎ Checking if % price decline has exceed the price decline threshold ✎✎")
                self.trade_executed = self.check_price_decline()
                print("➤ Asset Liquidation executed? ", "Yes" if self.trade_executed == 0 else "No")

                time.sleep(1)
                if self.trade_executed == 0:
                    self.update_orders_log(tomorrows_pred_price)
                    # Reset trade_executed flag
                    self.trade_executed = -1
            else:
                # print(interval_time_lapsed, " vs ", time_interval)
                print("【 Waiting for trade interval: ", sleep_interval, " seconds. 】")
            # bot.calc_cash_traded()
            # --------------------- Model Update ---------------------
            # Check if it is time to train the model again
            if train_time_lapsed >= train_interval:
                # Reload the module to execute rebuilding/training the model with updated data
                self.update_advisor()
                # print("【 ☆ Rebuilding/Training Model with updated market data ☆ 】")
                # Reload the module to execute rebuilding/training the model with updated data
                # importlib.reload(advisor)
                # print("【 Predicted Price: ", advisor.pred_price, "】")
                tomorrows_pred_price = advisor.pred_price[0][0]
                # Reset the start time.
                train_start_time = dt.datetime.now()

            # Keep track of the total intervals
            temp_delta = self.calculate_time_lapsed(bot_start_time)
            total_time_lapsed = temp_delta
            print("♦ New total_time_lapsed: ", total_time_lapsed, " ♦")
            # total_time never resets
            if total_time_lapsed >= total_time:
                print("♦ Total Time: ", total_time, " ♦")
                print("♦ Total time lapsed: ", total_time_lapsed)
                print("♪♪♪ Total Run Time Complete ♪♪♪♪")
                self.run_bot = False
            # Pause for the sleep interval
            time.sleep(sleep_interval)
            # print("[", interval_count, "]", "Completed interval: ", interval_count)
            self.interval_count += 1

            # interrupt_flag = self.check_interrupt_flag()
            # if interrupt_flag == 0:
            #     self.set_run_flag(False)






