use zed_extension_api as zed;

struct BendExtension;

impl zed::Extension for BendExtension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> zed::Result<zed::Command> {
        // The LSP shim must be on PATH as `bend-lsp` (symlink it from this
        // repo's lsp/bend_lsp.py, e.g. into ~/.bend/bin). We locate it via
        // the worktree's PATH, equivalent to `which bend-lsp`.
        if let Some(path) = worktree.which("bend-lsp") {
            return Ok(zed::Command {
                command: path,
                args: vec![],
                env: vec![],
            });
        }
        // Fallback: BEND_LSP_PATH env var pointing at the script.
        for (k, v) in worktree.shell_env() {
            if k == "BEND_LSP_PATH" {
                return Ok(zed::Command {
                    command: "python3".to_string(),
                    args: vec![v],
                    env: vec![],
                });
            }
        }
        Err("bend-lsp not found on PATH. Symlink lsp/bend_lsp.py as `bend-lsp` into ~/.bend/bin (or another PATH dir), or set BEND_LSP_PATH.".to_string())
    }
}

zed::register_extension!(BendExtension);
