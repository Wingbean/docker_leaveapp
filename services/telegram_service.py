import os, time
import requests
from typing import Optional

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
MAX_LEN = 4096

#############
#----NEW----#
#############

_session = requests.Session()  # reuse TCP

def _send_once(text: str, *, disable_notification: bool = False,
               reply_to_message_id: Optional[int] = None, timeout: float = 10.0) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN/CHAT_ID is missing")
        return False

    url = f"{API_BASE}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": disable_notification,
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        r = _session.post(url, data=payload, timeout=timeout)
        if r.status_code == 429:
            # rate limit → caller จะจัดการ sleep เอง
            return False
        if r.ok:
            return True
        print(f"[Telegram] {r.status_code} {r.text}")
        return False
    except Exception as e:
        print("❌ Telegram exception:", e)
        return False

def send_telegram_message(message: str, *,
                          disable_notification: bool = False,
                          reply_to_message_id: Optional[int] = None,
                          split_long: bool = True,
                          max_retries: int = 3) -> bool:
    """ส่งข้อความ HTML; คืน True ถ้าสำเร็จ (ถ้า split_long=True และยาว จะส่งหลายชิ้นให้ครบ)"""
    if not message:
        return True  # ไม่ต้องส่งอะไร

    texts = []
    if split_long and len(message) > MAX_LEN:
        # แบ่งตามบรรทัดเพื่อให้อ่านง่าย
        buf = []
        cur = 0
        for line in message.splitlines(keepends=True):
            if cur + len(line) > MAX_LEN:
                texts.append("".join(buf))
                buf, cur = [line], len(line)
            else:
                buf.append(line); cur += len(line)
        if buf:
            texts.append("".join(buf))
    else:
        texts = [message if len(message) <= MAX_LEN else (message[:MAX_LEN-3] + "...")]

    # ส่งทีละชิ้น พร้อม retry 429 แบบสุภาพ
    for part in texts:
        for attempt in range(1, max_retries + 1):
            ok = _send_once(part, disable_notification=disable_notification,
                            reply_to_message_id=reply_to_message_id)
            if ok:
                break
            # ถ้าโดน 429, Telegram จะให้ header Retry-After; เราเดาแบบ backoff ขั้นต่ำ
            backoff = min(5, attempt * 2)
            time.sleep(backoff)
        else:
            print("[Telegram] giving up after retries")
            return False
    return True


#---OLD---#
def send_telegram_messageOLD(message: str):
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