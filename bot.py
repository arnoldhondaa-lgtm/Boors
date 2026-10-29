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
}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

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
    proxies_list = []
    try:
        # گرفتن لیست از منبع اول
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=IR&ssl=all&anonymity=all"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            proxies_list.extend([f"http://{p.strip()}" for p in r.text.split("\n") if p.strip()])
            
        # گرفتن لیست از منبع دوم برای اطمینان بیشتر
        url2 = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        r2 = requests.get(url2, timeout=10)
        if r2.status_code == 200:
            # فقط چندتایی از این لیست برمیداریم که خیلی طولانی نشه
            proxies_list.extend([f"http://{p.strip()}" for p in r2.text.split("\n")[:100] if p.strip()])
            
    except Exception as e:
        print("خطا در دریافت پروکسی‌های آنلاین:", e)
    
    # لیست پیش‌فرض در صورتی که اینترنت قطع باشد
    if not proxies_list:
        proxies_list = [
            "http://46.209.30.11:8080", "http://45.131.4.93:80",
            "http://45.131.4.91:80", "http://81.12.28.35:3128",
        ]
        
    # مخلوط کردن لیست تا هر بار ترتیب متفاوتی تست شود
    random.shuffle(proxies_list)
    return proxies_list

def get_symbol_list(retries=15):
    url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
    params = {
        'market': 0,
        'paperTypes[0]': 1, 'paperTypes[1]': 2, 'paperTypes[2]': 3,
        'paperTypes[3]': 4, 'paperTypes[4]': 5, 'paperTypes[5]': 6,
        'paperTypes[6]': 7, 'paperTypes[7]': 8, 'paperTypes[8]': 9,
        'withBestLimits': 'false', 'hEven': 0, 'RefID': 0
    }
    
    proxies_to_try = get_fresh_proxies()
    # در نهایت یک بار هم بدون پروکسی (اتصال مستقیم) تست میکنیم
    proxies_to_try.append(None) 
    
    for attempt in range(min(retries, len(proxies_to_try))):
        proxy_url = proxies_to_try[attempt]
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        try:
            print(f"تلاش {attempt+1} با پروکسی: {proxy_url}")
            r = requests.get(url, params=params, headers=HEADERS, proxies=proxies, timeout=10)
            if r.status_code == 200:
                data = r.json()
                items = data.get('marketwatch') or data.get('marketWatch')
                if items:
                    print("موفق! لیست دریافت شد.")
                    return items
        except Exception:
            continue
            
    return None

def format_symbol_list(items, limit=30):
    if not items:
        return None
    lines = []
    for it in items[:limit]:
        symbol = it.get('lva', 'نامشخص')
        name = it.get('lvc', '')
        lines.append(f"• {symbol} — {name}")
    return f"📋 لیست نمادها (نمایش {len(lines)} از {len(items)} مورد)\n\n" + "\n".join(lines)


# ---------- اجرای اصلی ----------
state = load_state()
offset = state.get("offset", 0)
awaiting_scan = state.get("awaiting_scan", False)

if offset == 0 and not os.path.exists(STATE_FILE):
    try:
        r = requests.get(f"{BASE}/getUpdates", timeout=15)
        updates = r.json().get('result', [])
        offset = (max(u['update_id'] for u in updates) + 1) if updates else 0
    except Exception:
        pass
    save_state({"offset": offset, "awaiting_scan": False})
    exit(0)

try:
    r = requests.get(f"{BASE}/getUpdates", params={'offset': offset, 'timeout': 5}, timeout=20)
    updates = r.json().get('result', [])

    for u in updates:
        offset = u['update_id'] + 1
        msg = u.get('message')
        if not msg:
            continue
        chat_id = msg['chat']['id']
        text = msg.get('text', '').strip()

        if awaiting_scan:
            send(chat_id, f"⏳ در حال جستجوی نماد «{text}»...", MAIN_KEYBOARD)
            items = get_symbol_list()
            
            if items:
                found = None
                for it in items:
                    if it.get('lva', '').strip() == text:
                        found = it
                        break
                
                if found:
                    msg_text = f"📊 اطلاعات نماد: {found.get('lva')}\n"
                    msg_text += f"🏢 {found.get('lvc')}\n\n"
                    msg_text += f"💰 قیمت آخرین معامله: {found.get('pdv', 0):,} ریال\n"
                    msg_text += f"🔒 قیمت پایانی: {found.get('pClosing', 0):,} ریال\n"
                    msg_text += f"📉 قیمت دیروز: {found.get('py', 0):,} ریال\n"
                    msg_text += f"📈 بیشترین: {found.get('pmx', 0):,} | کمترین: {found.get('pmn', 0):,}\n"
                    msg_text += f"📦 حجم معاملات: {found.get('qtj', 0):,}"
                    send(chat_id, msg_text, MAIN_KEYBOARD)
                else:
                    send(chat_id, f"❌ نماد «{text}» پیدا نشد. دقت کن که اسم رو دقیقاً مثل لیست بنویسی.", MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ خطا در دریافت داده‌ها. احتمالاً پروکسی‌ها قطع شده‌اند. لطفاً دوباره امتحان کنید.", MAIN_KEYBOARD)
            
            awaiting_scan = False 
            continue

        if text == '/start':
            send(chat_id, "سلام 👋\nاز منوی پایین یک گزینه انتخاب کن:", MAIN_KEYBOARD)
            
        elif text == '⚙️ تنظیمات':
            send(chat_id, "بخش تنظیمات هنوز آماده نیست.", MAIN_KEYBOARD)
            
        elif text == '📊 اسکن':
            send(chat_id, "🔍 لطفاً نام نماد مورد نظر را بنویسید (مثلاً: خودرو یا شپنا):", MAIN_KEYBOARD)
            awaiting_scan = True
            
        elif text == '📋 لیست نمادها':
            send(chat_id, "⏳ در حال دریافت لیست نمادها...", MAIN_KEYBOARD)
            items = get_symbol_list()
            if items:
                msg_text = format_symbol_list(items)
                send(chat_id, msg_text, MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ دریافت لیست ناموفق بود. ممکن است لحظه‌ای قطعی شبکه باشد.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    save_state({"offset": offset, "awaiting_scan": awaiting_scan})

except Exception as e:
    print("خطای کلی:", e)
