import requests
import json
import os
import time
import random
from urllib.parse import quote, urlencode

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

# ====== موتور دریافت داده با اولویت‌دهی هوشمند ======
def fetch_json(url, params=None):
    # ۱. اولویت اول: استفاده از r.jina.ai (پروکسی پایدار برای APIهای خارجی)
    try:
        full_url = url
        if params:
            full_url += "?" + urlencode(params)
        jina_url = f"https://r.jina.ai/{full_url}"
        r = requests.get(jina_url, headers={'Accept': 'application/json'}, timeout=15)
        if r.status_code == 200:
            # jina ممکن است متن اضافی برگرداند، سعی میکنیم JSON را استخراج کنیم
            text = r.text.strip()
            if text.startswith('{') or text.startswith('['):
                return json.loads(text)
            # اگر JSON نبود، شاید داخل متن باشد
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
    except Exception as e:
        print("Jina failed:", e)

    # ۲. اولویت دوم: اتصال مستقیم (شاید IP گیت‌هاب در آن لحظه مسدود نباشد)
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Direct failed:", e)

    # ۳. اولویت سوم: پروکسی‌های CORS
    full_url = url
    if params:
        full_url += "?" + urlencode(params)
    quoted_url = quote(full_url, safe='')
    cors_proxies = [
        f"https://api.allorigins.win/raw?url={quoted_url}",
        f"https://api.codetabs.com/v1/proxy?quest={quoted_url}"
    ]
    for proxy_url in cors_proxies:
        try:
            r = requests.get(proxy_url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    # ۴. اولویت چهارم: پروکسی‌های ایرانی
    try:
        proxy_api = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=IR&ssl=all&anonymity=all"
        r = requests.get(proxy_api, timeout=5)
        if r.status_code == 200:
            proxies = [f"http://{p.strip()}" for p in r.text.split("\n") if p.strip()]
            random.shuffle(proxies)
            for p in proxies[:3]: 
                try:
                    r_data = requests.get(url, params=params, headers=HEADERS, 
                                          proxies={"http": p, "https": p}, timeout=8)
                    if r_data.status_code == 200:
                        return r_data.json()
                except Exception:
                    continue
    except Exception:
        pass

    return None

def search_and_get_price(query):
    # ۱. جستجوی نماد
    search_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(query)}"
    search_data = fetch_json(search_url)
    
    if not search_data or 'instrumentSearch' not in search_data:
        return None, "سرور بورس پاسخ نداد یا نماد پیدا نشد."
    
    items = search_data['instrumentSearch']
    if not items:
        return None, f"نمادی با عبارت «{query}» یافت نشد."
    
    # پیدا کردن دقیق‌ترین تطابق
    exact_match = None
    for item in items:
        # گاهی اوقات فاصله یا کاراکترهای اضافی وجود دارد، تمیز میکنیم
        symbol_db = item.get('lVal18AFC', '').strip().replace('ي', 'ی').replace('ك', 'ک')
        symbol_user = query.strip().replace('ي', 'ی').replace('ك', 'ک')
        
        if symbol_db == symbol_user:
            exact_match = item
            break
            
    if not exact_match:
        # اگر دقیق نبود، اولین نتیجه رو بردار (بهترین تطابق تقریبی)
        exact_match = items[0]
        
    ins_code = exact_match.get('insCode')
    
    # ۲. دریافت قیمت لحظه‌ای
    price_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
    price_data = fetch_json(price_url)
    
    if not price_data or 'closingPriceInfo' not in price_data:
        return None, "اطلاعات قیمت برای این نماد در دسترس نیست."
        
    return (exact_match, price_data['closingPriceInfo']), None

# ========== اجرای اصلی ==========
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
            
            result, error = search_and_get_price(text)
            
            if result:
                info, price = result
                msg_text = f"📊 نماد: {info.get('lVal18AFC')}\n"
                msg_text += f"🏢 {info.get('lVal30')}\n\n"
                msg_text += f"💰 آخرین معامله: {price.get('pDrCotVal', 0):,} ریال\n"
                msg_text += f"🔒 قیمت پایانی: {price.get('pClosing', 0):,} ریال\n"
                msg_text += f"📈 بیشترین: {price.get('priceMax', 0):,}\n"
                msg_text += f"📉 کمترین: {price.get('priceMin', 0):,}\n"
                msg_text += f"📦 حجم معاملات: {price.get('qTotTran5J', 0):,}"
                send(chat_id, msg_text, MAIN_KEYBOARD)
            else:
                # اگر نماد پیدا نشد، چند پیشنهاد از نتایج جستجو را نشان بده (اگر وجود داشته باشد)
                search_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(text)}"
                search_data = fetch_json(search_url)
                suggestions = ""
                if search_data and search_data.get('instrumentSearch'):
                    sugg_items = search_data['instrumentSearch'][:5]
                    sugg_list = [f"• {s.get('lVal18AFC')}" for s in sugg_items]
                    suggestions = "\n\n💡 نمادهای مشابه:\n" + "\n".join(sugg_list)
                
                send(chat_id, f"❌ {error}{suggestions}", MAIN_KEYBOARD)
            
            awaiting_scan = False 
            continue

        if text == '/start':
            send(chat_id, "سلام 👋\nاز منوی پایین یک گزینه انتخاب کن:", MAIN_KEYBOARD)
            
        elif text == '⚙️ تنظیمات':
            send(chat_id, "بخش تنظیمات هنوز آماده نیست.", MAIN_KEYBOARD)
            
        elif text == '📊 اسکن':
            send(chat_id, "🔍 لطفاً نام نماد مورد نظر را بنویسید (مثلاً: خودرو یا ضهرم8024):", MAIN_KEYBOARD)
            awaiting_scan = True
            
        elif text == '📋 لیست نمادها':
            send(chat_id, "⏳ در حال دریافت لیست نمادها...", MAIN_KEYBOARD)
            list_url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
            params = {'market': 0, 'paperTypes[0]': 1, 'paperTypes[1]': 2, 'paperTypes[2]': 3, 'withBestLimits': 'false', 'hEven': 0}
            data = fetch_json(list_url, params=params)
            
            if data:
                items = data.get('marketwatch') or data.get('marketWatch')
                if items:
                    lines = []
                    for it in items[:20]: 
                        lines.append(f"• {it.get('lva')} — {it.get('lvc')}")
                    send(chat_id, "📋 ۲۰ نماد اول بازار:\n\n" + "\n".join(lines), MAIN_KEYBOARD)
                else:
                    send(chat_id, "❌ داده‌ای دریافت نشد.", MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ سرورهای بورس پاسخ ندادند. لطفاً بعداً تلاش کنید.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    save_state({"offset": offset, "awaiting_scan": awaiting_scan})

except Exception as e:
    print("خطای کلی:", e)
