import time
import pandas as pd
import numpy as np
import ccxt
import logging
import asyncio
from ta import momentum, trend, volatility
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    filename='trading_bot.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TradingBot:
    def __init__(self, symbols, initial_capital=1000, stop_loss_pct=2, take_profit_pct=5):
        self.symbols = symbols
        # Using Binance as a more widely supported exchange
        self.exchange = ccxt.binance({
            'apiKey': os.getenv('EXCHANGE_API_KEY'),
            'secret': os.getenv('EXCHANGE_API_SECRET'),
            'options': {
                'defaultType': 'future'  # For futures trading
            }
        })

        try:
            self.exchange.load_markets()
            logging.info("Aevo Exchange loaded successfully.")
        except ccxt.NetworkError as e:
            logging.error(f"Network error connecting to Aevo: {e}")
            raise
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error loading markets from Aevo: {e}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading markets: {e}")
            raise

        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.data = pd.DataFrame()
        self.positions = {}

    def get_candles(self, symbol, timeframe='1m', limit=100):
        try:
            market = self.exchange.market(symbol)
            aevo_symbol = market['id']
            
            timeframe_mapping = {
                '1m': '1m', '5m': '5m', '15m': '15m',
                '30m': '30m', '1h': '1h', '4h': '4h', '1d': '1d'
            }

            if timeframe not in timeframe_mapping:
                logging.error(f"Invalid timeframe {timeframe}")
                return None

            candles = self.exchange.fetch_ohlcv(
                symbol=aevo_symbol,
                timeframe=timeframe_mapping[timeframe],
                limit=limit
            )

            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except Exception as e:
            logging.error(f"Error fetching candles: {e}")
            return None

    def calculate_indicators(self, df):
        # Simple Moving Averages
        df['SMA_5'] = trend.SMAIndicator(df['close'], window=5).sma_indicator()
        df['SMA_20'] = trend.SMAIndicator(df['close'], window=20).sma_indicator()
        
        # RSI
        df['RSI'] = momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # MACD
        macd = trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        
        # Bollinger Bands
        bb = volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Middle'] = bb.bollinger_mavg()
        df['BB_Lower'] = bb.bollinger_lband()
        
        return df

    def generate_signal(self, df):
        # Initialize signal as neutral
        signal = 0
        
        # SMA Crossover
        sma_signal = 1 if df['SMA_5'].iloc[-1] > df['SMA_20'].iloc[-1] else -1
        
        # RSI Conditions
        rsi = df['RSI'].iloc[-1]
        rsi_signal = 0
        if rsi > 70:
            rsi_signal = -1  # Overbought
        elif rsi < 30:
            rsi_signal = 1   # Oversold
            
        # MACD Crossover
        macd_signal = 1 if df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1] else -1
        
        # Bollinger Bands
        price = df['close'].iloc[-1]
        bb_signal = 0
        if price > df['BB_Upper'].iloc[-1]:
            bb_signal = -1  # Price too high
        elif price < df['BB_Lower'].iloc[-1]:
            bb_signal = 1   # Price too low
            
        # Combine signals (weighted)
        total_signal = (sma_signal * 0.3 + 
                       rsi_signal * 0.2 + 
                       macd_signal * 0.3 + 
                       bb_signal * 0.2)
        
        if total_signal > 0.5:
            signal = 1  # Strong buy
        elif total_signal < -0.5:
            signal = -1 # Strong sell
            
        return signal

    async def execute_trade(self, symbol, signal, price):
        try:
            # Calculate position size (5% of capital)
            position_size = self.current_capital * 0.05 / price
            
            if signal == 1:  # Buy signal
                # order = self.exchange.create_market_buy_order(
                #     symbol=symbol,
                #     amount=position_size
                # )
                logging.info(f"BUY {position_size} {symbol} at {price}")
                self.positions[symbol] = {
                    'entry_price': price,
                    'size': position_size,
                    'stop_loss': price * (1 - self.stop_loss_pct/100),
                    'take_profit': price * (1 + self.take_profit_pct/100)
                }
                self.current_capital -= position_size * price
                
            elif signal == -1:  # Sell signal
                if symbol in self.positions:
                    position = self.positions[symbol]
                    # order = self.exchange.create_market_sell_order(
                    #     symbol=symbol,
                    #     amount=position['size']
                    # )
                    profit = (price - position['entry_price']) * position['size']
                    logging.info(f"SELL {position['size']} {symbol} at {price} (Profit: {profit})")
                    self.current_capital += position['size'] * price
                    del self.positions[symbol]
                    
        except Exception as e:
            logging.error(f"Trade execution error: {e}")

    async def check_risk_management(self, symbol, current_price):
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Check stop loss
            if current_price <= position['stop_loss']:
                logging.info(f"Stop loss triggered for {symbol} at {current_price}")
                await self.execute_trade(symbol, -1, current_price)
                
            # Check take profit
            elif current_price >= position['take_profit']:
                logging.info(f"Take profit triggered for {symbol} at {current_price}")
                await self.execute_trade(symbol, -1, current_price)

    async def execute(self):
        for symbol in self.symbols:
            try:
                # Get market data
                df = self.get_candles(symbol, timeframe='5m', limit=100)
                if df is None or df.empty:
                    continue
                    
                # Calculate indicators
                df = self.calculate_indicators(df)
                
                # Generate trading signal
                signal = self.generate_signal(df)
                current_price = df['close'].iloc[-1]
                
                # Check risk management
                await self.check_risk_management(symbol, current_price)
                
                # Execute trade based on signal
                if signal != 0:
                    await self.execute_trade(symbol, signal, current_price)
                    
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")

async def main():
    symbols = ['ETH/USDC']  # Example symbols
    bot = TradingBot(
        symbols,
        initial_capital=1000,
        stop_loss_pct=2,    # 2% stop loss
        take_profit_pct=5   # 5% take profit
    )

    while True:
        try:
            await bot.execute()
            logging.info(f"Current capital: {bot.current_capital}")
            await asyncio.sleep(60)  # Run every minute
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())

