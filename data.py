########################################################################
#
# Functions for loading financial data.
#
# Data from several different files are combined into a single
# Pandas DataFrame for each stock or stock-index.
#
# The price-data is read from CSV-files from Yahoo Finance.
# Other financial data (Sales Per Share, Book-Value Per Share, etc.)
# is read from tab-separated text-files with date-format MM/DD/YYYY.
#
########################################################################
#
# This file is part of FinanceOps:
#
# https://github.com/Hvass-Labs/FinanceOps
#
# Published under the MIT License. See the file LICENSE for details.
#
# Copyright 2018 by Magnus Erik Hvass Pedersen
#
########################################################################

import pandas as pd
import os
from data_keys import *
from returns import total_return

########################################################################

# Data-directory. Set this before calling any of the load-functions.
data_dir = "data/"

########################################################################
# Private helper-functions.


def _resample_daily(data):
    """
    Resample data using linear interpolation.

    :param data: Pandas DataFrame or Series.
    :return: Resampled daily data.
    """
    return data.resample('D').interpolate(method='linear')


def _load_data(path):
    """
    Load a CSV-file with tab-separation, date-index is in first column
    and uses the MM/DD/YYYY.

    This is a simple wrapper for Pandas.read_csv().

    :param path: Path for the data-file.
    :return: Pandas DataFrame.
    """
    data = pd.read_csv(path,
                       sep="\t",
                       index_col=0,
                       parse_dates=True,
                       dayfirst=False)

    return data


def _load_price_yahoo(ticker):
    """
    Load share-price data from a Yahoo CSV-file.

    Only retrieve the 'Close' and 'Adj Close' prices
    which are interpolated to daily values.

    The 'Close' price-data is adjusted for stock-splits.

    The 'Adj Close' price-data is adjusted for both
    stock-splits and dividends, so it corresponds to
    the Total Return.

    https://help.yahoo.com/kb/SLN2311.html

    :param ticker: Ticker-name for the data to load.
    :return: Pandas DataFrame with SHARE_PRICE and TOTAL_RETURN
    """

    # Path for the data-file to load.
    path = os.path.join(data_dir, ticker + " Share-Price (Yahoo).csv")

    # Read share-prices from file.
    price_raw = pd.read_csv(path,
                            index_col=0,
                            header=0,
                            sep=',',
                            parse_dates=[0],
                            dayfirst=False)

    # Rename columns.
    columns = \
        {
            'Adj Close': TOTAL_RETURN,
            'Close': SHARE_PRICE
        }
    price = price_raw.rename(columns=columns)

    # Select the columns we need.
    price = price[[TOTAL_RETURN, SHARE_PRICE]]

    # Interpolate to get prices for all days.
    price_daily = _resample_daily(price)

    return price_daily


########################################################################
# Public functions.


def load_usa_cpi():
    """
    Load the U.S. Consumer Price Index (CPI) which measures inflation.
    The data is interpolated for daily values.

    http://www.bls.gov/cpi/data.htm

    :return: Pandas DataFrame.
    """

    # Path for the data-file to load.
    path = os.path.join(data_dir, "USA CPI.csv")

    # Load the data.
    data = pd.read_csv(path, sep=",", parse_dates=[3], index_col=3)

    # Rename the index- and data-columns.
    data.index.name = "Date"
    data.rename(columns={"Value": CPI}, inplace=True)

    # Resample by linear interpolation to get daily values.
    data_daily = _resample_daily(data[CPI])

    return data_daily


def load_index_data(ticker):
    """
    Load data for a stock-index from several different files
    and combine them into a single Pandas DataFrame.

    - Price is loaded from a Yahoo-file.
    - Dividend, Sales Per Share, and Book-Value Per Share
      are loaded from separate files.

    The Total Return is produced from the share-price and dividend.
    The P/Sales and P/Book ratios are calculated daily.

    Note that dividend-data is usually given quarterly for stock
    indices, but the individual companies pay dividends at different
    days during the quarter. When calculating the Total Return we
    assume the dividend is paid out and reinvested quarterly.
    There is probably a small error from this. We could instead
    spread the quarterly dividend evenly over all the days in
    the quarter and reinvest these small portions daily. Perhaps
    this would create a smaller estimation error. It could be
    tested if this is really a problem or if the estimation error
    is already very small.

    :param ticker:
        Name of the stock-index used in the filenames e.g. "S&P 500"
    :return: Pandas DataFrame with the data.
    """
    # Paths for the data-files.
    path_dividend_per_share = os.path.join(data_dir, ticker + " Dividend Per Share.txt")
    path_sales_per_share = os.path.join(data_dir, ticker + " Sales Per Share.txt")
    path_book_value_per_share = os.path.join(data_dir, ticker + " Book-Value Per Share.txt")

    # Load the data-files.
    price_daily = _load_price_yahoo(ticker=ticker)
    dividend_per_share = _load_data(path=path_dividend_per_share)
    sales_per_share = _load_data(path=path_sales_per_share)
    book_value_per_share = _load_data(path=path_book_value_per_share)

    # Merge price and dividend into a single data-frame.
    df = pd.concat([price_daily, dividend_per_share], axis=1)

    # Only keep the rows where the share-price is defined.
    df.dropna(subset=[SHARE_PRICE], inplace=True)

    # Calculate the Total Return.
    # The price-data from Yahoo does not contain the Total Return
    # for stock indices because it does not reinvest dividends.
    df[TOTAL_RETURN] = total_return(df=df)

    # Add financial data to the data-frame (interpolated daily).
    df[SALES_PER_SHARE] = _resample_daily(sales_per_share)
    df[BOOK_VALUE_PER_SHARE] = _resample_daily(book_value_per_share)

    # Add financial ratios to the data-frame (daily).
    df[PSALES] = df[SHARE_PRICE] / df[SALES_PER_SHARE]
    df[PBOOK] = df[SHARE_PRICE] / df[BOOK_VALUE_PER_SHARE]

    return df


def load_stock_data(ticker):
    """
    Load data for a single stock from several different files
    and combine them into a single Pandas DataFrame.

    - Price is loaded from a Yahoo-file.
    - Sales Per Share and Book-Value Per Share are loaded from separate files.

    The Total Return is taken directly from the Yahoo price-data.
    The P/Sales and P/Book ratios are calculated daily.

    :param ticker:
        Name of the stock used in the filenames e.g. "WMT"
    :return: Pandas DataFrame with the data.
    """
    # Paths for the data-files.
    path_sales_per_share = os.path.join(data_dir, ticker + " Sales Per Share.txt")
    path_book_value_per_share = os.path.join(data_dir, ticker + " Book-Value Per Share.txt")

    # Load the data-files.
    price_daily = _load_price_yahoo(ticker=ticker)
    sales_per_share = _load_data(path=path_sales_per_share)
    book_value_per_share = _load_data(path=path_book_value_per_share)

    # Use the DataFrame for the price and add more data-columns to it.
    df = price_daily

    # Only keep the rows where the share-price is defined.
    df.dropna(subset=[SHARE_PRICE], inplace=True)

    # Add financial data to the data-frame (interpolated daily).
    df[SALES_PER_SHARE] = _resample_daily(sales_per_share)
    df[BOOK_VALUE_PER_SHARE] = _resample_daily(book_value_per_share)

    # Add financial ratios to the data-frame (daily).
    df[PSALES] = df[SHARE_PRICE] / df[SALES_PER_SHARE]
    df[PBOOK] = df[SHARE_PRICE] / df[BOOK_VALUE_PER_SHARE]

    return df

########################################################################
