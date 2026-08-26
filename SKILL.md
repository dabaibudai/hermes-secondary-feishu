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
3. From a Hermes chat, install non-interactively so the command cannot hang on credential prompts:

   ```bash
   hermes plugins install dabaibudai/hermes-secondary-feishu --enable </dev/null
   ```

4. Never request the App Secret in chat. Ask the user to run this command in their own terminal; it hides the Secret and preserves the primary Feishu variables:

   ```bash
   python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py
   ```

   Stop and wait for the user to confirm that configuration was saved.
5. Guide the user through this exact Feishu/Lark developer-console checklist:

   - enable the **Bot** capability;
   - grant `im:message`, `im:message:send`, and `im:resource` permissions;
   - choose **long connection / WebSocket** event delivery;
   - subscribe to `im.message.receive_v1`;
   - for approval buttons and card interactions, enable **Interactive Card** and subscribe to `card.action.trigger`;
   - publish a new app version and make it available to the intended user or tenant.

   Stop and wait for the user to confirm each incomplete console item. Do not claim that the app is ready based only on local configuration.
6. If the user left the allowlist blank, tell them to send any DM to the second bot. When it returns a pairing code, approve it with:

   ```bash
   hermes pairing approve feishu_secondary PAIRING_CODE
   ```

   Never guess a code. Run `hermes pairing list` if the user reports that no code appeared.
7. If the user already knows their Feishu Open ID, they can instead set an allowlist in the Hermes environment file returned by `hermes config env-path`:

   ```dotenv
   HERMES_SECONDARY_FEISHU_ALLOWED_USERS=ou_xxx
   ```

8. Restart the gateway only after the credentials and developer-console checklist are complete, then verify with:

   ```bash
   hermes plugins list
   hermes gateway status
   ```

## Acceptance

Run these checks in order and report the first failing stage instead of continuing blindly:

1. Send `你好`. Expect one immediate reaction and exactly one answer.
2. Send `/new`. Expect confirmation that a fresh `feishu_secondary` session started.
3. Ask it to read a harmless local text file. Expect visible commentary, tool progress, and one final answer rendered as Markdown or a rich card.
4. Send one image. Expect Hermes to acknowledge or inspect the image without an unsupported-file error.

Success requires all of the following:

- the bot reacts immediately;
- Markdown or rich-card output renders correctly;
- visible commentary and tool progress appear during execution;
- the final answer arrives once, not multiple times;
- `/new` starts a fresh session;
- the primary Feishu app remains available to Hermes business tools.

If loading fails, inspect the gateway logs first. If replies are duplicated, check for an older external bridge or another gateway using the same App ID before changing plugin code.
