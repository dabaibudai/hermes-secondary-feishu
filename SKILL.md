---
name: hermes-secondary-feishu-installer
description: Install, configure, verify, or troubleshoot one or more secondary Feishu/Lark chat bots for Hermes while sharing the same memory, skills, tools, model, and primary Feishu business credentials.
---

# Hermes Secondary Feishu Installer

Install the native `dabaibudai/hermes-secondary-feishu` platform plugin. Hermes2, Hermes3, and later bots are independent chat entries and session namespaces. They share the existing Agent identity, memory, skills, tools, working directory, model configuration, and provider quota.

## Invariants

- Never replace or delete the primary `FEISHU_APP_ID` or `FEISHU_APP_SECRET`.
- Give every bot a unique Feishu/Lark App ID. Reusing one App ID across connections causes conflicts or duplicate replies.
- Store credentials only in bot-specific `HERMES_SECONDARY_FEISHU_<BOT>_*` variables created by the configuration script.
- Do not patch Hermes core files. This repository is a native Hermes platform plugin.
- Ask before restarting a live gateway if it may interrupt active work.
- Never print, echo, quote, summarize, or commit App Secrets.

## Install

1. Confirm that `hermes plugins install --help` works. If it does not, explain that Hermes must be upgraded to a build with platform-plugin support.
2. Ask how many chat entries the user wants and choose stable names such as `hermes2`, `hermes3`, and `hermes4`. Check whether another bridge or process already consumes any intended App ID. Stop or migrate that process before enabling this plugin.
3. From a Hermes chat, install non-interactively so the command cannot hang on credential prompts:

   ```bash
   hermes plugins install dabaibudai/hermes-secondary-feishu --enable </dev/null
   ```

4. Ask the user to provide the secondary App ID and App Secret, then give them the hidden-input command for the Hermes host or an SSH terminal:

   ```bash
   python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --name hermes2
   ```

   Keep credential transport user-controlled. If credentials are already available to the Agent, use `configure.py --secret-stdin` so the Secret is not placed in shell arguments, and never repeat it in output.

   Use only the names the user requested. Run `python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py --list` to verify that every bot reports `credentials=ready`. Configure all bots before restarting the Gateway.
5. Guide the user through this exact Feishu/Lark developer-console checklist for **every app**:

   - enable the **Bot** capability;
   - grant `im:message`, `im:message:send`, and `im:resource` permissions;
   - choose **long connection / WebSocket** event delivery;
   - subscribe to `im.message.receive_v1`;
   - for approval buttons and card interactions, enable **Interactive Card** and subscribe to `card.action.trigger`;
   - publish a new app version and make it available to the intended user or tenant.

   Stop and wait for the user to confirm each incomplete console item. Do not claim that the app is ready based only on local configuration.
6. If the user left an allowlist blank, tell them to send a DM to that bot. When it returns a pairing code, approve it with the platform printed by the configuration script:

   ```bash
   hermes pairing approve feishu_secondary PAIRING_CODE
   hermes pairing approve feishu_hermes3 PAIRING_CODE
   ```

   Never guess a code. Run `hermes pairing list` if the user reports that no code appeared.
   On that first DM, Hermes may also send `No home channel is set`. This is a generic Hermes onboarding notice, not an error and not a required setup step. Secondary bots are chat-only by default: tell the user to ignore the notice and do not run `/sethome` unless they explicitly want cron results delivered to that secondary chat.
7. If the user already knows their Feishu Open ID, the configuration script can store the allowlist separately for each bot. Do not use the primary `FEISHU_ALLOWED_USERS` variable for secondary bots.

8. Restart the gateway only after the credentials and developer-console checklist are complete.

   All Feishu bots share the same Hermes Gateway. Calling `hermes gateway restart` from the live Hermes conversation creates a self-wait: Gateway waits for the current agent to finish while that agent waits for Gateway to restart. Never call it directly from the conversation.

   Instead, schedule the plugin's external restart helper as the **last tool call**:

   ```bash
   python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/deferred_restart.py
   ```

   The helper waits until Gateway logs that the current response is being sent, then restarts from a detached process. Immediately after scheduling, send the final checkpoint response and run no more tools. Before scheduling:

   - tell the user that Hermes1 will be offline for several seconds;
   - record which installation steps are complete and that acceptance is the next stage;
   - ask for explicit confirmation to schedule the restart;
   - tell the user to send `继续验收` after Hermes1 reconnects.

   When the user sends `继续验收`, do not repeat installation or request credentials again. Check the plugin and gateway status, then continue from **Acceptance**. If no reconnect occurs within three minutes, the helper cancels the restart rather than killing an unresolved session.

   Verify with:

   ```bash
   hermes plugins list
   hermes gateway status
   ```

## Acceptance

Run these checks for every configured bot. Report the first failing bot and stage instead of continuing blindly:

1. Send `你好`. Expect one immediate reaction and exactly one answer.
2. Send `/new`. Expect a fresh session under that bot's platform (`feishu_secondary` for Hermes2, `feishu_hermes3` for Hermes3, and so on).
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

## Operational Blind Spots

- More bots create more conversations, not separate Agents. Memory, tools, model, provider quota, filesystem, and Gateway availability are shared.
- Concurrent chats can edit the same files or operate the same external account. Ask before destructive or conflicting work; separate working directories when tasks may collide.
- Every bot expands the access surface. Use separate allowlists or pairing grants and review them when a bot changes owners.
- Secondary bots are chat-only by default. Ignore their one-time `No home channel is set` notice; keep cron and cross-platform delivery on the primary bot unless the user explicitly requests otherwise.
- One Gateway restart interrupts all bots. Configure or update several bots together, then restart once.
- One broken App should be diagnosed by its platform name and App ID without printing secrets. Do not disable healthy bots unless shared Gateway startup itself fails.
