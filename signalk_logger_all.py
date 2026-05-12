import websocket
import json
import time

# EINSTELLUNGEN
# Ersetze 'raspberrypi.local' durch die IP deines PIs
SK_SERVER = "127.0.0.1" 
SK_PORT = "3000"
LOG_FILE = "signalk_dump.json"

def on_message(ws, message):
    # Die Daten kommen als String (JSON-Format)
    print(f"Daten empfangen und gespeichert: {time.ctime()}")
    
    # In Datei schreiben (Modus 'a' für Append / Anhängen)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

def on_error(ws, error):
    print(f"Fehler: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Verbindung geschlossen")

def on_open(ws):
    print("Verbindung zu Signal K hergestellt...")
    # Wir abonnieren alle Daten (self)
    subscribe_msg = {
        "context": "vessels.self",
        "subscribe": [{
            "path": "*",
            "period": 1000 # Update alle 1000ms
        }]
    }
    ws.send(json.dumps(subscribe_msg))

if __name__ == "__main__":
    # WebSocket URL für Signal K Deltas
    ws_url = f"ws://{SK_SERVER}:{SK_PORT}/signalk/v1/stream?subscribe=none"
    
    ws = websocket.WebSocketApp(ws_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever()