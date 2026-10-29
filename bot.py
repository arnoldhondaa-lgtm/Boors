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

# کیبوردهای ربات
MAIN_KEYBOARD = {
    'keyboard': [
        [{'text': '📊 اسکن'}, {'text': '📋 لیست نمادها'}],
        [{'text': '⚙️ تنظیمات'}]
    ],
    'resize_keyboard': True,
    'is_persistent': True
}

SETTINGS_KEYBOARD = {
    'keyboard': [
        [{'text': '🔔 افزودن هشدار'}, {'text': '📋 لیست هشدارها'}],
        [{'text': '🔙 بازگشت به منوی اصلی'}]
    ],
    'resize_keyboard': True,
    'is_persistent': True
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

# ====== موتور دریافت داده ======
def fetch_json(url, params=None):
    try:
        full_url = url
        if params:
            full_url += "?" + urlencode(params)
        jina_url = f"https://r.jina.ai/{full_url}"
        r = requests.get(jina_url, headers={'Accept': 'application/json'}, timeout=15)
        if r.status_code == 200:
            text = r.text.strip()
            if text.startswith('{') or text.startswith('['):
                return json.loads(text)
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
    except Exception:
        pass

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def get_symbol_info_and_price(query):
    search_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(query)}"
    search_data = fetch_json(search_url)
    if not search_data or 'instrumentSearch' not in search_data:
        return None, None
    
    items = search_data['instrumentSearch']
    if not items:
        return None, None
    
    exact_match = None
    for item in items:
        if item.get('lVal18AFC', '').strip().replace('ي', 'ی').replace('ك', 'ک') == query.strip().replace('ي', 'ی').replace('ك', 'ک'):
            exact_match = item
            break
    if not exact_match:
        exact_match = items[0]
        
    ins_code = exact_match.get('insCode')
    price_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
    price_data = fetch_json(price_url)
    if not price_data or 'closingPriceInfo' not in price_data:
        return None, None
        
    return exact_match, price_data['closingPriceInfo']

# ========== اجرای اصلی ==========
state = load_state()
offset = state.get("offset", 0)
alerts = state.get("alerts", [])
# حالت‌های انتظار
awaiting_scan = state.get("awaiting_scan", False)
awaiting_alert_sym = state.get("awaiting_alert_sym", False)
awaiting_alert_price = state.get("awaiting_alert_price", False)
temp_alert_sym = state.get("temp_alert_sym", "")

# اگر اولین اجراست
if offset == 0 and not os.path.exists(STATE_FILE):
    try:
        r = requests.get(f"{BASE}/getUpdates", timeout=15)
        updates = r.json().get('result', [])
        offset = (max(u['update_id'] for u in updates) + 1) if updates else 0
    except Exception:
        pass
    save_state({"offset": offset, "alerts": []})
    exit(0)

# ---------- ۱. بررسی هشدارهای فعال ----------
if alerts:
    print(f"بررسی {len(alerts)} هشدار...")
    remaining_alerts = []
    for alert in alerts:
        sym = alert.get("symbol")
        target = alert.get("target")
        chat_id = alert.get("chat_id")
        
        info, price = get_symbol_info_and_price(sym)
        if price:
            current_price = price.get('pDrCotVal', 0)
            print(f"نماد {sym}: قیمت فعلی {current_price} - هدف {target}")
            
            if current_price >= target:
                msg = f"🚨 **هشدار قیمت!**\n\n"
                msg += f"نماد: {sym}\n"
                msg += f"قیمت هدف شما: {target:,} ریال\n"
                msg += f"قیمت فعلی: {current_price:,} ریال\n"
                msg += f"این هشدار از لیست شما حذف شد."
                send(chat_id, msg, MAIN_KEYBOARD)
                # هشدار مصرف شده و به لیست باقی‌مانده اضافه نمی‌شود
            else:
                remaining_alerts.append(alert)
        else:
            # اگر در دریافت قیمت خطا داد، هشدار را نگه میداریم برای دفعه بعد
            remaining_alerts.append(alert)
            
    if len(remaining_alerts) != len(alerts):
        alerts = remaining_alerts
        state["alerts"] = alerts
        save_state(state)

# ---------- ۲. دریافت پیام‌های تلگرام ----------
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

        # --- حالت‌های انتظار برای ورودی کاربر ---
        if awaiting_scan:
            send(chat_id, f"⏳ در حال جستجوی نماد «{text}»...", MAIN_KEYBOARD)
            info, price = get_symbol_info_and_price(text)
            if info and price:
                msg_text = f"📊 نماد: {info.get('lVal18AFC')}\n🏢 {info.get('lVal30')}\n\n"
                msg_text += f"💰 آخرین معامله: {price.get('pDrCotVal', 0):,} ریال\n"
                msg_text += f"🔒 قیمت پایانی: {price.get('pClosing', 0):,} ریال"
                send(chat_id, msg_text, MAIN_KEYBOARD)
            else:
                send(chat_id, f"❌ نماد پیدا نشد یا خطای شبکه.", MAIN_KEYBOARD)
            awaiting_scan = False 
            continue

        if awaiting_alert_sym:
            info, price = get_symbol_info_and_price(text)
            if info:
                temp_alert_sym = info.get('lVal18AFC')
                send(chat_id, f"✅ نماد {temp_alert_sym} انتخاب شد.\nحالا قیمت هدف را به ریال بنویسید (فقط عدد):", MAIN_KEYBOARD)
                awaiting_alert_sym = False
                awaiting_alert_price = True
            else:
                send(chat_id, "❌ نماد پیدا نشد. نام نماد را دقیق بنویسید:", MAIN_KEYBOARD)
            continue

        if awaiting_alert_price:
            try:
                target = int(text.replace(',', ''))
                alerts.append({"symbol": temp_alert_sym, "target": target, "chat_id": chat_id})
                state["alerts"] = alerts
                send(chat_id, f"✅ هشدار ثبت شد!\nهر ۵ دقیقه چک می‌کنم، اگر {temp_alert_sym} به {target:,} ریال برسد بهت خبر می‌دم.", MAIN_KEYBOARD)
            except ValueError:
                send(chat_id, "❌ لطفاً فقط عدد بنویسید (مثلاً 45000).", MAIN_KEYBOARD)
                continue
            
            awaiting_alert_price = False
            temp_alert_sym = ""
            continue

        # --- پردازش دکمه‌های منو ---
        if text == '/start':
            send(chat_id, "سلام 👋\nاز منوی پایین یک گزینه انتخاب کن:", MAIN_KEYBOARD)
            
        elif text == '⚙️ تنظیمات':
            send(chat_id, "به بخش تنظیمات خوش آمدید. چه کاری می‌خواهید انجام دهید؟", SETTINGS_KEYBOARD)
            
        elif text == '🔙 بازگشت به منوی اصلی':
            send(chat_id, "به منوی اصلی برگشتید.", MAIN_KEYBOARD)
            
        elif text == '🔔 افزودن هشدار':
            send(chat_id, "🔍 نام نماد مورد نظر برای هشدار را بنویسید (مثلاً: خودرو یا ضهرم8024):", MAIN_KEYBOARD)
            awaiting_alert_sym = True
            awaiting_alert_price = False
            
        elif text == '📋 لیست هشدارها':
            if not alerts:
                send(chat_id, "شما هیچ هشدار فعالی ندارید.", SETTINGS_KEYBOARD)
            else:
                msg = "📋 هشدارهای فعال شما:\n\n"
                for i, a in enumerate(alerts, 1):
                    msg += f"{i}. {a['symbol']} -> بالای {a['target']:,} ریال\n"
                send(chat_id, msg, SETTINGS_KEYBOARD)
            
        elif text == '📊 اسکن':
            send(chat_id, "🔍 لطفاً نام نماد مورد نظر را بنویسید:", MAIN_KEYBOARD)
            awaiting_scan = True
            
        elif text == '📋 لیست نمادها':
            send(chat_id, "⏳ در حال دریافت لیست نمادها...", MAIN_KEYBOARD)
            list_url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
            params = {'market': 0, 'paperTypes[0]': 1, 'withBestLimits': 'false', 'hEven': 0}
            data = fetch_json(list_url, params=params)
            if data and data.get('marketwatch'):
                items = data['marketwatch'][:20]
                lines = [f"• {it.get('lva')} — {it.get('lvc')}" for it in items]
                send(chat_id, "📋 ۲۰ نماد اول بازار:\n\n" + "\n".join(lines), MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ سرورهای بورس پاسخ ندادند.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    # ذخیره وضعیت نهایی
    state.update({
        "offset": offset, 
        "alerts": alerts,
        "awaiting_scan": awaiting_scan,
        "awaiting_alert_sym": awaiting_alert_sym,
        "awaiting_alert_price": awaiting_alert_price,
        "temp_alert_sym": temp_alert_sym
    })
    save_state(state)

except Exception as e:
    print("خطای کلی:", e)
