#!/usr/bin/env python3
"""
NotionVoxBot - A Telegram bot that receives voice messages and logs their details.
Future enhancement: transcribe and send to Notion.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create downloads directory if it doesn't exist
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

class NotionVoxBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up command and message handlers."""
        # Commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Voice message handler
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        
        # Fallback for other messages
        self.application.add_handler(MessageHandler(filters.ALL & ~filters.VOICE, self.handle_other))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = (
            "🎤 Welcome to NotionVoxBot!\n\n"
            "Send me a voice message and I'll log its details for you.\n"
            "Use /help for more information."
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = (
            "🤖 NotionVoxBot Commands:\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n\n"
            "📝 How to use:\n"
            "• Send a voice message to log its details\n"
            "• The bot will download and analyze the voice file\n"
            "• File details will be logged to the console\n\n"
            "🚀 Future features:\n"
            "• Voice transcription\n"
            "• Notion integration"
        )
        await update.message.reply_text(help_message)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages."""
        try:
            voice = update.message.voice
            user = update.message.from_user
            
            # Log voice message details
            logger.info(f"Received voice message from {user.first_name} ({user.id})")
            logger.info(f"Voice details: duration={voice.duration}s, file_size={voice.file_size} bytes")
            
            # Get file info from Telegram
            file_info = await context.bot.get_file(voice.file_id)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_{user.id}_{timestamp}.oga"
            file_path = DOWNLOADS_DIR / filename
            
            # Download the voice file
            await file_info.download_to_drive(file_path)
            
            # Get actual file size after download
            actual_file_size = file_path.stat().st_size
            
            # Log comprehensive details
            details = {
                "user_id": user.id,
                "user_name": f"{user.first_name} {user.last_name or ''}".strip(),
                "username": user.username,
                "message_date": update.message.date,
                "voice_duration": voice.duration,
                "reported_file_size": voice.file_size,
                "actual_file_size": actual_file_size,
                "file_id": voice.file_id,
                "file_unique_id": voice.file_unique_id,
                "mime_type": voice.mime_type,
                "saved_filename": filename,
                "saved_path": str(file_path.absolute())
            }
            
            logger.info("Voice message details:")
            for key, value in details.items():
                logger.info(f"  {key}: {value}")
            
            # Send confirmation to user
            response = (
                f"✅ Voice message received!\n\n"
                f"👤 From: {details['user_name']}\n"
                f"⏱️ Duration: {details['voice_duration']} seconds\n"
                f"📁 File size: {details['actual_file_size']} bytes\n"
                f"💾 Saved as: {filename}\n"
                f"📅 Received at: {details['message_date'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error handling voice message: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error processing your voice message. Please try again."
            )

    async def handle_other(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-voice messages."""
        await update.message.reply_text(
            "🎤 Please send me a voice message to log its details!\n"
            "Use /help for more information."
        )

    def run(self):
        """Start the bot."""
        logger.info("Starting NotionVoxBot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main entry point."""
    # Get bot token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your bot token.")
        return
    
    # Create and run bot
    bot = NotionVoxBot(token)
    bot.run()

if __name__ == "__main__":
    main()
