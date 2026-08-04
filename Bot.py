import websocket
import threading
import time
import os
from flask import Flask

# ====== FLASK (Sirf Render ko khush rakhne ke liye) ======
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Live!"

def keep_alive():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ====== BOT ENGINE (Room me jaane ke liye) ======
def encode_varint(value):
    out = []
    while value > 127:
        out.append((value & 0x7f) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)

def get_v1_enter_packet(room_id):
    id_bytes = room_id.encode('utf-8')
    len_id = encode_varint(len(id_bytes))
    prefix = bytes.fromhex("721C20231351A076121D4010A065825006")
    p2 = bytes.fromhex("1000F29000C3330A19E6057426968661674212")
    inner_prefix = bytes.fromhex("9802000A")
    inner_len = encode_varint(len(id_bytes) + 4)
    p1 = bytes.fromhex("0A")
    return p1 + len_id + id_bytes + p2 + inner_len + inner_prefix + len_id + id_bytes

def run_single_bot(token, room_id, bot_num):
    print(f"[Bot {bot_num}] Connecting to room {room_id}...")
    headers = {
        'User-Agent': 'com.live.party/3346 (Linux; U; Android 11)',
        'X-Auth-Token': token.strip(),
        'X-DeviceType': 'Google Pixel 4',
        'X-App-Name': 'olaparty',
        'X-OsType': 'android'
    }
    ws_url = "wss://api.olaparty.com/ikxd_cproxy?token=4470969373"

    def on_open(ws):
        print(f"[Bot {bot_num}] ✅ Connected! Entering room...")
        enter_pkt = get_v1_enter_packet(room_id)
        ws.send(enter_pkt, websocket.ABNF.OPCODE_BINARY)
        print(f"[Bot {bot_num}] ✅ Room join command sent!")

        def heartbeat():
            while True:
                time.sleep(25)
                try:
                    ping = bytes.fromhex("0A 50 50 01 18 00 22 05 65 6E 5F 69 6E 3A 14 42 61 73 65 4F 6E 6C 69 6E 65 2E 48 65 61 72 74 42 65 61 74 48 01 32 00 10 C4 A2 95 9D FB 33 0A 1B 6E 65 74 2E 69 68 61 67 6F 2E 6F 6E 6C 69 6E 65 2E 73 72 76 2E 6F 6E 6C 69 6E 65 42 05 30 2E 30 2E 30 1A 04 18 01 10 00 10 00".replace(" ", ""))
                    ws.send(ping, websocket.ABNF.OPCODE_BINARY)
                except:
                    break
        threading.Thread(target=heartbeat, daemon=True).start()

    def on_close(ws, a, b):
        print(f"[Bot {bot_num}] ❌ Disconnected. Reconnecting in 5 sec...")
        time.sleep(5)
        run_single_bot(token, room_id, bot_num)

    ws = websocket.WebSocketApp(ws_url, header=headers, on_open=on_open, on_close=on_close)
    ws.run_forever()

# ====== MAIN (Yahan se sab start hoga) ======
def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    
    with open("tokens.txt", "r") as f:
        tokens = [line.strip() for line in f if line.strip()]
    with open("rooms.txt", "r") as f:
        rooms = [line.strip() for line in f if line.strip()]
    
    if not tokens or not rooms:
        print("❌ Error: tokens.txt ya rooms.txt khali hai!")
        return

    for i, token in enumerate(tokens):
        room = rooms[i % len(rooms)]
        t = threading.Thread(target=run_single_bot, args=(token, room, i+1))
        t.daemon = True
        t.start()
        time.sleep(0.5)

    print("✅ Sab bots start ho gaye!")
    while True:
        time.sleep(100)

if __name__ == "__main__":
    main()
