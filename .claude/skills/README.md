# Agent skills

Vendored from [github/awesome-copilot](https://github.com/github/awesome-copilot) at commit
`cb64ad12e32737ae764becd6885462e9b4c7cb00` (MIT License, see [`LICENSE`](LICENSE)). Every file
except this README is byte-identical to upstream `skills/<name>/` (and `LICENSE`). Do not edit them
here; refresh from upstream instead.

Claude Code loads `.claude/skills/` as project skills, and GitHub Copilot (cloud agent, CLI, VS Code
agent mode) reads it too. Where a skill disagrees with `CLAUDE.md` ("Vendored Agent Skills"), the
repo's rules win.

Not vendored:

- `github-release` and `conventional-commit`: they conflict with this repo's release and commit
  conventions.
- `pytest-coverage`: its fixed 100% target and loop conflict with this repo's own coverage settings.
- `security-review`: it shares its name with Claude Code's built-in `/security-review`.

| Skill                                | Purpose                                                                                |
| ------------------------------------ | -------------------------------------------------------------------------------------- |
| `dependabot`                         | Configuring `dependabot.yml` and working with Dependabot PRs                           |
| `docs-sync-audit`                    | Read-only audit of documentation drift against the code                                |
| `github-actions-hardening`           | Security review of `.github/workflows/*.yml`; reports, never edits                     |
| `mcp-implementation-security-review` | Security review of the MCP server implementation; reports, never edits                 |
| `mcp-release-qa`                     | Pre-release QA of the MCP server over a real protocol session                          |
| `mcp-security-audit`                 | Audit of MCP client configuration (`.mcp.json` etc.) for secrets and unpinned packages |
| `test-gap-audit`                     | Read-only audit of missing or weak tests                                               |
