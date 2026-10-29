import requests
import json
import os
import time
import random

# ===== تنظیمات خودت =====
TOKEN = "8956012435:AAG8yJA3E6PouLB0hmmw7rpXzAX_flnvqRc"
# ========================

BASE = f"https://api.telegram.org/bot{TOKEN}"
STATE_FILE = "state.json"

IRAN_PROXIES = [
    "http://46.209.30.11:8080",
    "http://45.131.4.93:80",
    "http://45.131.4.91:80",
    "http://81.12.28.35:3128",
    "http://185.88.177.40:80",
    "http://46.245.69.173:8080",
    "http://45.131.4.67:80",
    "http://185.95.152.38:8080",
    "http://31.14.124.45:8080",
    "http://195.181.40.34:8080",
    "http://185.118.153.110:8080",
    "http://79.175.188.203:443",
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send(chat_id, text, keyboard=None):
    payload = {'chat_id': chat_id, 'text': text}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        requests.post(f"{BASE}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print("خطا در ارسال:", e)

MAIN_KEYBOARD = {
    'keyboard': [
        [{'text': '📊 اسکن'}, {'text': '📋 لیست نمادها'}],
        [{'text': '⚙️ تنظیمات'}]
    ],
    'resize_keyboard': True,
    'is_persistent': True
}

def get_symbol_list(retries=5):
    url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
    params = {
        'market': 0,
        'paperTypes[0]': 1, 'paperTypes[1]': 2, 'paperTypes[2]': 3,
        'paperTypes[3]': 4, 'paperTypes[4]': 5, 'paperTypes[5]': 6,
        'paperTypes[6]': 7, 'paperTypes[7]': 8, 'paperTypes[8]': 9,
        'withBestLimits': 'false',
        'hEven': 0,
        'RefID': 0
    }
    proxies_to_try = IRAN_PROXIES if IRAN_PROXIES else [None]
    
    for attempt in range(retries):
        proxy_url = random.choice(proxies_to_try)
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        try:
            r = requests.get(url, params=params, headers=HEADERS, proxies=proxies, timeout=20)
            if r.status_code != 200:
                continue
            data = r.json()
            items = data.get('marketwatch') or data.get('marketWatch')
            if items:
                return items
        except Exception as e:
            print(f"تلاش {attempt+1} با پروکسی {proxy_url}: {e}")
            time.sleep(1)
    return None

def format_symbol_list(items, limit=40):
    if not items:
        return None
    lines = []
    for it in items[:limit]:
        # تلاش برای پیدا کردن اسم نماد با کلیدهای مختلف
        symbol = it.get('lVal18AFC') or it.get('lval18AFC') or it.get('symbol')
        name = it.get('lVal30') or it.get('lval30') or it.get('name')
        
        # اگر اسم پیدا نشد، از کد استفاده کن
        if not symbol:
            symbol = it.get('insCode', 'نامشخص')
            
        if name:
            lines.append(f"• {symbol}  —  {name}")
        else:
            lines.append(f"• {symbol}")
            
    if not lines:
        return None
    header = f"📋 لیست نمادها (نمایش {len(lines)} از {len(items)} مورد)\n\n"
    footer = "\n\n(نمایش محدود شده است؛ در مراحل بعد جستجو اضافه می‌شود.)"
    return header + "\n".join(lines) + footer


# ---------- اجرای اصلی ----------
state = load_state()

if state is None:
    print("اولین اجرا: دریافت offset اولیه...")
    try:
        r = requests.get(f"{BASE}/getUpdates", timeout=15)
        updates = r.json().get('result', [])
        offset = (max(u['update_id'] for u in updates) + 1) if updates else 0
    except Exception as e:
        print("خطا:", e)
        offset = 0
    save_state({"offset": offset})
    print("offset اولیه ذخیره شد:", offset)
    exit(0)

offset = state.get("offset", 0)

try:
    r = requests.get(f"{BASE}/getUpdates", params={'offset': offset, 'timeout': 5}, timeout=20)
    updates = r.json().get('result', [])

    for u in updates:
        offset = u['update_id'] + 1
        msg = u.get('message')
        if not msg:
            continue
        chat_id = msg['chat']['id']
        text = msg.get('text', '')

        if text == '/start':
            send(chat_id, "سلام 👋\nاز منوی پایین یک گزینه انتخاب کن:", MAIN_KEYBOARD)
            
        elif text == '⚙️ تنظیمات':
            send(chat_id, "بخش تنظیمات هنوز آماده نیست.", MAIN_KEYBOARD)
            
        elif text == '📊 اسکن':
            send(chat_id, "بخش اسکن هنوز آماده نیست.", MAIN_KEYBOARD)
            
        elif text == '📋 لیست نمادها':
            send(chat_id, "⏳ در حال دریافت لیست نمادها...", MAIN_KEYBOARD)
            items = get_symbol_list()
            if items:
                msg_text = format_symbol_list(items)
                if msg_text:
                    send(chat_id, msg_text, MAIN_KEYBOARD)
                    # ارسال یک نمونه از داده خام برای دیباگ (فقط برای بررسی)
                    debug_sample = str(items[0])[:300]
                    send(chat_id, f"🔍 نمونه داده خام:\n{debug_sample}", MAIN_KEYBOARD)
                else:
                    send(chat_id, "لیست دریافت شد اما نام نمادها استخراج نشد.", MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ دریافت لیست ناموفق بود. لطفاً دوباره تلاش کنید.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    save_state({"offset": offset})

except Exception as e:
    print("خطای کلی:", e)
