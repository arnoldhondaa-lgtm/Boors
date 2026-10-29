import requests
import json
import os

# ===== تنظیمات خودت =====
TOKEN = "8956012435:AAG8yJA3E6PouLB0hmmw7rpXzAX_flnvqRc"
# ========================

BASE = f"https://api.telegram.org/bot{TOKEN}"
STATE_FILE = "state.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36'
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

def get_symbol_list():
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
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print("خطای HTTP:", r.status_code)
            return None
        data = r.json()
        items = data.get('marketwatch') or data.get('marketWatch')
        if not items:
            print("پاسخ خالی:", str(data)[:200])
            return None
        return items
    except Exception as e:
        print("خطا در دریافت لیست:", e)
        return None

def format_symbol_list(items, limit=40):
    if not items:
        return None
    lines = []
    for it in items[:limit]:
        symbol = it.get('lVal18AFC') or it.get('symbol') or it.get('insCode')
        name = it.get('lVal30') or it.get('name') or ''
        if symbol:
            lines.append(f"• {symbol}  —  {name}")
    if not lines:
        return None
    header = f"📋 لیست نمادها (نمایش {len(lines)} از {len(items)} مورد)\n\n"
    footer = "\n\n(نمایش محدود شده است؛ در مراحل بعد جستجو اضافه می‌شود.)"
    return header + "\n".join(lines) + footer


# ---------- اجرای اصلی ----------
state = load_state()

# اگر اولین بار است، فقط آپدیت‌های قدیمی را نادیده بگیر و offset را ذخیره کن
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
print("offset فعلی:", offset)

try:
    r = requests.get(f"{BASE}/getUpdates",
                     params={'offset': offset, 'timeout': 5},
                     timeout=20)
    updates = r.json().get('result', [])
    print("تعداد آپدیت جدید:", len(updates))

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
                else:
                    send(chat_id, "لیست دریافت شد اما نام نمادها استخراج نشد.", MAIN_KEYBOARD)
            else:
                send(chat_id, "❌ دریافت لیست ناموفق بود.", MAIN_KEYBOARD)
        else:
            send(chat_id, "از منوی پایین انتخاب کن:", MAIN_KEYBOARD)

    save_state({"offset": offset})
    print("offset جدید ذخیره شد:", offset)

except Exception as e:
    print("خطای کلی:", e)
