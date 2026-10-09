# The MCP never sees a secret: it creates the request with the agent's PUBLIC key and reports status.
# Pickup and decryption stay in the agent's own client (GET /client.py), so plaintext only ever
# exists on the agent's side. That is the whole point of Secret Drop.


def _relay(method, path, payload=None, pickup=None):
    headers = {"Content-Type": "application/json"}
    host = REQUEST.get().get("host")
    if host:
        headers["Host"] = host  # links point at the address the caller used (unless SECRET_DROP_PUBLIC_URL is set)
    auth = REQUEST.get().get("authorization")
    if auth:
        headers["Authorization"] = auth  # the relay's own token, forwarded unchanged
    if pickup:
        headers["X-Secret-Drop-Pickup"] = str(pickup)
    body = None if payload is None else json.dumps(payload).encode()
    url = "http://%s:%d%s" % (up_addr(), UP_PORT, path)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError("relay %d: %s" % (e.code, e.read()[:400].decode("utf-8", "replace")))


@tool("secret_drop_info", "Relay version, limits, and where to download the client that decrypts pickups locally.")
def secret_drop_info():
    d = _relay("GET", "/api/v1/info")
    d["client"] = "GET /client.py on this app's address (check its sha256 against client_sha256)"
    d["skill"] = "GET /SKILL.md on this app's address"
    return d


@tool("request_secret", "Create a one-time link the human opens to type a credential. It is encrypted to your public key; "
      "send the human the full request_url and keep pickup_secret private. Decrypt with the Secret Drop client, never here.",
      {"key": {"type": "string", "description": "Env var to fill, uppercase, ending in _API_KEY, _TOKEN, _SECRET, _PASSWORD, _PASS, _URL, _URI or _CREDENTIAL"},
       "label": {"type": "string", "description": "What the human is asked for, e.g. 'OpenAI API key'"},
       "requester": {"type": "string", "description": "How you are shown to the human, e.g. 'Hermes on demobox'"},
       "public_key": {"type": "string", "description": "Your X25519 public key, base64url (from the client's keygen)"},
       "ttl_minutes": {"type": "integer", "description": "5 to 300, default 120"}},
      ["key", "label", "requester", "public_key"])
def request_secret(key, label, requester, public_key, ttl_minutes=None):
    payload = {"key": key, "label": label, "requester": requester, "public_key": public_key}
    if ttl_minutes:
        payload["ttl_minutes"] = int(ttl_minutes)
    return _relay("POST", "/api/v1/requests", payload)


@tool("secret_status", "Has the human submitted yet? Returns pending, submitted, picked up, expired or cancelled.",
      {"request_id": {"type": "string"}, "pickup_secret": {"type": "string"}}, ["request_id", "pickup_secret"])
def secret_status(request_id, pickup_secret):
    return _relay("GET", "/api/v1/requests/" + urllib.parse.quote(str(request_id), safe=""), pickup=pickup_secret)


@tool("cancel_secret_request", "Cancel a request that is no longer needed so its link stops working.",
      {"request_id": {"type": "string"}, "pickup_secret": {"type": "string"}}, ["request_id", "pickup_secret"])
def cancel_secret_request(request_id, pickup_secret):
    return _relay("DELETE", "/api/v1/requests/" + urllib.parse.quote(str(request_id), safe=""), pickup=pickup_secret)
