# Bend for Zed

Zed extension for the [Bend programming language](https://bend-lang.com)
(v2 syntax): syntax highlighting, code outline, snippets and inline
diagnostics.

## Features

- Tree-sitter grammar for Bend v2 (`def`, `type … is …`, `law`,
  `match`/`case`, `do`-notation, rewrites, GPU calls, …). Grammar source:
  [FabianVegaA/tree-sitter-bend](https://github.com/FabianVegaA/tree-sitter-bend).
- Language server shim (`bend-lsp`) reporting `bend` check errors as
  diagnostics without running your code (`bend <file> -o /dev/null`), plus
  hover with signatures from `bend base` and local `def` headers.
- Snippets for common shapes (`bend-hello`, `bend-def`, `bend-match`).

## Requirements

- The `bend` binary (install via
  `curl -fsSL https://bend-lang.com/install.sh | sh`). The extension looks
  for it at `~/.bend/bin/bend`, then on `PATH`.
- The `bend-lsp` shim on your `PATH` (the language server entry point).
  Symlink it from this repo, e.g.:
  `ln -s <repo>/lsp/bend_lsp.py ~/.bend/bin/bend-lsp`.
  Alternatively set `BEND_LSP_PATH` to the script location.

## Install as a dev extension

Zed → Extensions → `Install Dev Extension` → select this directory.

## Publishing

Releases go through
[zed-industries/extensions](https://github.com/zed-industries/extensions)
as submodule `extensions/bend`. Keep `version` in `extension.toml` and the
registry entry in sync.

## License

BSD 3-Clause, see [LICENSE](./LICENSE).
