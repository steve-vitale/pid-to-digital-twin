"""Minimal client for the Ignition 8.3 gateway REST API, used by the build and verify scripts.

Credentials never live in this repo. Set them in the environment, or point IGNITION_ENV_FILE at a private file of
KEY=VALUE lines:
  IGNITION_URL        e.g. https://localhost:8043 (API keys are created "require secure connections", so HTTPS)
  IGNITION_API_TOKEN  "<name>:<secret>" from Platform > Security > API Keys
  IGNITION_CA_FILE    optional: the gateway's certificate. Without it, certificate checks are skipped ONLY when the
                      gateway is on localhost (the trial gateway's self-signed certificate); any other host refuses.
"""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request


def _load_env():
    path = os.environ.get("IGNITION_ENV_FILE")
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


class Gateway:
    def __init__(self):
        _load_env()
        self.url = os.environ.get("IGNITION_URL", "https://localhost:8043").rstrip("/")
        self.token = os.environ.get("IGNITION_API_TOKEN")
        if not self.token:
            raise SystemExit("IGNITION_API_TOKEN is not set (see scripts/ignition/gw.py)")
        host = urllib.parse.urlparse(self.url).hostname
        ca = os.environ.get("IGNITION_CA_FILE")
        if ca:
            self.ctx = ssl.create_default_context(cafile=ca)
        elif host in ("localhost", "127.0.0.1"):
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        else:
            raise SystemExit(f"refusing to skip certificate checks for non-local gateway {host}; set IGNITION_CA_FILE")

    def request(self, method, path, body=None, raw=False, ctype="application/json"):
        data = None
        headers = {"X-Ignition-API-Token": self.token, "Accept": "application/json"}
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            headers["Content-Type"] = ctype
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as r:
                payload = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            payload, status = e.read(), e.code
        if raw:
            return status, payload
        try:
            return status, json.loads(payload) if payload else None
        except ValueError:
            return status, payload.decode("utf-8", "replace")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body, **kw)

    def delete(self, path, body=None, **kw):
        return self.request("DELETE", path, body, **kw)
