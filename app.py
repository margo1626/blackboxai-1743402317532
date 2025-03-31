from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from bot3 import TradingBot
import threading
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize trading bot
symbols = ['ETH/USDT']  # Binance uses USDT pairs for ETH trading
bot = TradingBot(
    symbols,
    initial_capital=1000,
    stop_loss_pct=2,
    take_profit_pct=5
)

# Background thread for running the bot
bot_thread = None
bot_running = False

def run_bot():
    global bot_running
    bot_running = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.execute())

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    status = {
        'current_capital': bot.current_capital,
        'positions': bot.positions,
        'symbols': bot.symbols,
        'stop_loss_pct': bot.stop_loss_pct,
        'take_profit_pct': bot.take_profit_pct,
        'bot_running': bot_running
    }
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_thread, bot_running
    if not bot_running:
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        return jsonify({'status': 'Bot started'})
    return jsonify({'status': 'Bot already running'})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_running
    bot_running = False
    return jsonify({'status': 'Bot stopped'})

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    bot.stop_loss_pct = data.get('stop_loss_pct', bot.stop_loss_pct)
    bot.take_profit_pct = data.get('take_profit_pct', bot.take_profit_pct)
    return jsonify({'status': 'Settings updated'})

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    socketio.emit('status_update', {
        'current_capital': bot.current_capital,
        'positions': bot.positions
    })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
