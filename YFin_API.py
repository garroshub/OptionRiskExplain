"""
@author: Garros

"""
import yfinance as yf
import pandas as pd
from datetime import datetime
import numpy as np

def grabExpDates(ticker):
    """
    Returns a dataframe of expiration dates available on Yahoo Finance.
    """
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        
        if not expirations:
            print(f"No expiration dates found for {ticker}")
            return pd.DataFrame(columns=['Unix Date'])
            
        expDatesNormal = pd.to_datetime(expirations)
        expDatesUnix = [int(x.timestamp()) for x in expDatesNormal]
        
        df = pd.DataFrame({'Date': expDatesNormal, 'Unix Date': expDatesUnix})
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Error getting expiration dates for {ticker}: {str(e)}")
        return pd.DataFrame(columns=['Unix Date'])

def optionChain(ticker='SPY', date='2022-11-18', calls_puts='calls'):
    """
    Get option chain data using yfinance
    """
    try:
        stock = yf.Ticker(ticker)
        
        opt = stock.option_chain(date)
        
        if calls_puts == 'calls':
            chain = opt.calls
        else:
            chain = opt.puts
            
        chain['Exp'] = pd.to_datetime(date)
        
        required_columns = ['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']
        for col in required_columns:
            if col not in chain.columns:
                chain[col] = 0
                
        return chain
    except Exception as e:
        print(f"Error getting option chain for {ticker}: {str(e)}")
        return pd.DataFrame()

def fnYFinJSON(stock, field):
    """
    Get stock information using yfinance
    """
    if not stock:
        return "enter a ticker"
    try:
        ticker = yf.Ticker(stock)
        info = ticker.info
        if field == 'regularMarketPrice':
            return ticker.fast_info['lastPrice']
        elif field in info:
            return info[field]
        else:
            print(f"Field {field} not found in stock info")
            return "N/A"
    except Exception as e:
        print(f"Error getting data for {stock}: {str(e)}")
        return "N/A"

def fnYFinJSONAll(stock):
    """
    Get all stock information using yfinance
    """
    try:
        ticker = yf.Ticker(stock)
        info = ticker.info
        df = pd.DataFrame([info])
        if not df.empty and 'symbol' in df.columns:
            df.set_index('symbol', inplace=True)
        return df
    except Exception as e:
        print(f"Error getting all data for {stock}: {str(e)}")
        return pd.DataFrame()

def fnYFinHist(stock, interval='1d', day_begin='2013-01-01', day_end='2021-11-17'):
    """
    Get historical stock data using yfinance
    """
    try:
        ticker = yf.Ticker(stock)
        hist = ticker.history(period='max', interval=interval, start=day_begin, end=day_end)
        hist['Returns'] = hist['Close'].pct_change()
        return hist
    except Exception as e:
        print(f"Error getting historical data for {stock}: {str(e)}")
        return pd.DataFrame()
