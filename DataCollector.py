from datetime import date, datetime, timedelta
from Historic_Crypto import HistoricalData
from csv import writer
import pandas as pd


# Obtain today's date and convert to datetime.datetime format for use in comparison
today = date.today()
today_formatted = str(today) + "-00-00"
today = str(today) + " 00:00:00"
today = datetime.strptime(today, "%Y-%m-%d %H:%M:%S")

# Puts the new and old data csv files in the correct order to be merged
csv_files = ['training_data/new_data.csv', 'training_data/old_data.csv']

# Get the most recent date from the dataset (output will be in format YYYY-MM-DD HH:MM:SS) 
# NOTE: MM & SS will always be zero
with open("training_data/dataset.csv", 'r') as data:
    recent = data.readlines()[1].split(',')
    most_recent_date = recent[0]

# Convert the most recent day from string to datetime.datetime format for use in comparison
most_recent_date = datetime.strptime(most_recent_date, "%Y-%m-%d %H:%M:%S")

# Get the new start date where dataset left off and convert to format used by HistoricalData
start_date = most_recent_date + timedelta(hours=1)
start_date = datetime.strftime(start_date, "%Y-%m-%d-%H-%M")


def fetch_new_data():
    # If most recent date in dataset is prior to today's date, fetch new data
    if most_recent_date < today:
        print("The dataset is out of date, obtaining new data...")

        # Fetches new data that is not currently in the dataset
        new_data = HistoricalData('BTC-USD', 3600, start_date=start_date, end_date=today_formatted).retrieve_data()
        new_data = new_data[::-1]
        new_data.to_csv(path_or_buf="training_data/new_data.csv")

        # Makes a copy of the current dataset as a backup
        old_data = pd.read_csv("training_data/dataset.csv")
        old_data.to_csv("training_data/old_data.csv", index=False)

        # Merges the old_data.csv and new_data.csv together into dataset.csv for an up-to-date dataset
        df_concat = pd.concat([pd.read_csv(f) for f in csv_files ], ignore_index=True)
        df_concat.to_csv("training_data/dataset.csv", index=False)
        
        return True
    else:
        print("Your data is up to date.")
        return False 

