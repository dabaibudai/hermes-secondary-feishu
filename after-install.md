# Hermes Secondary Feishu installed

1. Confirm the secondary Feishu app has bot capability and long-connection events enabled.
2. Set `HERMES_SECONDARY_FEISHU_ALLOWED_USERS` in `~/.hermes/.env`, or pair the first DM through Hermes' normal pairing flow.
3. Run `hermes gateway restart`.

The secondary app is only a chat transport. Hermes memory, skills, tools, model configuration, and primary Feishu tool credentials remain shared.
