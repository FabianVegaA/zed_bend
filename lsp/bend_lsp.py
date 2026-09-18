#!/usr/bin/env python3
"""Minimal LSP shim for Bend: publishes diagnostics from `bend <file> -o /dev/null`."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

LOC_RE = re.compile(r"^(\d+)\s*\|(.*)$")
LOC_MARK_RE = re.compile(r"^(\d+)\s*\|>")
MAIN_RE = re.compile(r"^[ \t]*def[ \t]+main[ \t]*\(", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*")
DECL_RE = re.compile(r"^[ \t]*(?:def|type|law)[ \t]+([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)?).*")
IMPORT_RE = re.compile(r"^[ \t]*import[ \t]+(\S+)(?:[ \t]+as[ \t]+([A-Za-z_][A-Za-z0-9_']*))?")

KEYWORDS = {
    "def": "Function definition: `def f(x: A) -> B:`",
    "type": "Datatype definition: `type D is Data:` with `K{…}` constructors",
    "law": "Open claim proven by a `def` of the same name",
    "match": "Pattern match on parameters or bound variables",
    "case": "Match branch: `case K{x, _} …:`",
    "do": "Monadic block: `do M<…>:` with `x : A <- m` binds",
    "return": "Wrap a pure value (`return v`) or a block result",
    "for": "Law parameter: `for x: A` (optionally `where P(x)`)",
    "exs": "Law witness the proof must return: `exs z: C`",
    "import": "Module import: `import Base`, `import ./f.bend as M`",
}

_base_cache = {}


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


def base_lookup(name):
    """Signature/docs for a Base name via `bend base <name>` (cached)."""
    if name in _base_cache:
        return _base_cache[name]
    result = None
    for query in (name, name.rsplit(".", 1)[-1]):
        try:
            p = subprocess.run(
                [find_bend(), "base", query],
                capture_output=True, text=True, timeout=10,
            )
            out = (p.stdout or "").strip()
            if p.returncode == 0 and out and not out.startswith("bend:"):
                result = "```bend\n" + out[:2000] + "\n```"
                break
        except Exception:
            pass
    _base_cache[name] = result
    return result


def word_at(text, line, character):
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    row = lines[line]
    if character < 0 or character > len(row):
        return None
    for m in WORD_RE.finditer(row):
        if m.start() <= character <= m.end():
            return m.group(0)
    return None


def local_def(text, name):
    """First `def`/`type`/`law <name>` header line in the given text, if any."""
    short = name.rsplit(".", 1)[-1]
    for line in text.splitlines():
        m = DECL_RE.match(line)
        if m and m.group(1).rsplit(".", 1)[-1] == short:
            return line.strip()
    return None


def file_imports(text):
    """Map of `alias -> path` from `import <path> as <alias>` lines."""
    out = {}
    for line in text.splitlines():
        m = IMPORT_RE.match(line)
        if m and m.group(2):
            out[m.group(2)] = m.group(1)
    return out


def imported_files(text, base):
    """Local `(alias, abspath)` module files imported by the buffer."""
    files = []
    if not base or not os.path.isdir(base):
        return files
    for alias, path in file_imports(text).items():
        if path == "Base" or path.startswith("0x") or not path.startswith("."):
            continue
        full = os.path.normpath(os.path.join(base, path))
        if os.path.isfile(full):
            files.append((alias, full))
    return files


def module_sig(docs, text, base, alias, short):
    """`def <short>` header from the module imported as `alias`, if found."""
    for al, path in imported_files(text, base):
        if al != alias:
            continue
        buf = docs.get("file://" + path)
        if buf is not None:
            sig = local_def(buf, short)
        else:
            sig = None
            try:
                with open(path) as f:
                    sig = local_def(f.read(), short)
            except OSError:
                pass
        if sig:
            return f"{os.path.basename(path)}: `{sig}`"
    return None


def unqualified_sig(docs, text, base, word):
    """`word` header from any locally imported module."""
    for _al, path in imported_files(text, base):
        buf = docs.get("file://" + path)
        if buf is not None:
            sig = local_def(buf, word)
        else:
            sig = None
            try:
                with open(path) as f:
                    sig = local_def(f.read(), word)
            except OSError:
                pass
        if sig:
            return f"{os.path.basename(path)}: `{sig}`"
    return None


def hover(docs, stages, uri, position):
    text = docs.get(uri)
    if text is None:
        return None
    word = word_at(text, position.get("line", 0), position.get("character", 0))
    if not word:
        return None
    if word in KEYWORDS and "." not in word:
        sig = local_def(text, word)
        body = KEYWORDS[word] + (f"\n\nLocal: `{sig}`" if sig else "")
        return {"contents": {"kind": "markdown", "value": body}}
    imports = file_imports(text)
    if word in imports:
        return {"contents": {"kind": "markdown",
                             "value": f"Module `{word}` → `{imports[word]}`"}}
    # Resolve sibling modules against the real file, or the staged copy
    # (which symlinks the real siblings) when it has never been saved.
    base = None
    real = uri.replace("file://", "", 1)
    if os.path.isfile(real):
        base = os.path.dirname(real)
    elif uri in stages:
        base = os.path.dirname(stages[uri])
    if "." in word:
        alias, _, _ = word.partition(".")
        short = word.rsplit(".", 1)[-1]
        if alias in imports and base is not None:
            sig = module_sig(docs, text, base, alias, short)
            if sig:
                return {"contents": {"kind": "markdown", "value": f"```bend\n{sig}\n```"}}
    else:
        sig = local_def(text, word)
        if sig:
            return {"contents": {"kind": "markdown", "value": f"```bend\n{sig}\n```"}}
        if base is not None:
            sig = unqualified_sig(docs, text, base, word)
            if sig:
                return {"contents": {"kind": "markdown", "value": f"```bend\n{sig}\n```"}}
    doc = base_lookup(word)
    if doc:
        return {"contents": {"kind": "markdown", "value": doc}}
    return None


def stage_path(uri, text):
    """Stage buffer text where relative imports resolve.

    Writes the buffer to a fresh temp dir shadowing the real file, with
    siblings (and subdirs) symlinked in so `./x.bend` and `./effs/x.c`
    resolve exactly as they would next to the real file. Returns the
    path to check, or None when staging is impossible.
    """
    if text is None:
        return None
    real = uri.replace("file://", "", 1)
    base = os.path.basename(real) or "file.bend"
    if not base.endswith(".bend"):
        return None
    parent = os.path.dirname(real)
    stage = tempfile.mkdtemp(prefix="bend-lsp-")
    if parent and os.path.isdir(parent):
        try:
            for entry in os.listdir(parent):
                if entry == base:
                    continue
                os.symlink(os.path.join(parent, entry), os.path.join(stage, entry))
        except OSError:
            pass
    dest = os.path.join(stage, base)
    try:
        with open(dest, "w") as f:
            f.write(text)
    except OSError:
        return None
    return dest


def drop_staged(path):
    if path:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def block_start(lines, i):
    """Index of the `Error:` line opening the block around line i."""
    for k in range(i, max(-1, i - 12), -1):
        if lines[k].strip().startswith("Error:"):
            return k
    return max(0, i - 4)


def find_decl_line(text, name):
    """0-based line of `def`/`type`/`law <name>` in text, if any."""
    short = name.strip().rsplit(" ", 1)[-1].rsplit(".", 1)[-1]
    if not short:
        return None
    for idx, line in enumerate(text.splitlines()):
        m = DECL_RE.match(line)
        if m and m.group(1).rsplit(".", 1)[-1] == short:
            return idx
    return None


def error_spots(err, text):
    """Yield (0-based line, message) for each Bend checker error.

    Bend reports two location shapes: bare `Location:` followed by
    `N | …` snippet lines, and `Location: <defname>` followed by snippet
    lines where `N|>` marks the exact line.
    """
    lines = err.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        s = lines[i].strip()
        if s == "Location:" and i + 1 < n:
            m = LOC_RE.match(lines[i + 1])
            if m:
                start = block_start(lines, i)
                yield max(0, int(m.group(1)) - 1), "\n".join(lines[start:i + 2]).strip()[:800]
                i += 2
                continue
            i += 1
            continue
        if s.startswith("Location:"):
            name = s[len("Location:"):].strip()
            target, end = None, i + 1
            for j in range(i + 1, min(i + 12, n)):
                mm = LOC_MARK_RE.match(lines[j])
                if mm:
                    target = max(0, int(mm.group(1)) - 1)
                    end = j + 1
                    break
                if target is None:
                    m2 = LOC_RE.match(lines[j])
                    if m2:
                        target = max(0, int(m2.group(1)) - 1)
            if target is None and text:
                target = find_decl_line(text, name)
            if target is None:
                target = 0
            start = block_start(lines, i)
            yield target, "\n".join(lines[start:end]).strip()[:800]
            i = end
            continue
        i += 1


def check(uri_to_path, uri, text):
    path = uri_to_path.get(uri, uri.replace("file://", "", 1))
    if not os.path.isfile(path) or not path.endswith(".bend"):
        return []
    # `bend <file> -o /dev/null` typechecks without running, but demands
    # a `main`; files without one are checked with plain `bend <file>`
    # (which only checks and never runs when there is no `main`).
    if text is not None and MAIN_RE.search(text):
        args = [find_bend(), path, "-o", os.devnull]
    else:
        args = [find_bend(), path]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        err = (p.stderr or "") + (p.stdout or "")
        if p.returncode == 0:
            return []
        diags = []
        for ln, msg in error_spots(err, text):
            diags.append({
                "range": {"start": {"line": ln, "character": 0},
                          "end": {"line": ln, "character": 1000}},
                "severity": 1, "source": "bend", "message": msg or err.strip()[:500],
            })
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
    docs = {}
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
            reply({"capabilities": {"textDocumentSync": 1, "hoverProvider": True}})
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
                docs[uri] = text
                drop_staged(uri_to_path.get(uri))
                staged = stage_path(uri, text)
                if staged is not None:
                    uri_to_path[uri] = staged
            send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": check(uri_to_path, uri, docs.get(uri))}})
        elif method == "textDocument/hover":
            td = params.get("textDocument", {})
            reply(hover(docs, uri_to_path, td.get("uri", ""), params.get("position", {})))
        else:
            if mid is not None:
                send({"jsonrpc": "2.0", "id": mid, "result": None})


if __name__ == "__main__":
    main()
