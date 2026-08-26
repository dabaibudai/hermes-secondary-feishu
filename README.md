# Hermes Secondary Feishu

A native Hermes Agent platform plugin that adds a second Feishu/Lark bot as an independent chat entry.

This repository is dual-purpose:

- **Hermes plugin:** provides the actual second Feishu/Lark runtime channel;
- **Agent Skill:** lets Codex, Claude Code, and other skill-aware agents install, configure, and verify the plugin for a user.

It uses Hermes' built-in Feishu adapter, so the second bot gets the same experience as the primary bot:

- immediate processing reaction;
- Markdown and rich message rendering;
- images and files;
- streamed assistant commentary;
- visible tool progress and long-task updates;
- native `/new`, `/stop`, pairing, session storage, and interruption behavior.

The second app is used only for receiving and replying to chat messages. Hermes still shares the same Agent identity, memory, skills, tools, working directory, model configuration, and primary Feishu credentials used by business tools.

## Requirements

- A recent Hermes Agent build with `hermes plugins` and platform plugin support.
- One additional Feishu or Lark app with bot capability.
- Long-connection event delivery enabled for `im.message.receive_v1`.
- The same message and media permissions normally required by Hermes' built-in Feishu adapter.

## Install

```bash
hermes plugins install dabaibudai/hermes-secondary-feishu --enable
hermes gateway restart
```

## Install as an Agent Skill

```bash
npx skills add dabaibudai/hermes-secondary-feishu
```

Then ask your Agent to install or troubleshoot a second Feishu bot for Hermes. The Skill guides the operation; the Hermes plugin still provides the runtime capability.

The installer prompts for:

- `HERMES_SECONDARY_FEISHU_APP_ID`
- `HERMES_SECONDARY_FEISHU_APP_SECRET`

When installation is initiated from an Agent chat, configure secrets from your own terminal instead of sending them in chat:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py
```

For a private bot, also set the allowed Feishu user Open IDs:

```dotenv
HERMES_SECONDARY_FEISHU_ALLOWED_USERS=ou_xxx,ou_yyy
```

Add optional variables to the Hermes environment file shown by:

```bash
hermes config env-path
```

Alternatively, leave the allowlist empty and use Hermes' normal DM pairing flow.

## Optional settings

```dotenv
HERMES_SECONDARY_FEISHU_DOMAIN=feishu
HERMES_SECONDARY_FEISHU_CONNECTION_MODE=websocket
HERMES_SECONDARY_FEISHU_REQUIRE_MENTION=true
HERMES_SECONDARY_FEISHU_GROUP_POLICY=allowlist
HERMES_SECONDARY_FEISHU_ALLOW_ALL_USERS=false
```

Use `lark` instead of `feishu` for international Lark tenants.

## Verify

```bash
hermes plugins list
hermes gateway status
```

Then send the second bot a task that calls a tool, for example:

> Read a local text file, explain what you found, and show your progress.

You should see a reaction, a short stage message, tool progress, and the final answer. These are visible execution updates, not hidden chain-of-thought.

## Architecture

```text
Secondary Feishu App
        ↓
feishu_secondary platform plugin
        ↓
Hermes Gateway → same Agent / memory / skills / tools
        ↓
Primary Feishu credentials remain available to Feishu business tools
```

Unlike an external HTTP bridge, this plugin runs inside Hermes Gateway and requires no Hermes core patch.

## Security

- Never commit App Secrets to Git.
- Keep the bot private with an allowlist or Hermes pairing.
- The plugin stores no credentials of its own; Hermes reads them from `~/.hermes/.env`.
- Hidden reasoning events are not exposed. Only user-facing commentary and execution progress are rendered.

## Uninstall

```bash
hermes plugins remove hermes-secondary-feishu
hermes gateway restart
```

## License

MIT. Hermes Agent is maintained separately by Nous Research.
