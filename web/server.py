"""
Web Server for Poker Hand Replayer & RocketSolver Reviewer.
Runs locally on http://localhost:8085
Supports file uploads, progress tracking, and 888poker conversion.
"""
import sys
import os
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR.parent))

from backend import ReplayerService

service = ReplayerService()

class ReplayerHandler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _send_json(self, data, status=200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _serve_file(self, filepath, content_type="text/html"):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            index_path = BASE_DIR / "static" / "index.html"
            self._serve_file(index_path, "text/html; charset=utf-8")
        elif path == "/api/hands":
            self._send_json(service.get_hands_list())
        elif path == "/api/progress":
            self._send_json(service.progress)
        elif path == "/api/hand":
            qs = parse_qs(url.query)
            hand_id = qs.get("id", [""])[0]
            hand_data = service.get_hand_details(hand_id)
            if hand_data:
                self._send_json(hand_data)
            else:
                self._send_json({"error": "Hand not found"}, 404)
        else:
            static_file = BASE_DIR / "static" / path.lstrip("/")
            if static_file.exists() and static_file.is_file():
                ctype = "text/plain"
                if static_file.suffix == ".css":
                    ctype = "text/css"
                elif static_file.suffix == ".js":
                    ctype = "application/javascript"
                elif static_file.suffix in (".png", ".jpg", ".jpeg"):
                    ctype = f"image/{static_file.suffix.lstrip('.')}"
                elif static_file.suffix == ".svg":
                    ctype = "image/svg+xml"
                self._serve_file(static_file, ctype)
            else:
                self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""

        if path == "/api/check_solver":
            hand_ids = None
            min_hero_net_cents = None
            net_mode = "any"
            skip_reviewed = True
            if body:
                try:
                    data = json.loads(body)
                    hand_ids = data.get("hand_ids")
                    min_amt = data.get("min_hero_net")
                    if min_amt is None:
                        min_amt = data.get("min_amount")
                    if min_amt is None:
                        min_amt = data.get("min_pot")
                    if min_amt is not None and str(min_amt).strip() != "":
                        min_hero_net_cents = int(round(float(min_amt) * 100))
                    net_mode = data.get("net_mode", "any")
                    if "skip_reviewed" in data:
                        skip_reviewed = bool(data["skip_reviewed"])
                except Exception as e:
                    print(f"Error parsing check_solver payload: {e}")
            service.start_background_solver_check(hand_ids=hand_ids, min_hero_net_cents=min_hero_net_cents, net_mode=net_mode, skip_reviewed=skip_reviewed)
            self._send_json({"status": "started"})
        elif path == "/api/cancel_solver":
            result = service.cancel_solver_check()
            self._send_json(result)
        elif path == "/api/step_hand_solver":
            try:
                data = json.loads(body)
                hand_id = data.get("hand_id", "")
                result = service.step_single_hand_in_solver(hand_id)
                self._send_json(result)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 400)
        elif path == "/api/delete_hand":
            try:
                data = json.loads(body)
                hand_id = data.get("hand_id", "")
                result = service.delete_hand(hand_id)
                self._send_json(result)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 400)
        elif path == "/api/clear_hands":
            result = service.clear_all_hands()
            self._send_json(result)
        elif path == "/api/load_converted":
            result = service.load_converted_from_disk()
            self._send_json(result)
        elif path == "/api/load_samples":
            service.load_default_hands()
            self._send_json({"success": True, "count": len(service.hands)})
        elif path == "/api/import":
            try:
                data = json.loads(body)
                text = data.get("text", "")
                result = service.import_text(text)
                self._send_json(result)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 400)
        elif path == "/api/upload":
            try:
                data = json.loads(body)
                files = data.get("files", [])
                total_imported = 0
                for item in files:
                    content = item.get("content", "")
                    name = item.get("name", "uploaded")
                    res = service.import_text(content, name)
                    if res.get("success"):
                        total_imported += res.get("count", 0)
                self._send_json({"success": True, "imported_hands": total_imported})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 400)
        else:
            self.send_error(404)

def run(port=8085):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ReplayerHandler)
    print(f"Poker Hand Replayer & Solver Reviewer running at http://localhost:{port}")
    while True:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Server loop recovered from: {e}")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8085
    run(port)
