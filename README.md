# NotionVoxBot

A Telegram bot that receives voice messages, logs their details, and will eventually transcribe them and send to Notion.

## Features

- 🎤 Receives voice messages from Telegram
- 📊 Logs comprehensive voice message details
- 💾 Downloads and stores voice files locally
- 📝 Future: Voice transcription and Notion integration

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Telegram bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
   ```

### 3. Run the Bot

```bash
python bot.py
```

## Bot Commands

- `/start` - Welcome message and introduction
- `/help` - Show available commands and usage instructions

## What the Bot Logs

When you send a voice message, the bot logs:

- User information (ID, name, username)
- Voice message metadata (duration, file size, MIME type)
- File IDs (both regular and unique)
- Timestamp of message
- Local file path where voice is saved

## File Structure

```
notionvoxbot/
├── bot.py              # Main bot application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── .env               # Your actual environment variables (not in git)
├── .gitignore         # Git ignore rules
├── downloads/         # Directory for downloaded voice files
└── README.md          # This file
```

## Future Enhancements

- 🎯 Voice transcription using OpenAI Whisper or similar
- 📔 Integration with Notion API
- 🔄 Database storage for voice message metadata
- 🎛️ Configuration options for different users
- 🚀 Deployment options (Docker, cloud platforms)

## Development

The bot uses the `python-telegram-bot` library version 20.x with async/await support.

Voice files are saved in OGG format as provided by Telegram's API.
