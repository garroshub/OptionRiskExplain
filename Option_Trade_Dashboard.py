"""
@author: Garros

"""
import numpy as np
from scipy import stats as si
import streamlit as st
import pandas as pd
import YFin_API as yf
import plotly.express as px

# Options Functions
def N(x):
    return si.norm.cdf(x)
    
def callOption(S, K, T, r, q, sigma):
    d1 = (np.log(S/K) + (r - q + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma* np.sqrt(T)
    return S*np.exp(-q*T) * N(d1) - K * np.exp(-r*T)* N(d2)

def putOption(S, K, T, r, q, sigma):
    d1 = (np.log(S/K) + (r - q + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma* np.sqrt(T)
    return K*np.exp(-r*T)*N(-d2) - S*np.exp(-q*T)*N(-d1)

# Streamlit Controls
st.set_page_config(layout="wide",page_title='Options Calculator',
menu_items={
        "About": f"Options Calculator"
        f"\nApp contact: [Garros Gong](https://www.linkedin.com/in/garros-gong/)",
    })

# App Details
appDetails = """
Created by: [Garros Gong](https://www.linkedin.com/in/garros-gong/) \n
Purpose: Compare different option chains and calculate value of calls/puts with Black Scholes \n
This app has two applications:
- You can calculate the value of a call or put using the sidebar Options Calculator
- You can scrape from Yahoo Finance the options chains for a particular stock or index
"""
with st.expander("See app info"):
    st.write(appDetails)

# Options Calculator
st.sidebar.header("Options Calculator")
with st.sidebar.form(key='inputs_form'):    
    spot = st.number_input('Spot Price (S):', value=100.0, min_value=0.0)
    strike = st.number_input('Strike Price (K):', value=100.0, min_value=0.0)
    timeInterval = st.selectbox("Time interval:", ('Days','Months','Years'),index=0)
    timeToExp = st.number_input('Time to expiration in (t - {}):'.format(timeInterval), value=30, min_value=0)
    if timeInterval == 'Days':
        t = timeToExp / 365
    elif timeInterval == 'Months':
        t = timeToExp / 12
    else:
        t = timeToExp
    st.write("Years to expiry: {:.2f}".format(t))
    rf = st.number_input('Risk-Free Interest Rate (r in %):', value=5.0, min_value=0.0)
    divRate = st.number_input('Dividend Rate (q in %):', value=0.0, min_value=0.0)
    vol = st.number_input('Volatility (v in %):', value=25.0, min_value=0.0)
    submit_btn = st.form_submit_button(label='Calculate')
 
call = callOption(spot, strike, t, rf/100, divRate/100, vol/100)
put = putOption(spot, strike, t, rf/100, divRate/100, vol/100)

col1_side, col2_side= st.sidebar.columns(2)
col1_side.metric("Call Value","${:.4f}".format(call))
col2_side.metric("Put Value","${:.4f}".format(put))

if st.checkbox("Show Options Calculator Results"):
    st.header("Options Calculator")
    col1, col2= st.columns(2)
    col1.metric("Call Value","${:.4f}".format(call))
    col2.metric("Put Value","${:.4f}".format(put))

    col1_1, col2_1, col3_1 = st.columns(3)
    col1_1.metric("Spot","${:.2f}".format(spot))
    col2_1.metric("Strike","${:.2f}".format(strike))
    col3_1.metric("Time (years)","{:.2f}".format(t))
    col1_2, col2_2, col3_2 = st.columns(3)
    col1_2.metric("Risk-Free Rate","{:.2%}".format(rf/100))
    col2_2.metric("Dividend Rate:","{:.2%}".format(divRate/100))
    col3_2.metric("Volatility","{:.2%}".format(vol/100))

# Option Chain 
st.header("Option Chain")

colInputs, colOutputs  = st.columns([1,1])
with colInputs:
    ticker = st.text_input("Ticker:","SPY")
    expDF = yf.grabExpDates(ticker)
    if not expDF.empty:
        link = "https://query2.finance.yahoo.com/v7/finance/options/{}?date=".format(ticker)
        expDF = expDF.copy()  # Create a copy to avoid SettingWithCopyWarning
        expDF['Link'] = expDF['Unix Date'].apply(lambda x: link + str(x))
        allDates = list(expDF.index.strftime('%Y-%m-%d'))
        expDate = st.selectbox("Pick expiry date:", allDates, index=0)
    else:
        st.error(f"No option data available for {ticker}")
        expDate = None

    if expDate is not None:
        df_calls = yf.optionChain(ticker=ticker, date=expDate, calls_puts = "calls")
        df_puts = yf.optionChain(ticker=ticker, date=expDate, calls_puts = "puts")

        df_calls['Type'] = 'Call'
        df_puts['Type'] = 'Put'

        df_all = pd.concat([df_calls, df_puts])
        price = yf.fnYFinJSON(ticker, "regularMarketPrice")
        ltmDivYield = yf.fnYFinJSON(ticker,'trailingAnnualDividendYield')
        st.metric("{} Last Price".format(ticker),"{:.2f}".format(price))
        st.metric("{} LTM Dividend Yield".format(ticker),"{:.2%}".format(ltmDivYield))

        url = "https://finance.yahoo.com/quote/{}/options?p={}&date={}"
        unixTS = pd.Timestamp('{} 00:00:00'.format(expDate)).timestamp()
        st.write("Yahoo Finance Link: " + url.format(ticker, ticker, int(unixTS)))

chartTitle = "{} Option Prices at various Strikes (Maturity: {})".format(ticker, expDate if expDate else "N/A")

with colOutputs:
    if expDate is not None and not df_all.empty:
        metricPlot = st.selectbox("Pick a metric to plot:", ('lastPrice','bid','ask','impliedVolatility'), index=0)
        titleMap = {'lastPrice':'Last Prices',
                    'bid':'Bid Prices',
                    'ask':'Ask Prices',
                    'impliedVolatility':'Implied Volatility'
                    }
        chartTitleMain = "{} Option {} at various Strikes (Maturity: {})".format(ticker, titleMap[metricPlot], expDate)
        figAll = px.scatter(df_all, x='strike', y=metricPlot, color='Type', title=chartTitleMain)
        figAll.add_vline(x=price, annotation_text="Current Price: ${:.2f}".format(price))
        st.plotly_chart(figAll)

if expDate is not None:
    #fig = px.scatter(df, x='strike', y='lastPrice', title="Last Price at various Strikes for {:%Y-%m-%d}".format(expDate))
    if not df_calls.empty:
        figCalls = px.scatter(df_calls, x='strike', y=['lastPrice','bid','ask'], title=chartTitle)
        figCalls.add_vline(x=price, annotation_text="Current Price: ${:.2f}".format(price))

    if not df_puts.empty:
        figPuts = px.scatter(df_puts, x='strike', y=['lastPrice','bid','ask'], title=chartTitle)
        figPuts.add_vline(x=price, annotation_text="Current Price: ${:.2f}".format(price))

    colCalls, colPuts  = st.columns([1,1])
    with colCalls:
        st.header("Calls")
        if not df_calls.empty:
            st.plotly_chart(figCalls)
        else:
            st.warning("No call options data available")

    with colPuts:
        st.header("Puts")
        if not df_puts.empty:
            st.plotly_chart(figPuts)
        else:
            st.warning("No put options data available")

    if not df_calls.empty:
        st.subheader("Calls Option Chain")
        st.write(df_calls)

    if not df_puts.empty:
        st.subheader("Puts Option Chain")
        st.write(df_puts)

if not expDF.empty:
    st.write("Expiry Dates")
    st.dataframe(expDF)
