import os
import sys
import threading
import time
from flask import Flask
import websocket

# Try to import accounts from accounts.py
try:
  from accounts import BOTS
except ImportError:
  BOTS = []
  print("⚠️ accounts.py not found. Please create it with your BOTS list.")

app = Flask(__name__)


@app.route("/")
def home():
  return "OlaParty Bots are running 24/7!"


def keep_alive():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# ==================== TARGET ROOM ====================
ROOM_ID = "C_1894232843312212416_V2_IN_0_IN"
ROOM_TOKEN = "Vr-dn2Edht6fLn70BYyBP2i2qKGl6zLU2Yn7KxB7E6VFAnMUpU6EaNya5ZbAmeoD260AU2fXjolq2UPv0pTOfgo8SpSMne4zu_z4ict5LZbdIUlbIoFVoXmLVE-6duCtIj3fVfGxkU4ejHg0GCRls-48k_LP6YHCux5Rex9Z6Jjm72OeCZEBdMR7iEsSWrffDyK_zsQZt5A="

OLD_ROOM_ID = "C_1937779646159154560_V2_IN_0_IN"
OLD_TOKEN = "3-WXhsVKUilvhMCCIRWAqs5VRsgs_uJjk3sOVLtZ5EWr0NiGxZmLkf-SrsB3rot05VQJolfQ1cqp4ga5eEIc3RfKLJxDOyEppahp8nvYX-OHfNJnLATAFIrRWz39i7T-5cwhDp0cAxcFYPNGHOYceBfNQEKpyTeIV2gZOB5YDPH_5LPzNgNiFaAfCox8Q8KfQk7IcdG1PFM="


def replace_room_in_frame(frame_hex):
  clean_hex = frame_hex.replace(" ", "").replace("\n", "")
  old_room_hex = OLD_ROOM_ID.encode("utf-8").hex().upper()
  new_room_hex = ROOM_ID.encode("utf-8").hex().upper()
  clean_hex = clean_hex.replace(old_room_hex, new_room_hex)
  old_token_hex = OLD_TOKEN.encode("utf-8").hex().upper()
  new_token_hex = ROOM_TOKEN.encode("utf-8").hex().upper()
  clean_hex = clean_hex.replace(old_token_hex, new_token_hex)
  return bytes.fromhex(clean_hex)


# ==================== HEARTBEAT ====================
def start_bot(config):
  uid = config["uid"]
  join_frame_bytes = replace_room_in_frame(config["join_frame_hex"])

  def on_open(ws):
    print(f"✅ Bot {uid} connected with device {config['device_id']}.")
    ws.send(join_frame_bytes, websocket.ABNF.OPCODE_BINARY)
    print(f"🚀 Bot {uid} sent Channel.Enter for new room.")

    def heartbeat():
      while True:
        time.sleep(20)
        try:
          ws.send(join_frame_bytes, websocket.ABNF.OPCODE_BINARY)
        except:
          break

    threading.Thread(target=heartbeat, daemon=True).start()

  def on_ping(ws, data):
    ws.send(data, websocket.ABNF.OPCODE_PONG)

  def on_error(ws, err):
    print(f"⚠️ Bot {uid} Error: {err}")

  def on_close(ws, a, b):
    print(f"❌ Bot {uid} disconnected. Reconnecting in 5s...")
    time.sleep(5)
    start_bot(config)

  ws_url = f"wss://i-875.olaparty.com/ikxd_cproxy?token={uid}"
  headers = {
      "X-Auth-Token": config["auth_token"],
      "X-DeviceId": config["device_id"],
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
      "X-Pcid": "1152921504624773252",
      "X-Request-WsId": str(int(time.time() * 1000)),
      "X-Last-Seqid": "0",
      "Origin": "wss://i-875.olaparty.com",
      (
          "User-Agent"
      ): "com.live.party/3185 (Linux; U; Android 11; en_IN; Pixel 4;"
      " Build/RD2A.211001.002; Cronet/93.0.4533.0)",
  }
  ws = websocket.WebSocketApp(
      ws_url,
      header=headers,
      on_open=on_open,
      on_ping=on_ping,
      on_error=on_error,
      on_close=on_close,
  )
  ws.run_forever(ping_interval=20, ping_timeout=10)


def start_all_bots():
  print("=== OlaParty Bots Starting (New Room) ===")
  if not BOTS:
    print(
        "⚠️ No bots found. Please add your accounts to accounts.py and"
        " restart."
    )
    return
  for bot in BOTS:
    thread = threading.Thread(target=start_bot, args=(bot,))
    thread.daemon = True
    thread.start()
    time.sleep(2)


print("⚡ Bot script loaded! Starting Flask + Bots...")
threading.Thread(target=keep_alive, daemon=True).start()
threading.Thread(target=start_all_bots, daemon=True).start()

print("🔄 Bot is running. Keeping main thread alive...")
while True:
  time.sleep(60)
