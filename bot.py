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

def get_fresh_proxies():
    """دریافت پروکسی‌های زنده ایرانی از یک منبع آنلاین"""
    try:
        # دریافت پروکسی‌های HTTP از ایران
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=IR&ssl=all&anonymity=all"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            proxies = [f"http://{p.strip()}" for p in r.text.split("\n") if p.strip()]
            if proxies:
                print(f"{len(proxies)} پروکسی جدید پیدا شد.")
                return proxies
    except Exception as e:
        print("خطا در دریافت پروکسی‌های آنلاین:", e)
    
    # اگر اینترنت قطع بود یا سایت جواب نداد، از لیست پیش‌فرض استفاده کن
    return [
        "http://46.209.30.11:8080", "http://45.131.4.93:80",
        "http://45.131.4.91:80", "http://81.12.28.35:3128",
    ]

def get_symbol_list(retries=10):
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
    
    proxies_to_try = get_fresh_proxies()
    
    for attempt in range(min(retries, len(proxies_to_try))):
        proxy_url = proxies_to_try[attempt]
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        try:
            print(f"تلاش {attempt+1} با پروکسی: {proxy_url}")
            r = requests.get(url, params=params, headers=HEADERS, proxies=proxies, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            items = data.get('marketwatch') or data.get('marketWatch')
            if items:
                print("موفق! لیست دریافت شد.")
                return items
        except Exception as e:
            print(f"خطا: {e}")
            continue
    return None

# ---------- اجرای اصلی ----------
state = load_state()

if state is None:
    print("اولین اجرا: دریافت offset اولیه...")
    try:
        r = requests.get(f"{BASE}/getUpdates", timeout=15)
        updates = r.json().get('result', [])
        offset = (max(u['update_id'] for u in updates) + 1) if updates else 0
    except Exception:
        offset = 0
    save_state({"offset": offset})
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
            send(chat_id, "⏳ در حال دریافت لیست نمادها (در حال تست پروکسی‌های جدید)...", MAIN_KEYBOARD)
            items = get_symbol_list()
            
            if items:
                # ارسال لیست (فقط ۱۵ نماد اول برای اینکه پیام طولانی نشود)
                lines = []
                for it in items[:15]:
                    symbol = it.get('lVal18AFC') or it.get('lval18AFC') or it.get('symbol') or it.get('insCode')
                    name = it.get('lVal30') or it.get('lval30') or it.get('name') or ''
                    lines.append(f"• {symbol} — {name}")
                
                msg_text = "📋 لیست نمادها (۱۵ مورد اول):\n\n" + "\n".join(lines)
                send(chat_id, msg_text, MAIN_KEYBOARD)
                
                # ارسال اطلاعات دیباگ برای پیدا کردن اسم فیلدها
                first_item = items[0]
                debug_msg = f"🔍 کلیدهای موجود در داده:\n{list(first_item.keys())}\n\n"
                debug_msg += f"📦 نمونه داده کامل:\n{json.dumps(first_item, ensure_ascii=False)}"
                send(chat_id, debug_msg[:4000], MAIN_KEYBOARD)
                
            else:
                send(chat_id, "❌ دریافت لیست ناموفق بود. تمام پروکسی‌ها از کار افتاده‌اند. لطفاً چند دقیقه دیگر دوباره تلاش کنید.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    save_state({"offset": offset})

except Exception as e:
    print("خطای کلی:", e)
