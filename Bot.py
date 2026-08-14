import websocket
import time
import threading
import os
import sys
import random
import string
from flask import Flask
from datetime import datetime

# ========== ACCOUNTS ==========
try:
    from accounts import ACCOUNTS
except ImportError:
    print("❌ accounts.py nahi mila!")
    sys.exit(1)

# ========== FLASK (Render/Heroku ke liye) ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ OlaParty Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

def keep_alive():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== DEFAULT ROOM (Updated) ==========
DEFAULT_ROOM_ID = "C_2088234260711592833_V2_IN_0_IN"
DEFAULT_ROOM_TOKEN = "6h4hfdCt_nMmZaFzZWVaUMtatVk9o8wX3URZ-XNYjKpOPpiEU4MxwDvR9q4YXL0zyEvADeZwLDIc6ga-9SGeqHYE1eeUSboB2EBa4PXJNVDOwev5-UisnIO5L0bYeOLHbrDIEmxisKrwG6Q5hmBM8v-o-JJ5uBElvJRui_ZLbpr_ixwP4YSlwy4BcwD1tbe8PBXT7Uf1vTg="

OLD_ROOM_ID = "C_1937779646159154560_V2_IN_0_IN"
OLD_TOKEN = "3-WXhsVKUilvhMCCIRWAqs5VRsgs_uJjk3sOVLtZ5EWr0NiGxZmLkf-SrsB3rot05VQJolfQ1cqp4ga5eEIc3RfKLJxDOyEppahp8nvYX-OHfNJnLATAFIrRWz39i7T-5cwhDp0cAxcFYPNGHOYceBfNQEKpyTeIV2gZOB5YDPH_5LPzNgNiFaAfCox8Q8KfQ7IcdG1PFM="

# ========== ONLINE FRAME TEMPLATE ==========
ONLINE_FRAME_TEMPLATE_HEX = "0A29500118002205656E5F696E3A00480032001098EEE7D7FE330A0D696B78645F6F6E6C696E655F6442002A04180110001003"

def build_online_frame(uid):
    clean_hex = ONLINE_FRAME_TEMPLATE_HEX.replace(" ", "").replace("\n", "")
    frame_bytes = bytes.fromhex(clean_hex)
    old_uid = b"1786255293228560621211"
    new_uid = str(uid).encode('utf-8')
    frame_str = frame_bytes.decode('latin-1')
    frame_str = frame_str.replace(old_uid.decode('ascii'), new_uid.decode('ascii'))
    return frame_str.encode('latin-1')

# ========== LOGGING ==========
os.makedirs("logs", exist_ok=True)
def log_message(uid, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    print(f"📩 [{uid}] {msg[:200]}...")
    with open(f"logs/{uid}.txt", "a", encoding="utf-8") as f:
        f.write(line)

# ========== DEVICE ID GENERATOR ==========
def generate_device_id():
    return ''.join(random.choices(string.hexdigits.lower(), k=32))

# ========== REPLACE ROOM IN JOIN FRAME ==========
def replace_room_in_join_frame(join_hex, new_room_id, new_token):
    old_room_hex = OLD_ROOM_ID.encode('utf-8').hex().upper()
    new_room_hex = new_room_id.encode('utf-8').hex().upper()
    old_token_hex = OLD_TOKEN.encode('utf-8').hex().upper()
    new_token_hex = new_token.encode('utf-8').hex().upper()
    
    clean_hex = join_hex.replace(" ", "").replace("\n", "")
    clean_hex = clean_hex.replace(old_room_hex, new_room_hex)
    clean_hex = clean_hex.replace(old_token_hex, new_token_hex)
    return bytes.fromhex(clean_hex)

# ========== BOT ==========
def start_bot(account, room_id, room_token):
    uid = account["uid"]
    auth_token = account["auth_token"]
    join_hex = account["join_frame_hex"]

    try:
        join_frame = replace_room_in_join_frame(join_hex, room_id, room_token)
        online_frame = build_online_frame(uid)
    except Exception as e:
        print(f"⚠️ [{uid}] Frame decode error: {e}")
        return

    device_id = generate_device_id()
    print(f"🔑 [{uid}] Device ID: {device_id}")

    def on_open(ws):
        print(f"✅ [{uid}] Connected!")
        log_message(uid, f"Connected to room: {room_id}")
        try:
            ws.send(join_frame, websocket.ABNF.OPCODE_BINARY)
            print(f"🚀 [{uid}] Sent join frame to {room_id}")
            log_message(uid, f"Sent join frame to {room_id}")
            time.sleep(0.5)
            ws.send(online_frame, websocket.ABNF.OPCODE_BINARY)
            print(f"🟢 [{uid}] Sent online presence")
            log_message(uid, "Sent online presence")
        except Exception as e:
            print(f"⚠️ [{uid}] Send error: {e}")
            log_message(uid, f"Send error: {e}")

        def heartbeat():
            while True:
                time.sleep(20)
                try:
                    ws.send(join_frame, websocket.ABNF.OPCODE_BINARY)
                    ws.send(online_frame, websocket.ABNF.OPCODE_BINARY)
                except:
                    break
        threading.Thread(target=heartbeat, daemon=True).start()

    def on_message(ws, msg):
        try:
            if isinstance(msg, bytes):
                log_message(uid, f"BINARY: {msg.hex()[:300]}...")
            else:
                log_message(uid, f"TEXT: {msg}")
        except Exception as e:
            log_message(uid, f"Msg parse error: {e}")

    def on_ping(ws, data):
        try:
            ws.send(data, websocket.ABNF.OPCODE_PONG)
        except:
            pass

    def on_error(ws, err):
        print(f"⚠️ [{uid}] Error: {err}")
        log_message(uid, f"Error: {err}")

    def on_close(ws, a, b):
        print(f"❌ [{uid}] Disconnected. Reconnecting in 5s...")
        log_message(uid, "Disconnected, reconnecting...")
        time.sleep(5)
        start_bot(account, room_id, room_token)

    ws_url = "wss://i-875.olaparty.com/ikxd_cproxy"
    headers = {
        "X-Auth-Token": auth_token,
        "X-DeviceId": device_id,
        "X-DeviceType": "Google Pixel 4",
        "X-App-Name": "olaparty",
        "X-OsType": "android",
        "X-CpuArch": "aarch64",
        "X-App-Channel": "official",
        "X-Sdk-Ver": "30",
        "X-SimCIso": "in",
        "X-Client-Net": "1",
        "X-BuildCode": "3185",
        "X-App-LastVer": "",
        "X-Apk-Abi": "abi64",
        "X-Lang": "en_in",
        "X-App-Ver": "52303",
        "X-App-Real-Ver": "52303",
        "X-Os-Ver": "11",
        "X-Pcid": f"115292150462477{uid[-4:]}",
        "X-Request-WsId": str(int(time.time()*1000)),
        "X-Last-Seqid": "0",
        "Origin": "https://i-875.olaparty.com",
        "User-Agent": "com.live.party/3185 (Linux; U; Android 11; en_IN; Pixel 4; Build/RD2A.211001.002; Cronet/93.0.4533.0)"
    }
    
    try:
        ws = websocket.WebSocketApp(ws_url, header=headers, on_open=on_open,
                                    on_message=on_message, on_ping=on_ping,
                                    on_error=on_error, on_close=on_close)
        ws.run_forever(ping_interval=20, ping_timeout=10)
    except Exception as e:
        print(f"⚠️ [{uid}] Connection exception: {e}")
        log_message(uid, f"Connection exception: {e}")
        time.sleep(5)
        start_bot(account, room_id, room_token)

# ========== MAIN ==========
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 OlaParty Bot Launcher")
    print("="*50)
    
    room_id = DEFAULT_ROOM_ID
    room_token = DEFAULT_ROOM_TOKEN
    bot_count = len(ACCOUNTS)

    selected_accounts = ACCOUNTS[:bot_count]
    print(f"\n✅ {bot_count} bots will be started with Room: {room_id}")
    print("="*50 + "\n")

    # ========== START FLASK ==========
    print("⚡ Starting Flask server...")
    threading.Thread(target=keep_alive, daemon=True).start()
    time.sleep(2)

    # ========== START BOTS (Speed Increased) ==========
    for idx, acc in enumerate(selected_accounts, 1):
        uid = acc['uid']
        print(f"🔄 Bot {idx} (UID: {uid}) starting...")
        threading.Thread(target=start_bot, args=(acc, room_id, room_token), daemon=True).start()
        time.sleep(0.2)

    print("\n✅ All bots are running continuously.")
    
    while True:
        time.sleep(60)
