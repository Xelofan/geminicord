# Gemini Discord Bot

A powerful Discord bot powered by Google's Gemini 2.5 AI models with advanced features like per-server personalization, Google Search integration, and automatic user profiling.

## Features

### 🤖 Gemini 2.5 Integration
- **Multiple Models**: Choose between Gemini 2.0 Flash (Experimental) and Gemini Experimental 1206
- **Google Search Grounding**: Answers enhanced with real-time web search
- **Vision Support**: Process images from Discord attachments and external URLs
- **Streaming Responses**: Real-time message updates as the AI generates responses

### 💬 Smart Conversation System
- **Reply-based Chat**: Start conversations with @ mentions, continue with replies
- **Message Threading**: Create threads from any message to branch conversations
- **DM Support**: Private conversations in direct messages
- **Automatic Context**: Back-to-back messages from the same user are chained together

### 🎨 Per-Server Customization
- **Server-Specific Models**: Each server can use a different Gemini model
- **Custom System Prompts**: Tailor the bot's personality per server
- **User Profiles**: Automatic user discovery and personalization
- **Persistent Storage**: All settings saved in JSON files

### 👤 User Personalization
- **Automatic Discovery**: Bot remembers users as they interact
- **User Descriptions**: Users can describe themselves for personalized responses
- **Display Names**: Bot uses Discord display names naturally in conversation
- **Privacy Controls**: Users can view and remove their own data

### 🔧 Admin Tools
- `/model` - Switch between Gemini models per server
- `/prompt` - View, set, or reset the system prompt
- `/known` - Manage user personalization settings

## Setup Instructions

### Prerequisites
1. **Discord Bot Token**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to the "Bot" tab and create a bot
   - Enable "MESSAGE CONTENT INTENT" under Privileged Gateway Intents
   - Copy the bot token

2. **Google AI API Key**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Copy the API key

### Installation

#### Option 1: Docker (Recommended)

1. Clone the repository:
```bash
git clone <your-repo-url>
cd gemini-discord-bot
```

2. Copy and configure the config file:
```bash
cp config.yaml config.yaml
```

3. Edit `config.yaml` and add:
   - Your Discord bot token
   - Your Discord client ID (from OAuth2 tab)
   - Your Google AI API key
   - Admin user IDs

4. Run with Docker:
```bash
docker compose up -d
```

#### Option 2: Local Python

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `config.yaml` as above

3. Run the bot:
```bash
python bot.py
```

### Bot Invitation

After starting the bot, check the console logs for the invite URL, or construct it manually:
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=412317191168&scope=bot
```

## Configuration Guide

### Discord Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `bot_token` | Your Discord bot token | Required |
| `client_id` | Your Discord application client ID | Required |
| `status_message` | Custom status message for the bot | "Powered by Gemini 2.5" |

### Gemini Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `gemini_api_key` | Your Google AI API key | Required |
| `default_model` | Default model for new servers | "gemini-2.0-flash-exp" |
| `default_system_prompt` | Default personality prompt | See config.yaml |
| `enable_search_grounding` | Enable Google Search integration | true |

### Limits

| Setting | Description | Default |
|---------|-------------|---------|
| `max_text` | Maximum characters per message | 100,000 |
| `max_images` | Maximum images per message | 5 |
| `max_messages` | Maximum messages in conversation | 25 |
| `max_urls` | Maximum image URLs to extract | 3 |
| `max_user_description_length` | Maximum user description length | 500 |

### Permissions

Configure who can use the bot:

```yaml
permissions:
  users:
    admin_ids: [123456789]  # Bot admins
    allowed_ids: []  # Empty = everyone allowed
    blocked_ids: []  # Specific blocked users
  roles:
    allowed_ids: []  # Allowed role IDs
    blocked_ids: []  # Blocked role IDs
  channels:
    allowed_ids: []  # Allowed channel/category IDs
    blocked_ids: []  # Blocked channel/category IDs
```

## Commands

### `/model [model]`
**Admin Only** - View or switch the current Gemini model

- Without argument: Shows current model
- With argument: Switches to specified model
- **Scope**: Per-server (each server has its own model setting)
- **Models**: 
  - `gemini-2.0-flash-exp` - Fast and efficient
  - `gemini-exp-1206` - Advanced experimental model

### `/prompt <action> [text]`
Manage the system prompt

**Actions:**
- `view` - View current system prompt (anyone can use)
- `set` - Set new system prompt (admin only)
- `reset` - Reset to default prompt (admin only)

**Scope**: Per-server

**Examples:**
```
/prompt view
/prompt set You are a friendly coding assistant. Always provide examples.
/prompt reset
```

### `/known <action> [description] [user]`
Manage user personalization

**Actions:**
- `set` - Set description for yourself or another user
- `view` - View description for yourself or another user
- `remove` - Remove description

**Permissions:**
- Anyone can manage their own description
- Admins can manage other users' descriptions
- Anyone can view any user's description

**Examples:**
```
/known set I'm a Python developer who loves clean code
/known view
/known view @JohnDoe
/known set Prefers detailed technical explanations @JaneSmith (admin only)
/known remove
```

## Usage Examples

### Starting a Conversation

In a server:
```
@BotName Hello! Can you help me with Python?
```

In DMs:
```
Hello! Can you help me with Python?
```

### Continuing a Conversation

Simply reply to any message in the conversation chain:
```
[Reply to bot's message] Can you explain that more?
```

### Using Images

1. **Upload directly**: Attach image to your message
2. **External URLs**: Include image URLs in your message
```
@BotName What's in this image? https://example.com/image.jpg
```

### Branching Conversations

Create a thread from any message to start a new conversation branch while keeping the original intact.

## Data Storage

### Server Data Structure

Each server's data is stored in `server_data/{server_id}.json`:

```json
{
  "model": "gemini-2.0-flash-exp",
  "system_prompt": "Custom prompt here...",
  "users": {
    "user_id": {
      "display_name": "Username",
      "description": "User's self-description",
      "first_seen": "2025-10-07T12:34:56Z",
      "last_updated": "2025-10-07T12:34:56Z"
    }
  }
}
```

### DM Data Structure

DM conversations are stored in `server_data/dm_{user_id}.json` with a similar structure.

## Features in Detail

### Google Search Grounding

When enabled, the bot can search the web to provide up-to-date information:
- Automatically activates when needed
- Provides source citations
- Configurable in `config.yaml`

### Automatic User Discovery

The bot automatically:
1. Detects new users in conversations
2. Records their display name
3. Updates names when changed
4. Tracks first interaction and last update

### Streaming Responses

Responses appear in real-time:
- Orange embed = generating
- Green embed = complete
- Automatically splits long responses
- Fixed: No more mid-stream cutoffs!

## License

This project is open source. Please check the repository for license details.

## Credits

Based on [llmcord](https://github.com/jakobdylanc/llmcord) by jakobdylanc, rebuilt from the ground up for Google Gemini with enhanced personalization features.
