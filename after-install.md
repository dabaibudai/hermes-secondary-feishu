# Hermes Secondary Feishu installed

1. Securely add one or more bots with `python3 ~/.hermes/plugins/hermes-secondary-feishu/scripts/configure.py`.
2. Give every bot its own Feishu/Lark App ID and App Secret.
3. Complete bot permissions and long-connection events for every app.
4. Optionally assign a persistent provider/model route with `configure.py --set-model NAME --provider PROVIDER_ID --model MODEL_ID`.
5. Configure all bots first, then restart Hermes Gateway once.

Each bot is an independent chat entry and session namespace. Hermes memory, skills, provider credentials/quota, tools, working directory, and primary Feishu business credentials remain shared. Per-bot model routes do not change the primary conversation model.
