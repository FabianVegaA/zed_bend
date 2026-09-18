#!/usr/bin/env python3
"""Minimal LSP shim for Bend: publishes diagnostics from `bend <file> -o /dev/null`."""
import json
import os
import re
import subprocess
import sys
import tempfile

LOC_RE = re.compile(r"^(\d+)\s*\|(.*)$")


def find_bend():
    explicit = os.path.expanduser("~/.bend/bin/bend")
    if os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    return "bend"


def read_msg(buf):
    while True:
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = buf.read(1)
            if not chunk:
                return None
            header += chunk
        head, rest = header.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.decode().split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        body = rest + buf.read(length - len(rest))
        return json.loads(body.decode())


def send(obj):
    data = json.dumps(obj).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
    sys.stdout.buffer.flush()


def check(uri_to_path, uri):
    path = uri_to_path.get(uri, uri.replace("file://", "", 1))
    if not os.path.isfile(path) or not path.endswith(".bend"):
        return []
    try:
        p = subprocess.run(
            [find_bend(), path, "-o", os.devnull],
            capture_output=True, text=True, timeout=30,
        )
        err = (p.stderr or "") + (p.stdout or "")
        if p.returncode == 0:
            return []
        diags = []
        lines = err.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].strip() == "Location:" and i + 1 < len(lines):
                m = LOC_RE.match(lines[i + 1])
                if m:
                    ln = max(0, int(m.group(1)) - 1)
                    msg = "\n".join(lines[max(0, i - 4):i]).strip() or err.strip()[:500]
                    diags.append({
                        "range": {"start": {"line": ln, "character": 0},
                                  "end": {"line": ln, "character": 1000}},
                        "severity": 1, "source": "bend", "message": msg,
                    })
                    i += 2
                    continue
            i += 1
        if not diags:
            diags.append({"range": {"start": {"line": 0, "character": 0},
                                    "end": {"line": 0, "character": 1000}},
                          "severity": 1, "source": "bend",
                          "message": err.strip()[:1000] or "bend check failed"})
        return diags
    except Exception as e:
        return [{"range": {"start": {"line": 0, "character": 0},
                           "end": {"line": 0, "character": 0}},
                 "severity": 2, "source": "bend", "message": str(e)}]


def main():
    buf = sys.stdin.buffer
    uri_to_path = {}
    tmpdir = tempfile.mkdtemp(prefix="bend-lsp-")
    while True:
        msg = read_msg(buf)
        if msg is None:
            break
        method = msg.get("method", "")
        mid = msg.get("id")
        params = msg.get("params", {})

        def reply(result):
            if mid is not None:
                send({"jsonrpc": "2.0", "id": mid, "result": result})

        if method == "initialize":
            reply({"capabilities": {"textDocumentSync": 1}})
        elif method in ("initialized", "$/cancelRequest", "$/setTrace"):
            pass
        elif method == "shutdown":
            reply(None)
        elif method == "exit":
            break
        elif method in ("textDocument/didOpen", "textDocument/didChange",
                        "textDocument/didSave"):
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            text = td.get("text")
            if text is None:
                for c in params.get("contentChanges", []):
                    text = c.get("text", "")
            if uri.endswith(".bend") and text is not None:
                name = uri.rsplit("/", 1)[-1] or "file.bend"
                path = os.path.join(tmpdir, name)
                with open(path, "w") as f:
                    f.write(text)
                uri_to_path[uri] = path
            send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": check(uri_to_path, uri)}})
        else:
            if mid is not None:
                send({"jsonrpc": "2.0", "id": mid, "result": None})


if __name__ == "__main__":
    main()
