# Quick Start Guide

Get your Gemini Discord bot running in 5 minutes!

## Step 1: Get Your Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name
3. Go to the "Bot" tab
4. Click "Reset Token" and copy the token (save it securely!)
5. **Important**: Scroll down and enable "MESSAGE CONTENT INTENT"
6. Go to the "OAuth2" tab and copy your "Client ID"

## Step 2: Get Your Google AI API Key

1. Visit https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the API key (save it securely!)

## Step 3: Configure the Bot

1. Copy the example config:
   ```bash
   cp config-example.yaml config.yaml
   ```

2. Edit `config.yaml` and fill in:
   ```yaml
   bot_token: "paste_your_discord_token_here"
   client_id: "paste_your_client_id_here"
   gemini_api_key: "paste_your_google_api_key_here"
   ```

3. Add your Discord user ID to admin_ids:
   - Right-click your name in Discord
   - Click "Copy User ID" (enable Developer Mode in Discord settings if you don't see this)
   - Add it to the config:
   ```yaml
   permissions:
     users:
       admin_ids: [YOUR_USER_ID_HERE]
   ```

## Step 4: Run the Bot

### Using Docker (Recommended):
```bash
docker compose up -d
```

### Using Python:
```bash
pip install -r requirements.txt
python bot.py
```

## Step 5: Invite Your Bot

1. Look for the invite URL in the console logs when the bot starts
2. Or manually create it:
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=412317191168&scope=bot
   ```
3. Open the URL in your browser and select your server

## Step 6: Test It!

In your Discord server:
```
@YourBot Hello! Can you help me?
```

## First Commands to Try

```
/model - See which model is active
/prompt view - See the current system prompt
/known set I'm learning to code in Python - Tell the bot about yourself
```

## Common Issues

**Bot doesn't respond:**
- Did you enable MESSAGE CONTENT INTENT?
- Check that config.yaml has the correct tokens
- Make sure the bot has permission to read/send messages in the channel

**Permission denied errors:**
- Add your user ID to admin_ids in config.yaml
- Restart the bot after config changes

**API errors:**
- Verify your Google AI API key is valid
- Check that you have API quota remaining

## Next Steps

- Read the full [README.md](README.md) for detailed features
- Customize the `default_system_prompt` in config.yaml
- Set up user descriptions with `/known`
- Try different models with `/model`

## Need Help?

Check the logs! The bot provides detailed logging in the console:
```bash
# If using Docker:
docker compose logs -f

# If using Python:
# Logs appear in the terminal where you ran the bot
```

## Tips

1. **Start with Flash**: `gemini-2.0-flash-exp` is faster and cheaper
2. **Use threads**: Create threads from messages to organize conversations
3. **Personalize**: Use `/known` to help the bot understand your users
4. **Per-server setup**: Each server can have different models and prompts
5. **Search is automatic**: The bot will search Google when it needs current info

Enjoy your new Gemini-powered Discord bot! 🚀