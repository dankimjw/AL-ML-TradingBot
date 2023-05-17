import json
import Utilities as util
import TradePlatform as tp
import BotTrader as bt
import datetime as dt
import pyfiglet
import time
import sys
import os
import signal
from multiprocessing import Process


menu_title = pyfiglet.figlet_format("AI/ML Bitcoin Trading Bot")
sub_title = pyfiglet.figlet_format("By: Miguel Garcia, Daniel Kim, Louis Lin")

menu_options = {
    1: 'Run trading bot in Test Mode',
    2: 'Run trading bot in Normal Mode',
    3: 'Execute a single manual trade to test Alpaca API',
    4: 'Exit'
}
def print_menu():
    print('------------------------------------------------------------------------------------------')
    print("Program Menu     ")
    print("☝️Note: app-keys.json must be in the same folder as this and related project files. ☝️")
    print('------------------------------------------------------------------------------------------')
    for key in menu_options.keys():
        print (key, '--', menu_options[key],'\n')

def test_bot_run(bot):
    print('------------------------------------------')
    print('\n ▶ Selected Test Mode')
    print('Running trading bot in TEST MODE...')
    print('Trading Interval every 5 seconds')
    print('Training Interval every 10 seconds')
    print('Total run time 20 seconds')
    print('------------------------------------------')
    time.sleep(1)
    bot.set_run_bot(True)
    bot.run_bot_trader(test_flag=True)
    bot.set_run_bot(False)

manual_options = {
    1: 'Buy',
    2: 'Sell',
    3: 'Exit'
}
def print_manual_menu():
    print('------------------------------------------------------------------------------------------')
    print(" Manual Menu ")
    print('------------------------------------------------------------------------------------------')
    for key in manual_options.keys():
        print (key, '--', manual_options[key],'\n')

def execute_single_trade(bot):
    print('------------------------------------------')
    print('\n ▶ Manual trade mode')
    print('Running trading bot in TEST MODE...')
    print('Trading Interval every 5 seconds')
    print('Training Interval every 10 seconds')
    print('Total run time 20 seconds')
    print('------------------------------------------')
    while(True):
        print_manual_menu()
        choice = ''
        try:
            choice = int(input('▶ Choose your trade type: '))
        except:
            print('Wrong input. Please enter a number ...')
        #Check what choice was entered and act accordingly
        if choice == 1:
           print("Executing manual buy order...")
           bot.execute_manual_trade('Buy')
        elif choice == 2:
           print("Executing manual sell order...")
           bot.execute_manual_trade('Sell')
        elif choice == 3:
            print('♢♢ Exiting... Thank you for trying our trading bot! ♢♢')
            exit()
        else:
            print('Invalid option. Please enter a number between 1 and 3.')


manual_options = {
    1: 'Buy',
    2: 'Sell',
    3: 'Exit'
}

def normal_bot_run(bot):
    print('------------------------------------------')
    # 'Run with default parameters (e.g. % cash per trade etc.)'
    print('------------------------------------------')
    print('\n ▶ Running trading bot in normal mode with default parameters.')
    print('Trading Interval every 30 seconds')
    print('Training Interval every 60 seconds')
    print('Total run time 86,400 seconds (1 day) or until bot is exited.')
    print('Note: This is primarily for testing the core functionality. '
          'Normal mode has the same default parameters such as % of cash used per trade etc.')
    print('In normal mode, the trading bot will continuously run for 1 day.')
    print('------------------------------------------')
    print('\n ★★ USE KEYBOARD INTERRUPT TO EXIT PROGRAM ★★ \n')
    print('------------------------------------------')
    time.sleep(3)
    print('\n ★★ USE KEYBOARD INTERRUPT TO EXIT PROGRAM ★★ \n')
    print("▶ Running trading bot in normal mode... ")
    bot.set_run_bot(True)
    # If total_run_time == None, bot will run for 1 day or 86,400 seconds
    # or until the bot is stopped via END BOT TRADER BUTTON
    try:
        status = bot.run_bot_trader(test_flag=False, trade_time_units='seconds', trade_time_interval=30,
                                    train_time_interval=60, total_run_time=86400)
        print("----- Normal execution loop: ", "Terminated Early" if status == 1 else "Loop Completed")
        bot.set_run_bot(False)
    except KeyboardInterrupt:
        print("----- ✓ Trading bot exited early ✓ -----")
        sys.exit(0)


if __name__=='__main__':
    # Allows the user to manually test the trading bot with 1) test mode 2) normal mode 3) manual trading mode
    print('------------------------------------------------------------------------------------------ \n')
    print('------------------------------------------------------------------------------------------ \n')
    print(menu_title)
    print('BY: Miguel Garcia, Daniel Kim, Louis Lin \n')
    print('')
    print('------------------------------------------------------------------------------------------')
    print('Checking for app-keys.json file for API KEY and SECRET.')
    try:
        with open('app-keys.json') as data_file:
            data = json.load(data_file)
        KEY_ID = data['API_KEY_ID']
        SECRET_KEY = data['SECRET_KEY']
        BASE_URL = "https://paper-api.alpaca.markets"
        print('✔ app-keys.json file found...')
        print('------------------------------------------------------------------------------------------')
    except OSError as e:
        print(f"{type(e)}: {e}")
        exit()

    print('API KEY ID: ', KEY_ID)
    print('SECRET_KEY: ', SECRET_KEY)
    bot = bt.BotTrader(KEY_ID, SECRET_KEY)

    while(True):
        print_menu()
        option = ''
        try:
            option = int(input('▶ Enter your choice: '))
        except:
            print('Wrong input. Please enter a number ...')
        #Check what choice was entered and act accordingly
        if option == 1:
           test_bot_run(bot)
        elif option == 2:
            normal_bot_run(bot)
        elif option == 3:
            execute_single_trade(bot)
        elif option == 4:
            print('♢♢ Exiting... Thank you for trying our trading bot! ♢♢')
            exit()
        else:
            print('Invalid option. Please enter a number between 1 and 4.')