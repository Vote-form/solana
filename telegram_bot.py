import os
import time
import logging
import requests
import base58
import firebase_admin
import json
import threading
from firebase_admin import credentials, initialize_app, db
from dotenv import load_dotenv
from solana.rpc.api import Client
from solders.keypair import Keypair
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackContext
import tweepy

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
PRIVATE_KEY = os.getenv("SOL_PRIVATE_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")  # CoinMarketCap API Key
SAFETY_THRESHOLD = 85  # Minimum safety score for trading

# Twitter API credentials
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET_KEY = os.getenv("TWITTER_API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Memecoin tickers to scan
MEMECOIN_TICKERS = ["$DOGE", "$SHIB", "$PEPE", "$SAFEMOON", "$CYN", "$HOGE", "$FLOKI", "$KISHU"]

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Solana client
client = Client(SOLANA_RPC_URL)
if not PRIVATE_KEY:
    raise ValueError("Missing private key! Ensure SOL_PRIVATE_KEY is set in the environment.")
wallet = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY))

# 🔹 Firebase Initialization (Loads JSON from Local File)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_CREDENTIALS_PATH = os.path.join(BASE_DIR, "solana-fdc09-firebase-adminsdk-fbsvc-7acdcf0c45.json")

# Ensure the file exists before loading
if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
    raise FileNotFoundError(f"❌ Firebase credentials not found at {FIREBASE_CREDENTIALS_PATH}")

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://solana-fdc09-default-rtdb.firebaseio.com'
})
logging.info("✅ Firebase Initialized Successfully!")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Initialize Twitter API client
def initialize_twitter_api():
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api

twitter_api = initialize_twitter_api()

# Send Telegram message
def send_telegram_message(message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

# Fetch Solana balance
async def fetch_balance(update: Update, context: CallbackContext):
    try:
        balance = client.get_balance(wallet.public_key)['result']['value'] / 1e9  # Convert lamports to SOL
        await update.message.reply_text(f"💰 Current Balance: {balance:.2f} SOL")
    except Exception as e:
        logging.error(f"Failed to fetch balance: {e}")
        await update.message.reply_text("⚠️ Error fetching balance.")

# Monitor tokens
def monitor_tokens():
    while True:
        send_telegram_message("📡 Monitoring tokens for trading opportunities...")
        time.sleep(30)  # Placeholder monitoring loop

# Start trading
async def start_trading(update: Update, context: CallbackContext):
    await update.message.reply_text("🚀 Trading started!")
    threading.Thread(target=monitor_tokens, daemon=True).start()

# Stop trading
async def stop_trading(update: Update, context: CallbackContext):
    await update.message.reply_text("⛔ Trading stopped!")

# Fetch total profit
async def fetch_profit(update: Update, context: CallbackContext):
    trades = db.reference("/trades").get()
    total_profit = sum(trade.get("profit", 0) for trade in trades.values()) if trades else 0
    await update.message.reply_text(f"📈 Total Profit: {total_profit:.2f} SOL")

# Fetch CoinMarketCap token prices
def fetch_cmc_prices():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json'}
    params = {'start': '1', 'limit': '50', 'convert': 'USD'}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return {coin['symbol']: coin['quote']['USD']['price'] for coin in data['data']}
    except requests.RequestException as e:
        logging.error(f"API Error: {e}")
        send_telegram_message(f"⚠️ API Failure: CoinMarketCap is down. Error: {str(e)}")
        return {}

# Main function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start_trading", start_trading))
    application.add_handler(CommandHandler("stop_trading", stop_trading))
    application.add_handler(CommandHandler("balance", fetch_balance))
    application.add_handler(CommandHandler("profit", fetch_profit))

    # Start polling
    application.run_polling()

if __name__ == "__main__":
    main()
