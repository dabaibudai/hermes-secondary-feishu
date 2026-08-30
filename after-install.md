# Hermes Secondary Feishu installed

1. Securely add one or more bots with `python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py`.
2. Give every bot its own Feishu/Lark App ID and App Secret.
3. Complete bot permissions and long-connection events for every app.
4. Configure all bots first, then restart Hermes Gateway once.

Each bot is an independent chat entry and session namespace. Hermes memory, skills, tools, model configuration, provider quota, working directory, and primary Feishu business credentials remain shared.
