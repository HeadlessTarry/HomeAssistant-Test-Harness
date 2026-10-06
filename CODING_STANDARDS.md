# 📐 Coding Standards

Judgement calls for the Standards reviewer in `/code-review`. Each rule names its scope; flag a diff that breaks one, quoting the rule's name.
Mechanical rules live in [.pre-commit-config.yaml](.pre-commit-config.yaml) (see [docs/development.md](docs/development.md#running-checks)) and stay out of this file.

## 🤖 Agent-facing docs

Scope: `AGENTS.md`, `.claude/skills/**`, `docs/**`.

- **Positive phrasing.** Apply the Negation guidance in the `writing-for-agents` skill.
- **Actionable instructions.** Every instruction is one the reading agent can carry out from inside its own session, with the tools it has.
- **Safe defaults.** A command shown to an agent leads with its lightest form, heavier variants opt-in;
  `./setup_dev_env.sh --skip-checks` in [.claude/skills/verify/SKILL.md](.claude/skills/verify/SKILL.md) is the reference example.

## 📚 All docs

Scope: every `*.md`.

- **Single source of truth.** Apply the Pruning guidance in the `writing-for-agents` skill: link to the canonical doc, file, or directory.
- **Present state.** Describe what the repo contains today. Mention future features only as a scope limit ("scope is limited to X; others may follow").
- **ADR limitations.** Each ADR in `docs/adr/` states what its decision covers and its known limitations, in its Consequences section.

## 🔐 Config and permissions

Scope: `.github/workflows/**`, skill frontmatter.

- **Least privilege.** Every permission, tool grant, or allowed command traces to a step that uses it.
