import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # สามารถเป็น user หรือ group ID ก็ได้

def send_telegram_message(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM_BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        if response.ok:
            print(f"[Telegram] Sent to GROUP :  successfully: {response.status_code}")
        else:
            print(f"[Telegram] Failed for GROUP: {response.status_code}, {response.text}")
    except Exception as e:
        print("❌ Failed to send Telegram message:", e)
