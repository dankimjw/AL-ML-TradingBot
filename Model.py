import warnings
warnings.filterwarnings('ignore')
import os
import pandas as pd
import numpy as np
import math
import datetime as dt
import matplotlib.pyplot as plt

from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler

from itertools import product

import tensorflow as tf

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.layers import LSTM

import DataCollector 

"""

The purpose of this module is to train a neural network model with Bitcoin
historical data and provide a future Bitcoin price predicition. 

The majority of the code used in the module came from or was adapted from Rohan Paul's 
'Bitcoin Price Prediction with LSTM' project, his GitHub repository containing 
this code can be found at: 
https://github.com/rohan-paul/MachineLearning-DeepLearning-Code-for-my-YouTube-Channel/blob/master/Finance_Stock_Crypto_Trading/Bitcoin_Price_Prediction_with_LSTM.ipynb 

"""

EPOCHS = 5
PREDICTION_DAYS = 60

DataCollector.fetch_new_data()

data_file_path = './training_data/dataset.csv'
btc_input_df = pd.read_csv(data_file_path, parse_dates=['time'])

btc_input_df_datetype = btc_input_df

btc_input_df_datetype['time'] = pd.to_datetime(btc_input_df_datetype['time'],unit='s').dt.date

group = btc_input_df_datetype.groupby('time')

btc_closing_price_groupby_date = group['close'].mean()

# Set Train data to be up to Total data length minus PREDICTION_DAYS
df_train= btc_closing_price_groupby_date[:len(btc_closing_price_groupby_date)-PREDICTION_DAYS].values.reshape(-1,1)

# Set Test data to be the last 60 days
df_test= btc_closing_price_groupby_date[len(btc_closing_price_groupby_date)-PREDICTION_DAYS:].values.reshape(-1,1)

scaler_train = MinMaxScaler(feature_range=(0, 1))
scaled_train = scaler_train.fit_transform(df_train)

scaler_test = MinMaxScaler(feature_range=(0, 1))
scaled_test = scaler_test.fit_transform(df_test)


def dataset_generator_lstm(dataset, look_back=5):
    # A “lookback period” defines the window-size of how many
    # previous timesteps are used in order to predict
    # the subsequent timestep. 
    dataX, dataY = [], []
    
    for i in range(len(dataset) - look_back):
        window_size_x = dataset[i:(i + look_back), 0]
        dataX.append(window_size_x)
        dataY.append(dataset[i + look_back, 0]) # this is the label or actual y-value
    return np.array(dataX), np.array(dataY)

trainX, trainY = dataset_generator_lstm(scaled_train)

testX, testY = dataset_generator_lstm(scaled_test)

trainX = np.reshape(trainX, (trainX.shape[0], trainX.shape[1], 1))

testX = np.reshape(testX, (testX.shape[0], testX.shape[1], 1 ))


def build_model(trainX, trainY, testX, testY):
    model = Sequential()

    model.add(LSTM(units = 128, activation = 'relu',return_sequences=True, input_shape = (trainX.shape[1], trainX.shape[2])))
    model.add(Dropout(0.2))

    model.add(LSTM(units = 64, input_shape = (trainX.shape[1], trainX.shape[2])))
    model.add(Dropout(0.2))

    model.add(Dense(units = 1))

    model.summary()
    model.compile(optimizer = 'adam', loss = 'mean_squared_error')

    history = model.fit(trainX, trainY, batch_size = 32, epochs = EPOCHS, verbose=1, shuffle=False, validation_data=(testX, testY))

    return model

# BTC Price Prediction
def tomorrows_prediction(model):
    lookback = 5
    testX_last_5_days = testX[testX.shape[0] - lookback :  ]

    for i in range(lookback):
        predicted_forecast_price = model.predict(testX_last_5_days[i:i+1])
        predicted_forecast_price = scaler_test.inverse_transform(predicted_forecast_price.reshape(-1, 1))

    print("Tomorrow's BTC price is predicted at: ", predicted_forecast_price[0][0])
    return predicted_forecast_price


model = build_model(trainX, trainY, testX, testY)
tomorrows_prediction(model)




