"""Browser boundary listener gate (default-off): the REAL MCP front (mcp/front.py + tools.py, as inlined) in front of
the REAL relay. Agent paths refuse browsers; the recipient page and its one-use link keep working.
Run: uv run --with cryptography==50.0.2 python -m unittest tests.test_listener_gate -v
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GateTest(unittest.TestCase):
    boundary = "1"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sd-gate-"))
        (self.tmp / "data").mkdir()
        self.eport, self.fport = free_port(), free_port()
        cfg = server.Config.from_env({"SECRET_DROP_DATA_DIR": str(self.tmp / "data"), "SECRET_DROP_BIND": "127.0.0.1",
                                      "SECRET_DROP_PORT": str(self.eport)})
        self.engine = server.Server(cfg)
        threading.Thread(target=self.engine.serve_forever, daemon=True).start()
        src = (ROOT / "mcp/front.py").read_text() + "\n\n" + (ROOT / "mcp/tools.py").read_text() + "\n\nif __name__ == '__main__':\n    asyncio.run(main())\n"
        (self.tmp / "front.py").write_text(src)
        env = {"PATH": os.environ.get("PATH", ""), "WIZARD_APP": "secret-drop", "FRONT_PORT": str(self.fport), "UPSTREAM_HOST": "127.0.0.1",
               "UPSTREAM_PORT": str(self.eport), "WIZARD_BROWSER_BOUNDARY": self.boundary}
        self.front = subprocess.Popen([sys.executable, str(self.tmp / "front.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if self.req("GET", "/health")[0] == 200:
                    break
            except OSError:
                time.sleep(0.05)

    def tearDown(self) -> None:
        self.front.kill(); self.front.wait()
        self.engine.shutdown(); self.engine.server_close()

    def req(self, method, path, headers=None, body=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.fport, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.fport}", **(headers or {})}
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            h.setdefault("Content-Type", "application/json")
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        out = (r.status, r.read(), dict(r.getheaders()))
        c.close()
        return out

    def create(self, headers=None):
        pub = os.urandom(32)
        import base64
        return self.req("POST", "/api/v1/requests", headers, {"label": "Synthetic", "key": "SYNTHETIC_API_KEY", "requester": "qa-agent",
                                                              "public_key": base64.urlsafe_b64encode(pub).decode().rstrip("=")})

    def rows(self) -> int:
        import sqlite3
        db = self.tmp / "data" / "secret-drop.sqlite3"
        with sqlite3.connect(db) as c:
            return c.execute("SELECT COUNT(*) FROM requests").fetchone()[0]


class BoundaryOn(GateTest):
    def test_agent_paths_refuse_browsers_and_preflights_before_the_engine(self):
        before = self.rows()
        browser = [{"Origin": "null"}, {"Origin": "https://evil.example"}, {"Origin": f"http://127.0.0.1:{self.fport}"},
                   {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Dest": "empty"}, {"Referer": "https://box.example/notifications/"},
                   {"Cookie": "a=b"}, {"Sec-Fetch-User": "?1"}]
        for h in browser:
            st, body, _ = self.create({"Content-Type": "text/plain", **h})
            self.assertEqual((st, json.loads(body)), (403, {"error": "browser_request_refused"}), h)
            st, body, _ = self.req("POST", "/mcp", {"Content-Type": "text/plain", **h}, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            self.assertEqual(st, 403, h)
            for m, p in (("GET", "/api/v1/requests/" + "a" * 64), ("POST", "/api/v1/requests/" + "a" * 64 + "/pickup"), ("DELETE", "/api/v1/requests/" + "a" * 64)):
                self.assertEqual(self.req(m, p, h)[0], 403, (m, p, h))
        for p in ("/mcp", "/api/v1/requests", "/api/v1/requests/x/pickup"):
            st, body, hdrs = self.req("OPTIONS", p, {"Origin": "null", "Access-Control-Request-Method": "POST"})
            self.assertEqual((st, json.loads(body)), (403, {"error": "preflight_refused"}))
            self.assertFalse(any(k.lower().startswith("access-control-") for k in hdrs))
        self.assertEqual(self.rows(), before, "no refused request reached the relay")

    def test_programs_still_work_including_node_fetch_mode_header(self):
        st, body, _ = self.create({"Sec-Fetch-Mode": "cors"})
        self.assertEqual(st, 201, body)
        made = json.loads(body)
        self.assertIn("#c=", made["request_url"])
        st, body, _ = self.req("POST", "/mcp", {}, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(body)["result"]["tools"])

    def test_recipient_page_and_one_use_link_are_unchanged(self):
        made = json.loads(self.create()[1])
        cap = made["request_url"].split("#c=", 1)[1]
        page = self.req("GET", "/", {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none"})
        self.assertEqual(page[0], 200)
        self.assertIn("frame-ancestors 'none'", page[2]["Content-Security-Policy"])
        self.assertEqual(page[2]["X-Frame-Options"], "DENY")
        self.assertEqual(page[2]["Cross-Origin-Opener-Policy"], "same-origin")
        own = f"http://127.0.0.1:{self.fport}"
        view = self.req("GET", "/api/request", {"X-Secret-Drop-Capability": cap, "Origin": own, "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(view[0], 200, view[1])
        # A framed (opaque) or foreign page cannot read or submit, even holding the link.
        self.assertEqual(self.req("GET", "/api/request", {"X-Secret-Drop-Capability": cap, "Origin": "null"})[0], 403)
        self.assertEqual(self.req("POST", "/api/submit", {"X-Secret-Drop-Capability": cap, "Origin": "null"}, {"x": 1})[0], 403)


class BoundaryOff(GateTest):
    boundary = "0"

    def test_flag_off_behaviour_is_unchanged(self):
        self.assertEqual(self.create({"Origin": "https://evil.example"})[0], 201)   # as before this change
        self.assertNotEqual(self.req("OPTIONS", "/mcp", {"Origin": "null"})[1], b'{"error": "preflight_refused"}')


if __name__ == "__main__":
    unittest.main()
