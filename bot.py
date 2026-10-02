# bot.py - OlaParty Bot with Fake UIDs + Auto Restart @ 4 AM

import websocket
import time
import threading
import os
import sys
import random
import string
import json
from flask import Flask, jsonify
from datetime import datetime, timedelta, timezone

# ==================== ACCOUNTS IMPORT ====================
try:
    from accounts import ACCOUNTS
    print(f"✅ accounts.py loaded! Total accounts: {len(ACCOUNTS)}")
except ImportError:
    print("❌ accounts.py not found! Please create accounts.py with ACCOUNTS list.")
    sys.exit(1)

# ==================== CONFIG ====================
# IST timezone (India)
IST = timezone(timedelta(hours=5, minutes=30))

# Auto restart time (IST) - default 4:00 AM
RESTART_HOUR   = int(os.environ.get("RESTART_HOUR", 4))
RESTART_MINUTE = int(os.environ.get("RESTART_MINUTE", 0))

# Restart gap between stop-all and start-all (seconds)
RESTART_GAP = int(os.environ.get("RESTART_GAP", 15))

# ==================== GLOBAL STATE ====================
active_bots = []                 # list[OlaPartyBot]
bots_lock = threading.Lock()
last_restart_time = None
restart_in_progress = False

# ==================== FLASK SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    with bots_lock:
        total = len(active_bots)
        connected = sum(1 for b in active_bots if b.connected)
        fake_count = sum(1 for b in active_bots if b.is_fake)
    return f"""
    <html>
        <head><title>OlaParty Bot</title>
        <style>
            body {{ font-family: Arial; margin: 50px; background: #f0f0f0; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 650px; margin: auto; }}
            h1 {{ color: #4CAF50; }}
            .status {{ color: green; font-weight: bold; }}
            .btn {{ background:#f44336;color:white;padding:10px 18px;border-radius:6px;text-decoration:none; }}
        </style></head>
        <body>
            <div class="container">
                <h1>🤖 OlaParty Bot</h1>
                <p>Status: <span class="status">✅ Running</span></p>
                <p>Total Bots: <b>{total}</b> | Connected: <b>{connected}</b> | Fake UIDs: <b>{fake_count}</b></p>
                <p>Next auto-restart: <b>{RESTART_HOUR:02d}:{RESTART_MINUTE:02d} IST (daily)</b></p>
                <p>
                    <a href="/status">📊 Status</a> &nbsp;|&nbsp;
                    <a class="btn" href="/restart">🔄 Restart Now</a>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/status')
def status():
    with bots_lock:
        total = len(active_bots)
        connected = sum(1 for b in active_bots if b.connected)
        fake_count = sum(1 for b in active_bots if b.is_fake)
    return jsonify({
        "status": "running",
        "total_bots": total,
        "connected_bots": connected,
        "fake_uids": fake_count,
        "restart_in_progress": restart_in_progress,
        "last_restart_time": last_restart_time.isoformat() if last_restart_time else None,
        "next_restart_ist": get_next_restart_time().isoformat(),
        "restart_hour_ist": RESTART_HOUR,
        "restart_minute_ist": RESTART_MINUTE,
        "timestamp": datetime.now(IST).isoformat()
    })

@app.route('/health')
def health():
    return "OK", 200

@app.route('/restart')
def manual_restart():
    """Manual restart trigger (browser / cron-job.org)"""
    threading.Thread(target=restart_all_bots, args=("manual",), daemon=True).start()
    return jsonify({
        "ok": True,
        "message": "Restart triggered. Check /status in 30 seconds.",
        "triggered_at": datetime.now(IST).isoformat()
    })

def keep_alive():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== DEFAULT ROOM ====================
DEFAULT_ROOM_ID = "C_2077124164694823808_V2_IN_0_IN"
DEFAULT_ROOM_TOKEN = "Ra_9sbCgmGBcmP-VPeIib63xADHMsQvOhNAZFh6a3yPkq1w57TQ8H1OaQoh1UsXvN2y2Jh7XDAMAnEFSgyXT4RNnRcg9vfG0e0G5noJkCSu9-A11se2Hegf27UN6rl-dQCnbyWNLv1TWbPRZCQfC25a9w9po6a5_Rxoga1WPyZ8EAV6efgrW1fzVe2NMGk33lFCb7uyKpAI="

# ==================== BASE ONLINE FRAME ====================
BASE_ONLINE_FRAME_HEX = "0A29500118002205656E5F696E3A00480032001098EEE7D7FE330A0D696B78645F6F6E6C696E655F6442002A04180110001003"

def build_base_online_frame(uid):
    try:
        clean_hex = BASE_ONLINE_FRAME_HEX.replace(" ", "").replace("\n", "")
        frame_bytes = bytes.fromhex(clean_hex)
        old_uid = b"1786255293228560621211"
        new_uid = str(uid).encode('utf-8')
        frame_str = frame_bytes.decode('latin-1')
        frame_str = frame_str.replace(old_uid.decode('ascii'), new_uid.decode('ascii'))
        return frame_str.encode('latin-1')
    except Exception as e:
        print(f"⚠️ Base online frame error: {e}")
        return None

# ==================== LOGGING ====================
os.makedirs("logs", exist_ok=True)

def log_message(uid, msg):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    print(f"📩 [{uid}] {msg[:200]}...")
    try:
        with open(f"logs/{uid}.txt", "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

# ==================== DEVICE ID ====================
def generate_device_id():
    return ''.join(random.choices(string.hexdigits.lower(), k=32))

# ==================== FRAME REPLACEMENT ====================
def replace_room_in_hex(hex_string, new_room_id):
    if not hex_string:
        return None
    clean_hex = hex_string.replace(" ", "").replace("\n", "")
    old_room_hex = DEFAULT_ROOM_ID.encode('utf-8').hex().upper()
    new_room_hex = new_room_id.encode('utf-8').hex().upper()
    updated_hex = clean_hex.replace(old_room_hex, new_room_hex)
    try:
        return bytes.fromhex(updated_hex)
    except:
        return None

def replace_room_and_token(hex_string, new_room_id, new_token):
    if not hex_string:
        return None
    clean_hex = hex_string.replace(" ", "").replace("\n", "")
    old_room_hex = DEFAULT_ROOM_ID.encode('utf-8').hex().upper()
    new_room_hex = new_room_id.encode('utf-8').hex().upper()
    clean_hex = clean_hex.replace(old_room_hex, new_room_hex)
    old_token_hex = DEFAULT_ROOM_TOKEN.encode('utf-8').hex().upper()
    new_token_hex = new_token.encode('utf-8').hex().upper()
    clean_hex = clean_hex.replace(old_token_hex, new_token_hex)
    try:
        return bytes.fromhex(clean_hex)
    except:
        return None

# ==================== BOT CLASS ====================
class OlaPartyBot:
    def __init__(self, account, room_id, room_token):
        self.account = account
        self.uid = account["uid"]
        self.auth_token = account["auth_token"]
        self.join_hex = account["join_frame_hex"]
        self.online_room_hex = account["online_room_frame_hex"]
        self.room_id = room_id
        self.room_token = room_token
        self.device_id = generate_device_id()
        self.ws = None
        self.running = True
        self.connected = False

        self.is_fake = len(str(self.uid)) > 15 or len(str(self.uid)) < 10

        if self.is_fake:
            print(f"🔴 [{self.uid}] Fake UID detected (length: {len(str(self.uid))})")
        else:
            print(f"🟢 [{self.uid}] Real UID (length: {len(str(self.uid))})")

        self.prepare_frames()

    def prepare_frames(self):
        try:
            self.join_frame = replace_room_and_token(self.join_hex, self.room_id, self.room_token)
            self.base_online_frame = build_base_online_frame(self.uid)
            self.room_online_frame = replace_room_in_hex(self.online_room_hex, self.room_id)

            if self.join_frame and self.base_online_frame and self.room_online_frame:
                log_message(self.uid, f"✅ All frames prepared")
                return True
            return False
        except Exception as e:
            log_message(self.uid, f"❌ Frame error: {e}")
            return False

    def on_open(self, ws):
        self.connected = True
        fake_status = "FAKE" if self.is_fake else "REAL"
        print(f"✅ [{self.uid}] Connected! ({fake_status})")
        log_message(self.uid, f"Connected to room: {self.room_id}")

        try:
            ws.send(self.join_frame, websocket.ABNF.OPCODE_BINARY)
            print(f"🚀 [{self.uid}] Sent Join Frame")
            time.sleep(0.5)
            ws.send(self.base_online_frame, websocket.ABNF.OPCODE_BINARY)
            print(f"🟢 [{self.uid}] Sent Base Online Frame")
            time.sleep(0.3)
            ws.send(self.room_online_frame, websocket.ABNF.OPCODE_BINARY)
            print(f"🔵 [{self.uid}] Sent Room Online Frame")
        except Exception as e:
            print(f"⚠️ [{self.uid}] Send error: {e}")
            log_message(self.uid, f"Send error: {e}")

        self.start_heartbeats(ws)

    def start_heartbeats(self, ws):
        def base_heartbeat():
            while self.running:
                time.sleep(25)
                try:
                    if self.connected and ws:
                        ws.send(self.base_online_frame, websocket.ABNF.OPCODE_BINARY)
                except:
                    self.connected = False
                    break

        def room_heartbeat():
            while self.running:
                time.sleep(20)
                try:
                    if self.connected and ws:
                        ws.send(self.room_online_frame, websocket.ABNF.OPCODE_BINARY)
                except:
                    self.connected = False
                    break

        threading.Thread(target=base_heartbeat, daemon=True).start()
        threading.Thread(target=room_heartbeat, daemon=True).start()
        print(f"💓 [{self.uid}] Heartbeats started (Base: 25s, Room: 20s)")
        log_message(self.uid, "Heartbeats started")

    def on_message(self, ws, msg):
        try:
            if isinstance(msg, bytes):
                log_message(self.uid, f"BINARY: {msg.hex()[:300]}...")
            else:
                log_message(self.uid, f"TEXT: {msg[:300]}")
        except:
            pass

    def on_ping(self, ws, data):
        try:
            ws.send(data, websocket.ABNF.OPCODE_PONG)
        except:
            pass

    def on_error(self, ws, err):
        print(f"⚠️ [{self.uid}] Error: {err}")
        log_message(self.uid, f"Error: {err}")
        self.connected = False

    def on_close(self, ws, a, b):
        print(f"❌ [{self.uid}] Disconnected")
        log_message(self.uid, "Disconnected")
        self.connected = False
        self.reconnect()

    def reconnect(self):
        if not self.running:
            return
        print(f"🔄 [{self.uid}] Reconnecting in 5 seconds...")
        log_message(self.uid, "Reconnecting...")
        time.sleep(5)
        if self.running:
            self.start()

    def start(self):
        if not self.running:
            return
        if not self.join_frame or not self.base_online_frame or not self.room_online_frame:
            if not self.prepare_frames():
                print(f"❌ [{self.uid}] Cannot start")
                return

        ws_url = "wss://i-875.olaparty.com/ikxd_cproxy"
        headers = {
            "X-Auth-Token": self.auth_token,
            "X-DeviceId": self.device_id,
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
            "X-Pcid": f"115292150462477{str(self.uid)[-4:]}",
            "X-Request-WsId": str(int(time.time()*1000)),
            "X-Last-Seqid": "0",
            "Origin": "https://i-875.olaparty.com",
            "User-Agent": "com.live.party/3185 (Linux; U; Android 11; en_IN; Pixel 4; Build/RD2A.211001.002; Cronet/93.0.4533.0)"
        }

        try:
            self.ws = websocket.WebSocketApp(
                ws_url,
                header=headers,
                on_open=self.on_open,
                on_message=self.on_message,
                on_ping=self.on_ping,
                on_error=self.on_error,
                on_close=self.on_close
            )
            self.ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            print(f"⚠️ [{self.uid}] Connection error: {e}")
            log_message(self.uid, f"Connection error: {e}")
            if self.running:
                self.reconnect()

    def stop(self):
        self.running = False
        self.connected = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        print(f"🛑 [{self.uid}] Stopped")
        log_message(self.uid, "Bot stopped")

# ==================== BOT MANAGER ====================
def create_and_start_bots():
    """Create fresh bots and start them, store in global list"""
    global active_bots

    room_id = os.environ.get("ROOM_ID", DEFAULT_ROOM_ID)
    room_token = os.environ.get("ROOM_TOKEN", DEFAULT_ROOM_TOKEN)

    try:
        bot_count = int(os.environ.get("BOT_COUNT", len(ACCOUNTS)))
        if bot_count < 1 or bot_count > len(ACCOUNTS):
            bot_count = len(ACCOUNTS)
    except:
        bot_count = len(ACCOUNTS)

    selected_accounts = ACCOUNTS[:bot_count]
    print(f"📍 Room ID: {room_id}")
    print(f"🤖 Starting {bot_count} bots...")

    new_bots = []
    for idx, acc in enumerate(selected_accounts, 1):
        uid = acc["uid"]
        fake_status = "🔴 FAKE" if (len(str(uid)) > 15 or len(str(uid)) < 10) else "🟢 REAL"
        print(f"🔄 Bot {idx}/{bot_count} (UID: {uid}) {fake_status} starting...")
        bot = OlaPartyBot(acc, room_id, room_token)
        bot_thread = threading.Thread(target=bot.start, daemon=True)
        bot_thread.start()
        new_bots.append(bot)
        time.sleep(3)

    with bots_lock:
        active_bots = new_bots

    print(f"✅ {len(new_bots)} bots deployed\n")

def stop_all_bots():
    """Stop all currently active bots"""
    with bots_lock:
        old = list(active_bots)
    print(f"🛑 Stopping {len(old)} bots...")
    for b in old:
        try:
            b.stop()
        except Exception as e:
            print(f"⚠️ stop error for {b.uid}: {e}")
    # Wait for WS to fully close & reconnect loops to exit
    time.sleep(3)

def restart_all_bots(trigger="auto"):
    """Full restart cycle: stop old → wait → start fresh"""
    global last_restart_time, restart_in_progress

    if restart_in_progress:
        print("⚠️ Restart already in progress, skipping...")
        return

    restart_in_progress = True
    try:
        print("\n" + "="*70)
        print(f"♻️  RESTARTING ALL BOTS ({trigger.upper()}) @ {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("="*70)

        stop_all_bots()

        print(f"⏳ Waiting {RESTART_GAP}s before restart...")
        time.sleep(RESTART_GAP)

        create_and_start_bots()

        last_restart_time = datetime.now(IST)
        print(f"✅ Restart complete @ {last_restart_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("="*70 + "\n")
    except Exception as e:
        print(f"❌ Restart error: {e}")
    finally:
        restart_in_progress = False

# ==================== AUTO-RESTART SCHEDULER ====================
def get_next_restart_time():
    """Return next 4:00 AM IST as timezone-aware datetime"""
    now = datetime.now(IST)
    target = now.replace(hour=RESTART_HOUR, minute=RESTART_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target

def auto_restart_scheduler():
    """Background thread: sleep until 4:00 AM IST → restart → repeat"""
    print(f"⏰ Auto-restart scheduler started. Daily at {RESTART_HOUR:02d}:{RESTART_MINUTE:02d} IST")
    while True:
        try:
            next_run = get_next_restart_time()
            wait_seconds = (next_run - datetime.now(IST)).total_seconds()
            print(f"⏳ Next auto-restart scheduled at {next_run.strftime('%Y-%m-%d %H:%M:%S IST')} "
                  f"(in {wait_seconds/3600:.2f} hours)")

            # Sleep in 60s chunks so we can react to clock drift
            while wait_seconds > 0:
                chunk = min(60, wait_seconds)
                time.sleep(chunk)
                wait_seconds -= chunk
                # Small drift correction
                now = datetime.now(IST)
                if now.hour == RESTART_HOUR and now.minute == RESTART_MINUTE:
                    break

            # Trigger restart
            restart_all_bots(trigger="auto-4am")
        except Exception as e:
            print(f"⚠️ Scheduler error: {e}, retrying in 60s")
            time.sleep(60)

# ==================== MAIN ====================
def main():
    print("\n" + "="*70)
    print("🤖 OLA PARTY BOT - WITH FAKE UIDs + AUTO RESTART")
    print("="*70)
    print(f"📱 Total Accounts: {len(ACCOUNTS)}")
    print(f"⏰ Daily auto-restart: {RESTART_HOUR:02d}:{RESTART_MINUTE:02d} IST")
    print("="*70 + "\n")

    # 1. Start Flask (keep-alive) first so Render/Railway health check passes
    threading.Thread(target=keep_alive, daemon=True).start()
    time.sleep(2)

    # 2. Start auto-restart scheduler
    threading.Thread(target=auto_restart_scheduler, daemon=True).start()

    # 3. Start bots
    create_and_start_bots()

    print("="*70)
    print(f"✅ All bots running! Next restart: "
          f"{get_next_restart_time().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"📁 Logs in 'logs/' folder")
    print(f"🌐 Web: http://localhost:{os.environ.get('PORT', 10000)}")
    print(f"🔄 Manual restart: /restart")
    print("="*70 + "\n")

    # 4. Status loop
    try:
        while True:
            time.sleep(60)
            with bots_lock:
                total = len(active_bots)
                connected = sum(1 for b in active_bots if b.connected)
                fake_count = sum(1 for b in active_bots if b.is_fake)
            next_r = get_next_restart_time().strftime('%H:%M IST')
            print(f"📊 Status: {connected}/{total} connected | Fake: {fake_count} | "
                  f"Next restart: {next_r}")
    except KeyboardInterrupt:
        print("\n🛑 Stopping all bots...")
        stop_all_bots()
        print("✅ All bots stopped. Goodbye!")

if __name__ == '__main__':
    main()
