from alpaca.broker.client import BrokerClient
from alpaca.broker.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetPortfolioHistoryRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus,QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
from alpaca.trading.stream import TradingStream
import uuid
import requests
import json
import Utilities as util
import datetime as dt
import streamlit as st
import pandas as pd

# -------- For testing on local machine or GCLOUD ------------
# with open('app-keys.json') as data_file:
#     data = json.load(data_file)
# KEY_ID = data['API_KEY_ID']
# SECRET_KEY = data['SECRET_KEY']
#
# BASE_URL = "https://paper-api.alpaca.markets"

#---- For streamlit cloud ----
# KEY_ID = st.secrets["API_KEY_ID"]
# SECRET_KEY = st.secrets["SECRET_KEY"]


class TradeAccount:
    """TradeAccount class used to help with consolidating alpaca api objects
    and simplifying the get, set methods for the project use.

    Attributes:
        alpaca_objs: a dictionary of alpaca objects returned from trading client object
                    (e.g. Account, Orders, Positions, Assets, Account Activities,
                    Portfolio History)
        utils: holds the Utilities helper class object
        trading_client: holds the alpaca trading client object
        crypto_client: holds the alpaca crypto client object for historical crypto currency data
        trading_stream: holds the alpaca real time trading data stream
    """
    def __init__(self, KEY_ID, SECRET_KEY):
        """Initializes TradeAccount object with alpaca objects

        Args:
            KEY_ID: key for API
            SECRET_KEY: secret key for API
        """
        # List of alpaca objects
        self.KEY_ID = KEY_ID
        self.SECRET_KEY = SECRET_KEY
        self.trading_client = TradingClient(KEY_ID, SECRET_KEY, paper=True)
        self.crypto_client = CryptoHistoricalDataClient()
        self.utils = util.Utilities()
        self.trading_stream = TradingStream(KEY_ID, SECRET_KEY, paper=True)
        self.account = {}
        self.cash = 0
        self.account_number = 0
        self.positions = {}
        self.current_quote = {}
        # How much BTC is in our portfolio, account
        self.portfolio_btc_qty = 0
        self.prev_buy_order = {}
        self.prev_sell_order = {}
        self.recent_order = {}
        self.prev_order_is_sell = False
        self.portfolio_history:pd.DataFrame

    #----[Platform Communiction Functions]-------
    def get_account_info(self):
        # Communicates with Alpaca API to get Account object
        # and saves it in the alpaca_objs attribute dictionary in the TradeAccount class
        # This object is static which means that to obtain updated account info, this
        # method needs to be called.
        self.account = self.trading_client.get_account()
        self.cash  = float(self.account.cash)
        print("-- Account Info Retrieved--")

    def print_account_info(self):
        print("Cash: ", self.cash)
        print("")

    def get_account_item(self, line_item: str):
        if not isinstance(line_item,str):
            return None
        # Helper function to retrieve specific account line item
        if line_item == "cash":
            return self.account.cash
        elif line_item == "account_number":
            self.account_nubmer = self.account.account_number
        elif line_item == "buying_power":
            return self.account.buying_power
        elif line_item == "non_margin_buy_power":
            return self.account.non_marginable_buying_power
        elif line_item == "accrued_fees":
            return self.account.accrued_fees
        elif line_item == "pending_trans_out":
            return self.account.pending_transfer_in
        elif line_item == "pending_trans_in":
            return self.account.pending_transfer_out
        elif line_item == "daytrade_count":
            return self.account.daytrade_count
        elif line_item == "day_buypower":
            return self.account.daytrading_buying_power
        elif line_item == "equity":
            return self.account.equity
        elif line_item == "initial_margin":
            return self.account.initial_margin
        elif line_item == "last_eq":
            return self.account.last_equity
        elif line_item == "last_maintenance_margin":
            return self.account.last_maintenance_margin
        elif line_item == "long_val":
            return self.account.long_market_value
        elif line_item == "maintenance_margin":
            return self.account.maintenance_margin
        elif line_item == "multiplier":
            return self.account.multiplier
        elif line_item == "portfolio_val":
            return self.account.portfolio_value
        elif line_item == "regt_buy_pow":
            return self.account.regt_buying_power
        elif line_item == "short_val":
            return self.account.short_market_value
        elif line_item == "all":
            return self.account
        else:
            print("account item not found")
            return 1

    def get_crypto_data(self, timeframe, start_date: str, end_date, symbols= "BTC", as_df=True):
        """Wrapper for setting up getting historical crypto data

        Args:
            symbols: list of symbols as strings e.g. "BTCUSD"
            timeframe: Alpaca.data.timeframe object e.g TimeFrame.Day
                        Minute, Hour, Day, Week, Month
            start_date: start date of the historical data
                        e.g. 2022-07-01
            end_Date: end date of timeframe for historical data
                        e.g. 2022-07-01
        Returns:
            A pandas dataframe of historical data or alpaca set of bar objects
            0: if parameters are invalid
        """
        if symbols == "BTC":
            symbols = ["BTC/USD"]
        # Check if the required TimeFrame object is there
        if isinstance(timeframe, TimeFrame) is True:
            request_params = None
            symbols = symbols
            timeframe = timeframe
            # TimeFrame.Day
            # ["BTC/USD", "ETH/USD"],
        else:
            # Failure timeframe is not a TimeFrame object
            return 1
        if start_date == None or isinstance(start_date, str) == False:
            print("Error: Check start date type")
            return 1
        # Check if start_date is correct and convert to datetime obj
        # return False
        start_date = self.utils.parse_date(start_date)
        if start_date != False:
            if end_date != None:
                # Check if end_date is correct and convert to datetime obj
                end_date = self.utils.parse_date(end_date)
                if end_date != False:
                    request_params = CryptoBarsRequest(
                        symbol_or_symbols=symbols,
                        timeframe=timeframe,
                        start=start_date,
                        end=end_date
                    )
                if as_df == True:
                    return self.crypto_client.get_crypto_bars(request_params).df
                else:
                    return self.crypto_client.get_crypto_bars(request_params)
            else:
                # only start_date provided
                request_params = CryptoBarsRequest(
                    symbol_or_symbols=symbols,
                    timeframe=timeframe,
                    start=start_date
                )
                if as_df == True:
                    return self.crypto_client.get_crypto_bars(request_params).df
                else:
                    return self.crypto_client.get_crypto_bars(request_params)
        else:
            # Fail: start_date is not datetime or string
            return 1

    def get_current_data(self, timeframe, symbols="BTC"):
        """Wrapper for setting up getting current historical crypto data
        assumption is that the start_date = current date today
          Args:
              symbols: list of symbols as strings e.g. "BTCUSD"
              timeframe: Alpaca.data.timeframe object e.g TimeFrame.Day
                          Minute, Hour, Day, Week, Month
          Returns:
              A pandas dataframe of historical data or alpaca set of bar objects
              0: if parameters are invalid
          """
        if symbols == "BTC":
            symbols = ["BTC/USD"]
        # Check if the required TimeFrame object is there
        if isinstance(timeframe, TimeFrame) is True:
            request_params = None
            symbols = symbols
            timeframe = timeframe
            # TimeFrame.Day
            # ["BTC/USD", "ETH/USD"],
        else:
            # Failure timeframe is not a TimeFrame object
            return 1

        start_date = dt.datetime.today()
        print("start_date: ", start_date)
        request_params = CryptoBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe,
            start=start_date,
        )
        return self.crypto_client.get_crypto_bars(request_params).df

    def get_positions(self):
        # Gets a list of positions objects from alpaca trading client and updates position_vals dictionary attribute
        self.positions_list = self.trading_client.get_all_positions()
        self.number_of_positions =  len(self.positions_list)
        print("Current number of positions (0 holding no BTC or 1 for holding BTC): ", self.number_of_positions)
        if self.number_of_positions == 0:
            print("--- No Current Positions ---")
            return 0
        else:
            self.positions["current_btc_price"] = self.positions_list[0].current_price
            self.positions["lastday_price"] = self.positions_list[0].lastday_price
            self.positions["qty"] = self.positions_list[0].qty
            self.positions["market_value"] = self.positions_list[0].market_value
            self.positions["avg_entry_price"] = self.positions_list[0].avg_entry_price
            self.portfolio_btc_qty = float(self.positions_list[0].qty)
            print("---Retrieved All Positions---")
            return self.positions_list

    def get_position_vals(self):
        # Retrieves position_vals attributes dictionary
        return self.position_vals

    def print_position_vals(self):
        for key, vals in self.position_vals.items():
            print(key,": ", vals)

    def get_crypto_quote(self, symbol="BTC"):
        """Wrapper for setting up getting current crypto currency quote
        with ask price, ask size, bid price, bid price etc.
          Args:
              symbol: list of symbols as strings e.g. "BTC"

          Returns:
            Quote object with attributes:
                ask_price, ask_size, bid_exchange, bid_price, bid_size, conditions, symbol, tape, timestamp
          """
        if symbol == "BTC":
            symbol = ["BTC/USD"]
        req_params = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        self.current_quote = self.crypto_client.get_crypto_latest_quote(req_params)
        return self.current_quote


    def sell_crypto(self, quantity=1, symbol="BTC", time_in_force=TimeInForce.GTC):
        # time_in_force values
        # DAY = "day"
        # GTC = "gtc" [DEFAULT] good-till-cancelled
        # OPG = "opg"
        # CLS = "cls"
        # IOC = "ioc"
        # FOK = "fok"
        if symbol == "BTC":
            symbol = "BTC/USD"
        # preparing orders
        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.SELL,
            time_in_force=time_in_force
        )
        # Market order
        market_order = self.trading_client.submit_order(
            order_data=market_order_data
        )
        self.recent_order = market_order
        return self.recent_order

    def buy_crypto(self, quantity=1, symbol="BTC", time_in_force=TimeInForce.GTC):
        # time_in_force values
        # DAY = "day"
        # GTC = "gtc" [DEFAULT] good-till-cancelled
        # OPG = "opg"
        # CLS = "cls"
        # IOC = "ioc"
        # FOK = "fok"
        # ---------------------------------------------------------------------------------------

        # 1. Update Account information to obtain cash balance
        self.get_account_info()
        # 2. Update Account information to obtain cash balance

        if symbol == "BTC":
            symbol = "BTC/USD"
        # preparing orders
        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.BUY,
            time_in_force=time_in_force
        )
        # Market order
        market_order = self.trading_client.submit_order(
            order_data=market_order_data
        )
        self.recent_order = market_order
        return self.recent_order

    def get_orders(self, order_status="OPEN", order_side="BUY"):
        """Retrieves a list of order objects
        with asset_id, created_at, filled_at, filled_avg_price, filled_qt etc.
          Args:
              symbol: list of symbols as strings e.g. "BTC"

          Returns:
              List of order objects with attributes
                filled_at, filled_avg_price, qty
          """

        # Gets all orders to filter orders by OrderStatus.OPEN, CLOSED, ALL
        # params to filter orders by
        if order_status == "OPEN":
            order_status = QueryOrderStatus.OPEN
        elif order_status == "CLOSED":
            order_status = QueryOrderStatus.CLOSED
        elif order_status == "ALL":
            order_status = QueryOrderStatus.ALL
        else:
            print("-- order_status can only be NEW, CLOSED, or ALL --")
            return 1

        if order_side == "BUY":
            order_side = OrderSide.BUY
        elif order_side == "SELL":
            order_side = OrderSide.SELL
        else:
            print("-- order_side can only be BUY or SELL --")
            return 1
        request_params = GetOrdersRequest(
            status=order_status,
            side=order_side
        )
        # orders that satisfy params
        orders = self.trading_client.get_orders(filter=request_params)
        if order_status == "OPEN":
            self.recent_order = orders
        elif order_status == "CLOSED":
            self.closed_orders = orders
        else:
            self.closed_all_orders = orders
        return orders

    def cancel_orders(self):
        self.trading_client.close_all_positions(cancel_orders=True)

    def stream_trades(self):
        try:
            # ----- Need this for real time trade data -----------
            async def update_handler(data):
                # trade updates will arrive in our async handler
                print(data)
            # subscribe to trade updates and supply the handler as a parameter
            self.trading_stream.subscribe_trade_updates(update_handler)
            # start our websocket streaming
            self.trading_stream.run()
        except KeyboardInterrupt as e:
            self.trading_stream.stop()

    def get_portfolio_history(self):
        """API route for getting trading account portfolio history exists but the functions
        within the alpaca-py api isn't implemented yet or it is not clear where that method
        is for the trading client. Looking on github, the broker side method has the portfolio history method.
        Thus, the method has been implemented here using a API GET request via requests.
          Args:
              period
                The duration of the data in number + unit, such as 1D. unit can be D for day, W for week, M for month and A for year. Defaults to 1M.
                TYPE Optional[str]

                timeframe: The resolution of time window. 1Min, 5Min, 15Min, 1H, or 1D. If omitted, 1Min for less than 7 days period, 15Min for less than 30 days, or otherwise 1D.
                TYPE Optional[str]

                date_end
                The date the data is returned up to. Defaults to the current market date (rolls over at the market open if extended_hours is false, otherwise at 7am ET).
                TYPE Optional[date]

                extended_hours
                If true, include extended hours in the result. This is effective only for timeframe less than 1D.
                TYPE Optional[bool]

          Returns:
              dictionary of current quote data which includes:
                ask_price, ask_size, bid_exchange, bid_price, bid_size, conditions, symbol, tape, timestamp
          """
        headers = {"Apca-Api-Key-Id": self.KEY_ID, "Apca-Api-Secret-Key": self.SECRET_KEY }
        response = requests.get('https://paper-api.alpaca.markets/v2/account/portfolio/history', headers=headers)
        temp = json.loads(response.content)
        new_df = pd.DataFrame.from_dict(temp)
        new_df['profit_loss'] = new_df['equity'].diff()
        new_df['profit_loss_pct'] = new_df['equity'].pct_change()
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='s')
        self.portfolio_history = new_df
        return new_df

    def update_recent_orders(self):
        """Retrieves both recent buy and sell orders. Then, those orders are saved
        in prev_buy and prev_sell class attributes.

          Returns:
              List of order objects with attributes
                filled_at, filled_avg_price, qty
          """

        sell_request_params = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            side=OrderSide.SELL
        )
        # orders that satisfy params
        sell_orders = self.trading_client.get_orders(filter=sell_request_params)
        buy_request_params = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            side=OrderSide.BUY
        )
        # orders that satisfy params
        buy_orders = self.trading_client.get_orders(filter=buy_request_params)

        self.prev_sell_order = sell_orders[0]
        self.prev_buy_order = buy_orders[0]

        # Which order has the most recent date
        if self.prev_sell_order.filled_at > self.prev_buy_order.filled_at or self.prev_sell_order.filled_at == None:
            self.prev_order_is_sell = True
        else:
            self.prev_order_is_sell = False
