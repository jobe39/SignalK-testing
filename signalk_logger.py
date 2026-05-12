import websocket
import json
import logging
import argparse

# Configure logging to write to SignalK_Output_Stream.log
logging.basicConfig(
    filename='SignalK_Output_Stream.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def on_message(ws, message):
    """
    Called when a message is received from the websocket.
    """
    try:
        # Log the raw JSON message to the log file
        logging.info(message)
        print(f"Received data: {message[:100]}... [logged]") # Print a small preview to console
    except Exception as e:
        print(f"Error handling message: {e}")

def on_error(ws, error):
    """
    Called when a websocket error occurs.
    """
    print(f"Websocket error: {error}")
    logging.error(f"Websocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """
    Called when the websocket connection is closed.
    """
    print("### Connection closed ###")
    logging.info("### Connection closed ###")

def on_open(ws):
    """
    Called when the websocket connection is opened.
    """
    print("### Connection established ###")
    logging.info("### Connection established ###")

    # To explicitly subscribe to all paths on all contexts, we can send a subscription message:
    subscribe_msg = {
        "context": "*",
        "subscribe": [
            {
                "path": "*",
                "period": 1000,
                "format": "delta",
                "policy": "ideal",
                "minPeriod": 200
            }
        ]
    }
    
    ws.send(json.dumps(subscribe_msg))
    print("### Sent subscription request for ALL contexts and streams ###")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SignalK Websocket Stream Logger")
    parser.add_argument("--host", default="localhost", help="SignalK server host (default: localhost)")
    parser.add_argument("--port", default="3000", help="SignalK server port (default: 3000)")
    args = parser.parse_args()

    # The stream URL usually includes ?subscribe=all, or we can send the subscribe message in on_open
    websocket_url = f"ws://{args.host}:{args.port}/signalk/v1/stream?subscribe=all"
    
    print(f"Connecting to SignalK stream at {websocket_url}...")
    
    ws = websocket.WebSocketApp(websocket_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=None)
