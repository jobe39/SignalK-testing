import websocket
import json
import time
import math

# Konfiguration
SK_SERVER = "127.0.0.1"  # Die IP deines Pi 3
LOG_FILE = "signalk_bulk_dump.txt"

# Wildcard-Pfade für den ersten Test
SUBSCRIBE_PATHS = [
    "navigation.*",
    "environment.*",
    "tanks.*",
    "electrical.*"
]

def human_readable(path, value):
    """ Konvertiert SI-Einheiten in nautische Einheiten """
    try:
        if value is None: return "None"
        
        # Geschwindigkeit: m/s -> Knoten
        if "speed" in path.lower() or "velocity" in path.lower():
            return f"{round(value * 1.94384, 2)} kn"
        
        # Temperatur: Kelvin -> Celsius
        if "temperature" in path.lower():
            return f"{round(value - 273.15, 1)} °C"
        
        # Winkel: Radiant -> Grad
        if "angle" in path.lower() or "direction" in path.lower():
            deg = math.degrees(value) % 360
            return f"{round(deg, 1)} °"
        
        # Tiefe: Meter (bleibt meist Meter)
        if "depth" in path.lower():
            return f"{round(value, 2)} m"
            
        # Tank/Batterie: 0-1 oder Volt
        if "currentlevel" in path.lower():
            return f"{round(value * 100, 1)} %"
            
        return str(value)
    except:
        return str(value)

def on_message(ws, message):
    data = json.loads(message)
    
    if "updates" in data:
        for update in data["updates"]:
            # Zeitstempel von Signal K nutzen (falls vorhanden) oder Lokalzeit
            ts = update.get("timestamp", time.strftime("%H:%M:%S"))
            
            if "values" in update:
                for item in update["values"]:
                    path = item["path"]
                    val = item["value"]
                    
                    readable_val = human_readable(path, val)
                    log_entry = f"{ts} | {path:40} | {readable_val}\n"
                    
                    with open(LOG_FILE, "a") as f:
                        f.write(log_entry)
                    print(log_entry.strip())

def on_open(ws):
    print(f"Abonniere: {', '.join(SUBSCRIBE_PATHS)}")
    subscribe_msg = {
        "context": "vessels.self",
        "subscribe": [{"path": p, "period": 2000} for p in SUBSCRIBE_PATHS]
    }
    ws.send(json.dumps(subscribe_msg))

def on_error(ws, error): print(f"Fehler: {error}")
def on_close(ws, close_status, msg): print("Verbindung beendet")

if __name__ == "__main__":
    ws_url = f"ws://{SK_SERVER}:3000/signalk/v1/stream?subscribe=none"
    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, 
                              on_error=on_error, on_close=on_close)
    ws.run_forever()