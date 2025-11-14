#!/usr/bin/env python
"""
Simple webhook receiver for testing webhooks locally.

Usage:
    python test_webhook_receiver.py

Then use ngrok or similar to expose it:
    ngrok http 8001

Use the ngrok URL as your webhook URL in the application.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming webhook requests."""
    
    received_webhooks = []
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
    
    def do_POST(self):
        """Handle POST requests (webhook payloads)."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Parse JSON payload
            try:
                payload = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                payload = body.decode('utf-8')
            
            # Store webhook data
            webhook_data = {
                'timestamp': datetime.now().isoformat(),
                'method': self.command,
                'path': self.path,
                'headers': dict(self.headers),
                'payload': payload,
            }
            self.received_webhooks.append(webhook_data)
            
            # Print webhook details
            print("\n" + "="*80)
            print(f"WEBHOOK RECEIVED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            print(f"Method: {self.command}")
            print(f"Path: {self.path}")
            print(f"Headers:")
            for key, value in self.headers.items():
                print(f"  {key}: {value}")
            print(f"\nPayload:")
            print(json.dumps(payload, indent=2))
            print("="*80 + "\n")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'status': 'success',
                'message': 'Webhook received',
                'timestamp': datetime.now().isoformat(),
                'received_payload': payload
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            print(f"Error processing webhook: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {
                'status': 'error',
                'message': str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests - show received webhooks."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Webhook Receiver - Test Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .webhook {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .timestamp {{ color: #666; font-size: 0.9em; }}
                pre {{ background: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <h1>Webhook Test Receiver</h1>
            <p>This server is listening for webhook POST requests.</p>
            <p>Total webhooks received: <strong>{len(self.received_webhooks)}</strong></p>
            <p><a href="/clear">Clear all webhooks</a></p>
            <hr>
        """
        
        if not self.received_webhooks:
            html += "<p>No webhooks received yet. Send a POST request to this URL from your application.</p>"
        else:
            for i, webhook in enumerate(reversed(self.received_webhooks[-10:]), 1):  # Show last 10
                html += f"""
                <div class="webhook">
                    <h3>Webhook #{len(self.received_webhooks) - i + 1}</h3>
                    <p class="timestamp">Received: {webhook['timestamp']}</p>
                    <p><strong>Path:</strong> {webhook['path']}</p>
                    <p><strong>Payload:</strong></p>
                    <pre>{json.dumps(webhook['payload'], indent=2)}</pre>
                </div>
                """
        
        html += """
        </body>
        </html>
        """
        
        self.wfile.write(html.encode('utf-8'))
    
    def do_DELETE(self):
        """Handle DELETE requests - clear webhooks."""
        if self.path == '/clear':
            self.received_webhooks.clear()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'status': 'success', 'message': 'All webhooks cleared'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port=8001):
    """Run the webhook receiver server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"\n{'='*80}")
    print(f"Webhook Test Receiver Server")
    print(f"{'='*80}")
    print(f"Server running on http://localhost:{port}")
    print(f"\nTo test webhooks:")
    print(f"1. Use ngrok to expose this server: ngrok http {port}")
    print(f"2. Use the ngrok URL as your webhook URL in the application")
    print(f"3. View received webhooks at: http://localhost:{port}")
    print(f"\nPress Ctrl+C to stop the server")
    print(f"{'='*80}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.server_close()
        print("Server stopped.")


if __name__ == '__main__':
    run_server()

