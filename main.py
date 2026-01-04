#region imports
from AlgorithmImports import *
from QuantConnect import Resolution
import numpy as np
import pandas as pd
from collections import deque
import pickle
#endregion

"""
Project: In & Out Strategy (Refactored)
Original Author: Peter Guenther
Refactored for: GitHub / Personal Use
Description: Switches between Aggressive Equities and Safe Havens based on market stress signals.
"""

class InOut(QCAlgorithm):

    def Initialize(self):
            # 1. CONFIGURATION SECTION ------------------------------------------------
            # -------------------------------------------------------------------------
            # Set the dates to test. Change StartDate to 2022, 1, 1 to test the "fail" case.
            self.SetStartDate(2008, 1, 1) 
            self.SetCash(100000) 
            
            # ASSETS TO TRADE
            # The "Bull" asset (what we own when market is safe)
            self.bull_ticker = "QQQ" 
            
            # The "Bear" asset (what we own when market is dangerous)
            self.bear_ticker = "TLT" 
            
            # -------------------------------------------------------------------------
            # END CONFIGURATION
            # -------------------------------------------------------------------------
            
            # REMOVED: self.SetSettings(...) <- This line was causing the error.
            
            res = Resolution.Minute
            
            # Initialize Holdings Dictionaries
            self.HLD_OUT = {self.AddEquity(self.bear_ticker, res).Symbol: 1}
            self.HLD_IN = {self.AddEquity(self.bull_ticker, res).Symbol: 1}
            
            # Parameters
            self.out_mom_lb = 40  # Lookback for momentum on the Out asset
            
            # --- SIGNAL ASSETS (DO NOT CHANGE THESE) ---
            # The algorithm's "magic numbers" are tuned to THESE specific tickers.
            self.MRKT = self.AddEquity('QQQ', res).Symbol   # Market Proxy
            self.PRDC = self.AddEquity('XLI', res).Symbol   # Industrials (Production)
            self.METL = self.AddEquity('DBB', res).Symbol   # Base Metals (Input Costs)
            self.NRES = self.AddEquity('IGE', res).Symbol   # Natural Resources
            self.DEBT = self.AddEquity('SHY', res).Symbol   # Short Term Treasuries (Cost of Debt)
            self.USDX = self.AddEquity('UUP', res).Symbol   # US Dollar (Safe Haven)
            self.GOLD = self.AddEquity('GLD', res).Symbol   # Gold
            self.SLVA = self.AddEquity('SLV', res).Symbol   # Silver
            self.UTIL = self.AddEquity('XLU', res).Symbol   # Utilities
            self.INDU = self.PRDC                           # Comparison pair

            self.SIGNALS = [self.PRDC, self.METL, self.NRES, self.USDX, self.DEBT, self.MRKT]
            self.FORPAIRS = [self.GOLD, self.SLVA, self.UTIL, self.INDU]
            self.pairlist = ['G_S', 'U_I']

            # Initialize internal variables
            self.lookback, self.shift_vars, self.stat_alpha, self.ema_f = [252*5, [11, 60, 45], 5, 2/(1+50)]
            
            # FIX: Ensure portf_val initializes correctly with current cash if portfolio value is 0
            current_val = self.Portfolio.TotalPortfolioValue if self.Portfolio.TotalPortfolioValue > 0 else self.cap
            self.be_in, self.portf_val, self.signal_dens = [[1], [current_val], deque([0, 0, 0, 0, 0], maxlen = 100)]
            
            # Schedule the check to run 2 hours (120 min) after market open
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen('QQQ', 120), self.inout_check)
            
            # Charts setup
            self.SPY = self.AddEquity('SPY', res).Symbol
            self.QQQ = self.MRKT
            
            # Data Consolidation
            symbols = list(set(self.SIGNALS + [self.MRKT] + self.FORPAIRS + list(self.HLD_OUT.keys()) + list(self.HLD_IN.keys()) + [self.SPY] + [self.QQQ]))
            for symbol in symbols:
                self.consolidator = TradeBarConsolidator(timedelta(days=1))
                self.consolidator.DataConsolidated += self.consolidation_handler
                self.SubscriptionManager.AddConsolidator(symbol, self.consolidator)
            
            # Warm Up
            self.history = self.History(symbols, self.lookback, Resolution.Daily)
            if self.history.empty or 'close' not in self.history.columns:
                return
            self.history = self.history['close'].unstack(level=0).dropna()
            self.update_history_shift()
            
            # Benchmarks for charting
            self.benchmarks = [self.history[self.SPY].iloc[-2], self.history[self.QQQ].iloc[-2]]    
        
    def consolidation_handler(self, sender, consolidated):
        """Updates history every day with the new closing price"""
        self.history.loc[consolidated.EndTime, consolidated.Symbol] = consolidated.Close
        self.history = self.history.iloc[-self.lookback:]
        self.update_history_shift()
        
    def update_history_shift(self):
        """Calculates the shifted moving averages used for signal detection"""
        self.history_shift = self.history.rolling(self.shift_vars[0], center=True).mean().shift(self.shift_vars[1])

    def inout_check(self):
        """The Main Logic Loop"""
        if self.history.empty: return

        # Live Mode Persistence (Reloads memory if the bot restarts)
        if self.LiveMode and sum(list(self.signal_dens))==0 and self.ObjectStore.ContainsKey('OS_signal_dens'):
            OS = self.ObjectStore.ReadBytes('OS_signal_dens')
            OS = pickle.loads(bytearray(OS))
            self.signal_dens = deque(OS, maxlen = 100)
    
        # 1. Calculate Returns
        returns_sample = (self.history / self.history_shift - 1)
        
        # 2. Reverse Code Logic (Flip signs for safe havens)
        returns_sample[self.USDX] = returns_sample[self.USDX] * (-1)
        returns_sample['G_S'] = -(returns_sample[self.GOLD] - returns_sample[self.SLVA])
        returns_sample['U_I'] = -(returns_sample[self.UTIL] - returns_sample[self.INDU])

        # 3. Detect Extreme Observations (Percentile check)
        extreme_b = returns_sample.iloc[-1] < np.nanpercentile(returns_sample, self.stat_alpha, axis=0)
        
        # 4. Filter False Positives
        abovemedian = returns_sample.iloc[-1] > np.nanmedian(returns_sample, axis=0)
        extreme_b.loc[self.DEBT] = np.where((extreme_b.loc[self.DEBT].any()) & (abovemedian[[self.METL, self.NRES]].any()), False, extreme_b.loc[self.DEBT])
        
        # 5. Calculate Signal Density
        cur_signal_dens = extreme_b[self.SIGNALS + self.pairlist].sum() / len(self.SIGNALS + self.pairlist)
        add_dens = np.array((1-self.ema_f) * self.signal_dens[-1] + self.ema_f * cur_signal_dens)
        self.signal_dens.append(add_dens)
        
        # 6. Decide: IN or OUT?
        # If stress is rising -> OUT
        if self.signal_dens[-1] > self.signal_dens[-2]:
            self.be_in.append(0)
        # If stress is lower than recent history -> IN
        if self.signal_dens[-1] < min(list(self.signal_dens)[-(self.shift_vars[2]):-2]):
            self.be_in.append(1)

        # 7. Execute Trades
        if not self.be_in[-1]:
            # MARKET IS DANGEROUS -> Switch to Out Asset
            self.out_mom_sel()
            self.trade({**dict.fromkeys(self.HLD_IN, 0), **self.HLD_OUT})
        if self.be_in[-1]:
            # MARKET IS SAFE -> Switch to In Asset
            self.trade({**self.HLD_IN, **dict.fromkeys(self.HLD_OUT, 0)})

        self.charts(extreme_b)
        
        if self.LiveMode: self.SaveData()
        
    def trade(self, weight_by_sec):
        # Order Execution Logic (Sells before Buys to free up cash)
        hold_wt = {k: (self.Portfolio[k].Quantity*self.Portfolio[k].Price)/self.Portfolio.TotalPortfolioValue for k in self.Portfolio.Keys}
        order_wt = {k: weight_by_sec[k] - hold_wt.get(k, 0) for k in weight_by_sec}
        weight_by_sec = {k: weight_by_sec[k] for k in dict(sorted(order_wt.items(), key=lambda item: item[1]))}
        
        for sec, weight in weight_by_sec.items(): 
            if not self.CurrentSlice.ContainsKey(sec) or self.CurrentSlice[sec] is None:
                continue
            cond1 = (weight==0) and (self.Portfolio[sec].IsLong or self.Portfolio[sec].IsShort)
            cond2 = (weight>0 or weight<0) and not self.Portfolio[sec].Invested
            if cond1 or cond2:
                self.SetHoldings(sec, weight)
                
    def out_mom_sel(self):
        """Logic to decide if we should hold the Out Asset or just sit in Cash"""
        get_list = []
        if self.history.empty: return
            
        for out_key in list(self.HLD_OUT.keys()):
            if out_key in self.history: get_list.append(out_key)

        # Check momentum of the Out Asset
        rets = (self.history[get_list].iloc[-1] / self.history[get_list].iloc[-self.out_mom_lb] - 1).sort_values(ascending = False)
        
        for out_sec in self.HLD_OUT.keys():
            if (out_sec not in get_list) or (out_sec not in rets): 
                self.HLD_OUT[out_sec] = 0
                continue
            if out_sec!=rets.index[0]:
                self.HLD_OUT[out_sec] = 0
            else:
                # If TLT is going up, buy it. If TLT is crashing too, go to CASH (0.0).
                if rets.iloc[0] > 0:
                    self.HLD_OUT[out_sec] = 1
                else:
                    self.HLD_OUT[out_sec] = 0 # 0 means 100% Cash

    def charts(self, extreme_b):
        # Plotting Logic
        spy_perf = self.history[self.SPY].iloc[-1] / self.benchmarks[0] * self.Portfolio.TotalPortfolioValue
        qqq_perf = self.history[self.QQQ].iloc[-1] / self.benchmarks[1] * self.Portfolio.TotalPortfolioValue
        self.Plot('Strategy Equity', 'SPY', spy_perf)
        self.Plot('Strategy Equity', 'QQQ', qqq_perf)
        self.Plot("In Out", "in_market", self.be_in[-1])
        self.Plot("In Out", "signal_dens", self.signal_dens[-1])
        
    def SaveData(self):
        self.ObjectStore.SaveBytes('OS_signal_dens', pickle.dumps(self.signal_dens))