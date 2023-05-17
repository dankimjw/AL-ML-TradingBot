import datetime as dt
import pandas as pd
#----[Utility/Helper Functions]-------
class Utilities:
    """Utilities class used to help with data validation and other helper operations.
    """
    def check_date(self, date:str):
        if isinstance(date, dt):
            return True
        else:
            return False

    def parse_date(self, date:str):
        """ Helper function for parsing string dates "9-10-22" "m-d-yy" string format
        into a datetime object
        Args:
            date: "m-d-yy" date as a string
        Returns:
            datetime object with the respect m-d-yy values
            False: if parameters are invalid
        """
        if isinstance(date, str):
            new_date = date.split("-")
            dt_date = dt.datetime(int(new_date[0]), int(new_date[1]), int(new_date[2]))
            return dt_date
        else:
            return False

    def reverse_parse_date(self, date):
        """ Helper function for parsing string dates "9-10-22" "m-d-yy" string format
        into a datetime object
        Args:
            date: "m-d-yy" date as a string
        Returns:
            datetime object with the respect m-d-yy values
            False: if parameters are invalid
        """
        if isinstance(date, str) == False:
            year = int(date.strftime("%Y"))
            month = int(date.strftime("%m"))
            day = int(date.strftime("%d"))
            new_date = str(year) + "-" + str(month) + "-" + str(day)
            return new_date
        else:
            return False

    def parse_historical_data(self, data):
        """ Helper function for parsing the multi-index dataframe from alpaca
        API calls.
        Args:
            data: pandas dataframe from alpaca get_crypto_bars method
        Returns:
            pandas dataframe with only 1 index for time intervals

        """
        symbol_name = data.index[1][0]
        btc_data = data.copy()
        btc_data = btc_data.droplevel("symbol")
        btc_data.index = btc_data.index.strftime('%Y-%m-%d')
        return symbol_name, btc_data

    def get_second_val(self, my_tuple):
        val = str(my_tuple[1])
        # print("my_val: ", val)
        return val

    def parse_positions(self, positions):
        new_col_list = []
        positions_df = pd.DataFrame(positions)
        num_cols = len(positions_df.columns)
        # print("positions idx: ", len(positions_df.columns))
        for i in range(0, num_cols, 1):
            new_col_list.append(positions_df[i][0][0])
            positions_df[i] = positions_df[i].apply(self.get_second_val)
        positions_df.columns = new_col_list
        return positions_df

    def parse_orders(self, orders):
        new_col_list = []
        orders_df = pd.DataFrame(orders)
        old_cols = orders_df.columns
        columns = orders_df.columns
        num_cols = len(orders_df.columns)
        for i in range(0,num_cols,1):
            new_col_list.append(orders_df[i][0][0])
            orders_df[i] = orders_df[i].apply(self.get_second_val)
        orders_df.columns = new_col_list
        orders_df.drop(columns=['client_order_id',  'expired_at', 'canceled_at', 'failed_at', 'replaced_at', 'replaced_by', 'replaces', 'asset_id',
                                'asset_class', 'notional', 'legs', 'trail_percent', 'trail_price', 'hwm',
                                'order_class', 'extended_hours', 'stop_price', 'type', 'limit_price'],axis=1, inplace=True)
        orders_df['qty'] = pd.to_numeric(orders_df['qty'], errors='coerce')
        orders_df['filled_qty'] = pd.to_numeric(orders_df['filled_qty'], errors='coerce')
        orders_df['filled_avg_price'] = pd.to_numeric(orders_df['filled_avg_price'], errors='coerce')
        orders_df['filled_avg_price'] = orders_df['filled_avg_price'].round(2)
        orders_df['created_at'] = pd.to_datetime(orders_df['created_at']).dt.tz_convert(None)
        orders_df['updated_at'] = pd.to_datetime(orders_df['updated_at']).dt.tz_convert(None)
        orders_df['submitted_at'] = pd.to_datetime(orders_df['submitted_at']).dt.tz_convert(None)
        orders_df['filled_at'] = pd.to_datetime(orders_df['filled_at']).dt.tz_convert(None)
        return orders_df

    def truncate_val(self, n, decimals=0):
        multiplier = 10 ** decimals
        return int(n * multiplier) / multiplier

    def parse_sort_portfolio(self, df):
        df['Date'] = df['timestamp']
        df.sort_values(by='timestamp', ascending=False, inplace=True)
        return df


