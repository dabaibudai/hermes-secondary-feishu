---
name: hermes-secondary-feishu-installer
description: Install, configure, verify, or troubleshoot the Hermes Secondary Feishu plugin when a user wants a second Feishu/Lark bot to share the same Hermes memory, skills, tools, and model while keeping primary Feishu business credentials unchanged.
---

# Hermes Secondary Feishu Installer

Install the native `dabaibudai/hermes-secondary-feishu` platform plugin. The second Feishu/Lark app is only a chat transport; Hermes continues to share the existing Agent identity, sessions, memory, skills, tools, working directory, and model configuration.

## Invariants

- Never replace or delete the primary `FEISHU_APP_ID` or `FEISHU_APP_SECRET`.
- Store the second app only in `HERMES_SECONDARY_FEISHU_APP_ID` and `HERMES_SECONDARY_FEISHU_APP_SECRET`.
- Do not patch Hermes core files. This repository is a native Hermes platform plugin.
- Ask before restarting a live gateway if it may interrupt active work.
- Never print or commit App Secrets.

## Install

1. Confirm that `hermes plugins install --help` works. If it does not, explain that Hermes must be upgraded to a build with platform-plugin support.
2. Check whether another bridge or process already consumes the same secondary Feishu App ID. Stop or migrate that process before enabling this plugin, otherwise one message may receive duplicate replies.
3. Run:

   ```bash
   hermes plugins install dabaibudai/hermes-secondary-feishu --enable
   ```

4. Let the installer securely prompt for the secondary App ID and App Secret. Do not place either value in chat logs or shell history.
5. In the Feishu developer console, confirm bot capability, long-connection event delivery, `im.message.receive_v1`, and the message/media permissions required by Hermes' built-in Feishu adapter.
6. For a private bot, add the user's Open ID to the Hermes environment file returned by `hermes config env-path`:

   ```dotenv
   HERMES_SECONDARY_FEISHU_ALLOWED_USERS=ou_xxx
   ```

   Alternatively, leave the allowlist empty and use Hermes' normal DM pairing flow.
7. Restart the gateway after receiving authorization, then verify with:

   ```bash
   hermes plugins list
   hermes gateway status
   ```

## Acceptance

Send the second bot a small tool-using task. Success requires all of the following:

- the bot reacts immediately;
- Markdown or rich-card output renders correctly;
- visible commentary and tool progress appear during execution;
- the final answer arrives once, not multiple times;
- `/new` starts a fresh session;
- the primary Feishu app remains available to Hermes business tools.

If loading fails, inspect the gateway logs first. If replies are duplicated, check for an older external bridge or another gateway using the same App ID before changing plugin code.
