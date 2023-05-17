import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.colored_header import colored_header
from markdownlit import mdlit
import pandas as pd
import numpy as np
import TradePlatform as tp
import Utilities as util
import BotTrader as bt
import datetime as dt
from alpaca.data.timeframe import TimeFrame
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import concurrent.futures
import os
import signal
from multiprocessing import Process

# -------- For testing on local machine or GCLOUD ------------
try:
    # For testing on local machine
    with open('app-keys.json') as data_file:
        data = json.load(data_file)
    KEY_ID = data['API_KEY_ID']
    SECRET_KEY = data['SECRET_KEY']
    PASSWORD = data['PASSWORD']
    BASE_URL = "https://paper-api.alpaca.markets"
except FileNotFoundError:
    print("BotTrader.py: app-keys.json not found")
    print("Using st.secrets via streamlit to find API KEY and SECRET KEY")
    # For streamlit cloud
    KEY_ID = st.secrets["API_KEY_ID"]
    SECRET_KEY = st.secrets["SECRET_KEY"]
    PASSWORD = st.secrets["PASSWORD"]


# -------- Session Information ------------
# Initialization
if 'key' not in st.session_state:
    st.session_state['key'] = 'value'
# Session State also supports attribute based syntax
if 'key' not in st.session_state:
    st.session_state.key = 'value'

# ---- For streamlit cloud ----
# KEY_ID = st.secrets["API_KEY_ID"]
# SECRET_KEY = st.secrets["SECRET_KEY"]

# Create TraceAccount class instance with alpaca trading_client object instance
utils = util.Utilities()
ta = tp.TradeAccount(KEY_ID, SECRET_KEY)
bot = bt.BotTrader(KEY_ID, SECRET_KEY)

# ---- TEST ---------------------------------------------------------------------------------------
# Retrieve Account object for accounts

ta.get_account_info()
account_item = ta.get_account_item("cash")

st.set_page_config(layout="wide")

startDate = "2022-7-11"
new_date = utils.parse_date(startDate)


# Section 1 ---------------------------------- [TITLE] ----------------------------------
st.title('AI/ML Bitcoin Trading Bot')
st.subheader("Team: Miguel Garcia, Daniel Kim, Louis Lin")

# Subsection 1 ------- LINKS------------------

link1 = "@(Alpaca Account Home)(https://app.alpaca.markets/paper/dashboard/overview)"
mdlit(link1)
link2 = "@(Github Repository)(https://github.com/magarjr/AI-ML-Bitcoin-Trading-Bot)"
mdlit(link2)
# --------------------------------------------

# -------------------------------------------------------------------------------
# ------------[ Assumptions Section for Sidebar ]--------------------------------
# ---------------------[ Parameters SECTION ]---------------------
# If no, then initialize password_provided to False
# If pct_to_trade is already initialized, don't do anything
def reinitialize_state_vars():
    st.session_state.pct_to_trade = 0.1
    st.session_state.trade_time_units = "seconds"
    st.session_state.trade_time_interval = 5
    st.session_state.train_time_units = "seconds"
    st.session_state.train_time_interval = 10
    st.session_state.cash_threshold = .25
    st.session_state.decline_threshold = -0.10

if 'pct_to_trade' not in st.session_state:
    st.session_state.pct_to_trade = 0.1
#  if False, no password (correct/incorrect) was provided in the text box yet
if 'trade_time_units' not in st.session_state:
    st.session_state.trade_time_units = "seconds"

if 'trade_time_interval' not in st.session_state:
    st.session_state.trade_time_interval = 5

if 'train_time_interval' not in st.session_state:
    st.session_state.train_time_interval = 10

if 'cash_threshold ' not in st.session_state:
    st.session_state.cash_threshold  = .25

if 'decline_threshold ' not in st.session_state:
    st.session_state.decline_threshold  = -0.10

# Instantiate the Session State Variables
if 'cache' not in st.session_state:
    st.session_state.cache = {'pct_to_trade': .1, 'trade_time_units': "seconds", 'trade_time_interval': 5,
                              'train_time_interval': 10, 'cash_threshold': .25, 'decline_threshold': -0.10}

reinitialize_state_vars()

st.sidebar.subheader("Trading Bot Assumptions & Parameters")
# --- [ Percent Cash ] ---
# Side bar widget: Cash Percentage to Trade
st.sidebar.write("➊ Percentage of Cash to Trade")
pct_to_trade = st.sidebar.slider('1. Percentage of Cash to Trade', 1, 25, 1)
st.sidebar.write("Note: percentage of Cash can only be from 1% to 25% of total cash")
pct_to_trade = float(pct_to_trade) / 100
# Update percent of cash to trade
bot.update_pct_of_cash(pct_to_trade)
st.sidebar.write("Cash Proportion to trade: ", pct_to_trade)
st.session_state.pct_to_trade = pct_to_trade
st.sidebar.subheader('──────────────────────────────────')

# **** TRADING TIME INTERVALS ****
st.sidebar.write("❷. Time interval unit between trades (e.g. Minutes)")
trade_time_units  = st.sidebar.radio('2a. Select a time interval unit between trades:',
                                     ["Seconds", "Minutes", "Hours"], index=0)
st.session_state.trade_time_units = trade_time_units
print("time_units: ", trade_time_units )
st.sidebar.write("*Your selected time units*: ", trade_time_units )
if trade_time_units == "Minutes":
    # st.sidebar.write("2b. Time intervals between trades")
    trade_time_interval = st.sidebar.selectbox(
        '2b. Select the minutes interval between trades',
        # default value in 0th index
        (1, 2, 5, 10, 15, 30, 60), 0)
elif trade_time_units == "Seconds":
    trade_time_interval = st.sidebar.selectbox(
        '2b. Select the seconds interval between trades',
        # default value in 2nd index
        (1, 2, 5, 10, 15, 30, 60),0)
else:
    # st.sidebar.write("2b. Time intervals between trades")
    trade_time_interval = st.sidebar.selectbox(
        '2b. Select the hour interval between trades',
        # default value in 0th index
        (1, 2, 3, 4, 5, 6, 7, 8), 0)
trade_time_interval = float(trade_time_interval)
st.session_state.trade_time_interval = trade_time_interval
# Update the bot object attributes
bot.update_trade_time_units(trade_time_units)
bot.update_trade_time_interval(trade_time_interval)

st.sidebar.write('You selected to make a trading decision every ', trade_time_interval, " ", trade_time_units)
st.sidebar.subheader('──────────────────────────────────')

# **** MODEL TRAINING INTERVALS ****
st.sidebar.write("➌. Model training intervals (e.g. updating model every 2 trade intervals)")
train_time_units = trade_time_units
st.session_state.train_time_units = trade_time_units

train_frequency = st.sidebar.selectbox(
    '3. Select the how many trading intervals between updating the model',
    # default value in 1st index
    (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60), 1)

# Should be a multiple of the trading time intervals
train_time_interval = train_frequency * trade_time_interval
st.session_state.train_time_interval = train_time_interval
# Update bot object
bot.update_trade_time_interval(train_time_interval)
st.sidebar.write('Model will be updated every ', train_time_interval, "trade intervals")
st.sidebar.subheader('──────────────────────────────────')

# --- [ Percent Cash Threshold ] ---
# Side bar widget: Percent Cash Threshold
st.sidebar.write("➍ Percent Cash Threshold (max % of cash used in BTC assets) "
                 "(i.e. if buy signals lead to continuous buy orders, "
                 "the % cash threshold will prevent any additional buy orders.")
cash_threshold = st.sidebar.slider('4. Percent Cash Threshold', 1, 25, 25)
st.sidebar.write("Note: percentage of Cash can only be from 1% to 25% of total cash")
cash_threshold = float(cash_threshold) / 100
st.session_state.cash_threshold = cash_threshold
# Update percent of cash to trade
bot.update_cash_threshold(cash_threshold)

st.sidebar.write("% Cash threshold is ", cash_threshold)
st.sidebar.subheader('──────────────────────────────────')

# --- [ Max Price Decline Threshold ] ---
# Side bar widget: Percent Cash Threshold
st.sidebar.write("➎ Max Percent Decline Threshold for portfolio "
                 "(e.g. if BTC sell price declines 10% or more respective to the previous buy price, "
                 "the % decline threshold will trigger liquidation of all BTC holdings. "
                 "This functionality is used to prevent unrecoverable downside trends.")
decline_threshold = st.sidebar.slider('4. Percent Decline Threshold',10, 30, 10)
st.sidebar.write("Note: max % decline of portfolio value can only be from 1% to 25% of total cash")
decline_threshold = (float(decline_threshold) / 100) * -1
st.session_state.decline_threshold = decline_threshold
bot.update_decline_threshold(decline_threshold)

st.sidebar.write("% Decline threshold is ",decline_threshold)
st.sidebar.subheader('──────────────────────────────────')
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------

# ----------------- [ BOT CONTROLS & Instructions ] --------------------------
colored_header(
    label="Section 1. Instructions",
    description="Click on the collapsable instructions below",
    color_name="yellow-70"
)

with st.expander("See instruction details!"):
    st.write("**Order of testing**")
    st.write('A. Enter Password [Section 2]')
    st.write('B. Manually test API functionality [Section 3]')
    st.write('C. Test trading bot [Section 4]')
    st.write("")
    st.write("**Testing the trading bot**")
    st.write("From the sidebar menu: ")
    st.write("1. Choose: Percentage of Cash to Trade")
    st.write("2. Choose:  Select a time interval unit between trades")
    st.write("3. Choose: Select a time interval between trades")
    st.write("4. Percent Cash Threshold (max % of cash used in BTC assets) ")
    st.write("5.  Max Percent Decline Threshold for portfolio ")
    st.write("")
    st.write("From the main page below:")
    st.write(
        "1. Enter the correct password (see project instructions document) to enable Start Bot Trader/ End Bot Trader buttons")
    st.write("2. Click 'Start Bot Trader' button to launch the trading bot")
    st.write("3. Click 'End Bot Trader' button to shutdown the trading bot")

colored_header(
    label="Section 2. Enter Password",
    description="Password is required to enable manual and bot testing",
    color_name="yellow-80",
)

# ---------------------[ PASSWORD SECTION ]---------------------
# If no, then initialize password_provided to False
# If password_provided is already initialized, don't do anything
if 'password_provided' not in st.session_state:
    st.session_state.password_provided = False
#  if False, no password (correct/incorrect) was provided in the text box yet
if 'correct_password' not in st.session_state:
    st.session_state.correct_password = False

# Correct/Incorrect password provided (doesn't matter if it is correct)
def password_provided():
    st.session_state.password_provided = True
    return True

# Resets all session variables
def reset_session():
    st.session_state.password_provided = False
    st.session_state.correct_password = False
    st.session_state.manual_trade_count = 0
    st.session_state.trade_time_units = "seconds"
    st.session_state.pct_to_trade = 0.1
    st.session_state.trade_time_interval = 5
    st.session_state.train_time_interval = 10
    st.session_state.cash_threshold = .25
    st.session_state.decline_threshold = -0.10
    st.session_state.pw = "Enter Password"
    user_pw = "Enter Password"
    password_provided = None


def check_pw(user_pw):
    password_provided()
    if user_pw == PASSWORD:
        st.session_state.pw = user_pw
        st.session_state.correct_password = True
        return True
    else:
        st.session_state.correct_password = False
        return False

col_pw, col_reset, space2a = st.columns(3)

with col_pw:
    user_pw = st.text_input('Enter Password to start bot and press "Enter" on your keyboard','Password',
                       help="Password is needed to execute trades and use the trader bot")
    if user_pw != 'Password':
        correct_password = check_pw(user_pw)
        password_provided = password_provided()
    else:
        correct_password = False
        password_provided = False

    pw_msg = st.empty()
    if correct_password:
        # st.write("st.session_state.correct_password: ", st.session_state.correct_password)
        # st.write("st.session_state.pw: ", st.session_state.pw)
        pw_msg.success('*Password is correct.*')
        # Incorrect password provided
    elif password_provided == True and correct_password == False:
        # st.write("st.session_state.password_provided: ", st.session_state.password_provided)
        pw_msg.error('*Incorrect password.*')
    else:
        pw_msg.empty()

with col_reset:
    st.write("Reset all session variables (password, trade count etc.)")
    reset = st.button('Reset Session', type="secondary", on_click=reset_session)
    if reset:
        correct_password = False
        password_provided = False
        pw_msg.empty()



#---------------------[ Manual Order Execution SECTION ]---------------------
colored_header(
    label="Section 3. Manual API Test",
    description="This is a description",
    color_name="light-blue-70",
)
# If no, then initialize password_provided to False
# If password_provided is already initialized, don't do anything
if 'manual_trade_count' not in st.session_state:
    st.session_state.manual_trade_count = 0

manual_trade_count = 0
def update_manual_trade_count(flag=0, manual_trade_count=0):
    if flag == 0:
        st.session_state.manual_trade_count += 1
        manual_trade_count += 1
        return manual_trade_count
    elif flag == 1:
        st.session_state.manual_trade_count = 0
        manual_trade_count = 0
        return manual_trade_count
    else:
        return -1


st.write(
    "**To manually test the Alpaca Trading API, please enter the correct password above, select/enter the sell/buy order information, and click the 'Execute Trade' button.**")
col1b, col2b = st.columns(2)
traded_qty = 0
with col1b:
    # --- Manual API TEST Metric cards ---
    with col1b:
        # Current BTC prices
        bot.update_account_info()
        btc_price = '$ {:>9,.2f}'.format(float(bot.trade_account.cash))
        title = 'Current Cash'
        st.metric(title, btc_price, help="Total cash available in the trading account.")
        # Update the trade quantity
        bot.calculate_trade_qty()
        cash_used_per_trade = '$ {:>9,.2f}'.format(float(bot.max_trade_usd))
        title = 'Calculated Available Cash Used per Trade'
        st.metric(title, cash_used_per_trade, help="Cash available per trade will decrease as more buy orders are made.")

    # --- Manual API TEST radio button and execute trade button ---
    with col2b:
        trade_type = st.radio(
            "Select Trade Type:",
            ('Buy', 'Sell'))
        if trade_type == 'Buy':
            st.write('You selected buy.')
        else:
            st.write("You selected sell.")

        # ------- Session State Value --------
        if correct_password:
            st.write("Click the button to execute order:")
            exec_msg = st.empty()
            if st.button('Execute Trade', type="primary"):
                # ------- Session State Value --------
                exec_msg.write('**Order Executed.**')
                traded_qty = bot.execute_manual_trade(trade_type)
                if traded_qty == -1 and trade_type == "Buy":
                    exec_msg.write("Not enough cash in account to execute a buy order")
                else:
                    manual_trade_count = update_manual_trade_count()

            reset_count = st.button('Reset Manual Trade Count', type="secondary")
            if reset_count == True:
                manual_trade_count = update_manual_trade_count(1, manual_trade_count)

            st.write("Manual Trade Count: ", manual_trade_count)
        else:
            st.write("Click the button to execute order:")
            if st.button('Execute Trade', type="secondary"):
                st.write('Password is incorrect.')


st.markdown('#### Most Recent Order: ')
st.write('To get the most recent order click the "Get most recent order" button.')
if st.button('Get most recent order', type="primary"):
    temp_df = bot.update_orders_log()
    if manual_trade_count > 1 or manual_trade_count != None:
        final_traded_qty = temp_df.loc[0:5]
    else:
        final_traded_qty = temp_df.loc[0:1]
    side = str(temp_df['side'])
    if side == 'OrderSide.Buy':
        trade_side = "Buy"
    else:
        trade_side = "Sell"
    st.write("**Most recent trade is a ", trade_side, " order**")
    st.write(final_traded_qty)
else:
    temp_df = bot.update_orders_log()
    if manual_trade_count > 1 or manual_trade_count != None:
        final_traded_qty = temp_df.loc[0:5]
    else:
        final_traded_qty = temp_df.loc[0:1]
    side = str(temp_df['side'])
    if side == 'OrderSide.Buy':
        trade_side = "Buy"
    else:
        trade_side = "Sell"
    st.write("**Most recent trade is a ", trade_side, " order**")
    st.write(final_traded_qty)

# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# -------- [Section 4: TRADING BOT] --------
colored_header(
    label="Section 4. Trading Bot",
    description="Controls for the trading bot",
    color_name="light-blue-70",
)

st.write("**To begin the trading bot, please enter the correct password and click the 'Start Bot Trader' button.**")
col1, col2, col3 = st.columns(3)
start_bot = False

# initialize pid
if "pid" not in st.session_state:
    st.session_state.pid = None

def t1_method(test_flag):
    print("t1 run bot flag: ", test_flag)
    print("t1 Starting bot going Online...")
    # def run_bot_trader(test_flag=False, trade_time_units='seconds',
    #                   trade_time_interval=None,
    # train_time_interval=None,
    status = bot.run_bot_trader(test_flag = True)
    print("-----t1 test loop: ", "Terminated Early" if status == 1 else "Loop Completed")

def t2_method(test_flag,trade_time_units, trade_time_interval,train_time_interval, total_run_time):
    print("t2 run bot flag: ", test_flag)
    print("t2 Starting bot going Online...")
    # def run_bot_trader(test_flag=False, trade_time_units='seconds',
    #                   trade_time_interval=None,
    # train_time_interval=None,
    # If total_run_time == None, bot will run for 1 day or 86,400 seconds
    # or until the bot is stopped via END BOT TRADER BUTTON
    status = bot.run_bot_trader(test_flag, trade_time_units,
                                   trade_time_interval,
                                   train_time_interval,
                                   total_run_time)

    print("-----t2test loop: ", "Terminated Early" if status == 1 else "Loop Completed")
#

# Helper function
def show_bot_status(start_bot=False, placeholder=st.empty()):
    with placeholder.container():
        if start_bot == True:
            st.metric("Trading bot status:", "Online")
        else:
            st.metric("Trading bot status:", "Offline")

with col_pw:
    # pw = st.text_input('Enter Password to start bot and press "Enter"', 'Password')
    # show_bot_status(start_bot)
    with col1:
        # Placeholder for bot status (Online vs. Offline)
        placeholder = st.empty()

    with col2:
        test_mode = st.checkbox('Test Mode', True, help='Test mode will run the bot for 20 seconds with trading'
                                                        ' decisions/executions made every 5 seconds and'
                                                        ' model updates occurring every 10 seconds.')
        st.write("Click the button to begin trading:")
        show_bot_status(start_bot, placeholder)
        if correct_password:
            start = st.button('Start Bot Trader', type="primary")
            if start:
                st.write('**Trading bot is live.**')
                start_bot = True
                if test_mode == True:
                    show_bot_status(start_bot, placeholder)
                    # def run_bot_trader(self, test_flag=False, trade_time_units='seconds',
                    #                   trade_time_interval=None,
                                       # train_time_interval=None,
                    #                    total_run_time=None
                    p = Process(target=t1_method, args=(test_mode, ))
                    p.start()
                    st.session_state.pid = p.pid
                    st.write("Started process with pid:", st.session_state.pid)
                    start_bot = False
                    bot.set_run_bot(start_bot)
                else:
                    show_bot_status(start_bot, placeholder)
                    trade_time_units = st.session_state.trade_time_units if st.session_state.trade_time_units != None else trade_time_units
                    trade_time_interval = st.session_state.trade_time_interval if st.session_state.trade_time_interval != None else trade_time_interval
                    train_time_interval = st.session_state.train_time_interval if st.session_state.train_time_interval != None else train_time_interval

                    p = Process(target=t2_method, args=(False,trade_time_units,
                                                        trade_time_interval,
                                                        train_time_interval,
                                                        None))
                    p.start()
                    st.session_state.pid = p.pid
                    st.write("Started process with pid:", st.session_state.pid)
                    start_bot = False
                    bot.set_run_bot(start_bot)
        else:
            st.button('Start Bot Trader', type="secondary")
            st.write('Password is incorrect.')

        st.write("Click the button to end trading:")
        if correct_password:
            stop = st.button('End Bot Trader', type="primary")
            if stop:
                if st.session_state.pid != None:
                    # Had to update due to windows os not having compatible linux signals such as SIGKILL
                    os.kill(st.session_state.pid, signal.SIGKILL)
                    # signal.raise_signal(signal.SIGINT)
                    # os.kill(st.session_state.pid, signal.CTRL_C_EVENT)
                    st.write("Stopped process with pid:", st.session_state.pid)
                    st.session_state.pid = None
                    start_bot = False
                    # Set the bot run flag to false
                    bot.set_run_bot(start_bot)
                    st.write('**Trading bot is "Offline"**')
                else:
                    st.write("No process to terminate.")
        else:
            st.button('End Bot Trader', type="secondary")
            st.write('Password is incorrect.')

# # ------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------

tabs_font_css = """
<style>
button[data-baseweb="tab"] {
  font-size: 20px;
}
</style>
"""
# st.markdown("""---""")
st.write(tabs_font_css, unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📈 Portfolio", "🗃 Historical_Data"])

with tab1:
    st.header("Portfolio Information")
    # -----------------[Account BTC Data Table and Chart from API] -----------------
    # st.markdown("""---""")
    positions = ta.get_positions()
    position_table_title = "**Current Positions:**"
    st.subheader(position_table_title)

    if positions == 0:
        st.write("---------- **No Current Positions** ----------")
    else:
        ####### -- TO DO----------------
        # 1. Drop any columns that are confusing or don't provide insight
        new_positions = utils.parse_positions(positions)
        avg_entry = 'Avg. Entry Price:  **$ {:>9,.2f}**'.format(float(new_positions["avg_entry_price"][0]))
        quantity = '{:>9,.8f}'.format(float(new_positions['qty'][0]))
        current_price = '$ {:>9,.2f}'.format(float(new_positions["current_price"][0]))
        change_today = '**Change Today:  {:>+9,.8f} %**'.format(float(new_positions["change_today"][0]) * 100)
        avg_entry2 = '${:>9,.2f}'.format(float(new_positions["avg_entry_price"][0]))
        quantity2 = 'Quantity:  {:>9,.8f}'.format(float(new_positions['qty'][0]))
        current_price2 = 'Current Price: **$ {:>9,.2f}**'.format(float(new_positions["current_price"][0]))
        change_today2 = '{:>+4,.4f} %'.format(float(new_positions["change_today"][0]) * 100)
        st.write("Positions in BTC/USD")

        c1, c2, cc = st.columns(3)
        with c1:
            st.metric("Quanity", quantity)

        with c2:
            st.metric("Average Entry Price", avg_entry2)

        c3, c4, cc2 = st.columns(3)
        with c3:
            st.metric("Current Price", current_price)

        with c4:
            st.metric("Change Today", change_today2)

    style_metric_cards()

    # -----------------[Account BTC Portfolio History] -----------------
    st.markdown("""---""")
    st.subheader("Portfolio History")
    portfolio = ta.get_portfolio_history()
    port_df = utils.parse_sort_portfolio(portfolio)

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces
    fig.add_trace(
        go.Scatter(x=port_df['timestamp'], y=port_df['equity'], name="Equity"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=port_df['timestamp'], y=port_df['profit_loss_pct'], name="Profit/Loss"),
        secondary_y=True,
    )
    # Add figure title
    fig.update_layout(
        title_text="<b>Portfolio Performance</b>", template='plotly'
    )
    # Set x-axis title
    fig.update_xaxes(title_text="<b>Date</b>")

    # Set y-axes titles
    fig.update_yaxes(title_text="<b>Equity</b>", secondary_y=False)
    fig.update_yaxes(title_text="<b>Profit/Loss</b>", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    # fig.show()

    st.write(portfolio)

    st.markdown("""---""")

    # ----- Order History data table Section is moved after portfolio history -------
    st.subheader("**ORDER HISTORY**")
    # ----- Order History data table Section is moved after portfolio history -------
    # st.write("**ORDER HISTORY**")
    # with st.expander("Click to See order history details!"):
    #     st.dataframe(orders_df)
    orders_df_new = bot.update_orders_log()
    st.dataframe(orders_df_new)

    # -------------------------------------------------------------------------------------------

st.sidebar.subheader("Historical Data Selection")
today = dt.datetime.today()
yesterday = dt.datetime.today() - dt.timedelta(days=7)

start_date = st.sidebar.date_input('Historical Data Start Date',
                                   value=dt.datetime(yesterday.year, yesterday.month, yesterday.day),
                                   min_value=dt.datetime(2018, 1, 1),
                                   max_value=dt.datetime(yesterday.year, yesterday.month, yesterday.day))
new_start_date = utils.reverse_parse_date(start_date)
end_date = st.sidebar.date_input('Historical Data End Date', max_value=dt.datetime(today.year, today.month, today.day))
# print(type(start_date))


bars = ta.get_crypto_data(tp.TimeFrame.Day, new_start_date, None, "BTC", True)
print(bars)
# curr_data = ta.get_current_data(TimeFrame.Minute)
symbol, df = ta.utils.parse_historical_data(bars)
# ----------------------------------------------------------------------------

with tab2:
    st.header("BTC/USD Historical Market Data")
    # -----------------[Historical BTC Data Table and Chart] -----------------
    # st.markdown("""---""")
    if end_date == dt.datetime(today.year, today.month, today.day):
        table_title = "Historical Crypto Market Data: From " + str(start_date) + " to " + "Current Date"
    else:
        table_title = "Historical Crypto Market Data: From " + str(start_date) + " to " + str(end_date)

    st.subheader("Historical Market Data")
    st.write("Note: Use the sidebar menu to change the historical data dates")
    st.write(table_title)

    st.write("**Crypto Currency**: " + "**" + symbol + "**")

    st.write(df)
    st.line_chart(df)
    # -------------------------------------------------------------------------------------------
    st.write("Markets a bit 'rough'? Smile! ")
    st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
