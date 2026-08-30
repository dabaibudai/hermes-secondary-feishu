# Hermes Secondary Feishu

A native Hermes Agent platform plugin that adds multiple Feishu/Lark bots as independent chat entries.

This repository is dual-purpose:

- **Hermes plugin:** provides the actual second Feishu/Lark runtime channel;
- **Agent Skill:** lets Codex, Claude Code, and other skill-aware agents install, configure, and verify the plugin for a user.

It uses Hermes' built-in Feishu adapter, so every additional bot gets the same experience as the primary bot:

- immediate processing reaction;
- Markdown and rich message rendering;
- images and files;
- streamed assistant commentary;
- visible tool progress and long-task updates;
- native `/new`, `/stop`, pairing, session storage, and interruption behavior.

Each additional app is used only for receiving and replying to chat messages. Bots have independent session namespaces while sharing the same Agent identity, memory, skills, tools, working directory, provider credentials/quota, and primary Feishu credentials used by business tools. A bot inherits Hermes' global model unless an optional per-bot model route is configured.

The plugin suppresses Hermes' generic `No home channel is set` notice in secondary chats. Secondary bots are chat-only by default, while cron and cross-platform delivery remain on the primary bot. Use `/sethome` in a secondary chat only when that routing change is intentional.

## Requirements

- A recent Hermes Agent build with `hermes plugins` and platform plugin support.
- One unique Feishu or Lark app for every additional bot.
- Long-connection event delivery enabled for `im.message.receive_v1`.
- The same message and media permissions normally required by Hermes' built-in Feishu adapter.

## Install

```bash
hermes plugins install dabaibudai/hermes-secondary-feishu --enable
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --name hermes2
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --name hermes3
hermes gateway restart
```

## Install as an Agent Skill

```bash
npx skills add dabaibudai/hermes-secondary-feishu
```

Then ask your Agent to install or troubleshoot a second Feishu bot for Hermes. The Skill guides the operation; the Hermes plugin still provides the runtime capability.

Configure credentials with the hidden terminal prompt on the host or over SSH:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --name hermes2
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --name hermes3
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --list
```

The script writes an instance list and separate credentials:

```dotenv
HERMES_SECONDARY_FEISHU_BOTS=hermes2,hermes3
HERMES_SECONDARY_FEISHU_HERMES2_APP_ID=cli_xxx
HERMES_SECONDARY_FEISHU_HERMES3_APP_ID=cli_yyy
```

App Secrets are stored beside these variables but are never printed. Version 1 singular `HERMES_SECONDARY_FEISHU_*` variables remain supported as Hermes2 for backward compatibility.

Remove one bot with:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --remove hermes3
```

## Per-bot model routing

Keep the primary Hermes model unchanged while assigning a cheaper or specialized model to one secondary bot:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py \
  --set-model hermes2 \
  --provider kimi-coding \
  --model kimi-for-coding
```

Use provider and API model IDs, not product or marketing names. The route is persistent across `/new` and Gateway restarts. A manual `/model` command temporarily overrides it for the current session; `/new` returns that bot to its configured route. Do not use `/model ... --global` for this purpose because it changes the primary and every inheriting bot.

Remove the per-bot route and return to Hermes' global model with:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py \
  --clear-model hermes2
```

## Optional settings

```dotenv
HERMES_SECONDARY_FEISHU_HERMES3_DOMAIN=feishu
HERMES_SECONDARY_FEISHU_HERMES3_CONNECTION_MODE=websocket
HERMES_SECONDARY_FEISHU_HERMES3_REQUIRE_MENTION=true
HERMES_SECONDARY_FEISHU_HERMES3_GROUP_POLICY=allowlist
HERMES_SECONDARY_FEISHU_HERMES3_ALLOW_ALL_USERS=false
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
Feishu Apps: Hermes2 / Hermes3 / Hermes4
                  ↓
Platforms: feishu_secondary / feishu_hermes3 / feishu_hermes4
                  ↓
Hermes Gateway → independent sessions, shared Agent / memory / skills / tools
                  ↳ optional persistent provider/model route per bot
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

When installation is controlled from the primary Hermes chat, do not run `hermes gateway restart` directly. Schedule the detached helper as the final tool call, then send the checkpoint response immediately:

```bash
python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/deferred_restart.py
```

## License

MIT. Hermes Agent is maintained separately by Nous Research.
