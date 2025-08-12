#!/usr/bin/env python3
"""
NotionVoxBot - A Telegram bot that receives voice messages and logs their details.
Future enhancement: transcribe and send to Notion.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
import tempfile

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from openai import OpenAI
from pydub import AudioSegment
from notion_client import Client as NotionClient

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

class WhisperTranscriber:
    """Handles voice transcription using OpenAI Whisper API."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. Transcription will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
    
    def convert_oga_to_mp3(self, oga_path: Path) -> Path:
        """Convert OGA file to MP3 format for Whisper API compatibility."""
        try:
            # Load the OGA file
            audio = AudioSegment.from_ogg(oga_path)
            
            # Create MP3 filename
            mp3_path = oga_path.with_suffix('.mp3')
            
            # Export as MP3
            audio.export(mp3_path, format="mp3")
            
            logger.info(f"Converted {oga_path} to {mp3_path}")
            return mp3_path
            
        except Exception as e:
            logger.error(f"Error converting audio file: {e}")
            raise
    
    def transcribe_audio(self, audio_path: Path) -> dict:
        """Transcribe audio file using OpenAI Whisper API."""
        if not self.client:
            return {
                "success": False,
                "error": "OpenAI API key not configured",
                "transcript": None
            }
        
        try:
            # Convert OGA to MP3 if needed
            if audio_path.suffix.lower() == '.oga':
                audio_path = self.convert_oga_to_mp3(audio_path)
            
            # Transcribe using Whisper API
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            logger.info(f"Successfully transcribed audio: {len(transcript)} characters")
            
            return {
                "success": True,
                "transcript": transcript,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcript": None
            }

class NotionIntegrator:
    """Handles integration with Notion API for saving voice memos."""
    
    def __init__(self):
        notion_token = os.getenv("NOTION_TOKEN")
        self.database_id = os.getenv("NOTION_DATABASE_ID")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not notion_token or not self.database_id:
            logger.warning("Notion credentials not found. Notion integration will be disabled.")
            self.client = None
            self.openai_client = None
        else:
            self.client = NotionClient(auth=notion_token)
            self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
            logger.info("Notion integration initialized successfully")
    
    def generate_ai_title(self, transcript: str) -> str:
        """Generate a concise AI-powered title for the transcript."""
        if not self.openai_client:
            # Fallback to simple truncation if OpenAI not available
            return transcript[:50] + "..." if len(transcript) > 50 else transcript
        
        try:
            # Create a prompt for generating a concise title
            prompt = f"""Create a very short, concise title (3-8 words maximum) that summarizes the key topic or main point of this voice memo transcript. The title should be clear and descriptive.

Transcript: "{transcript}"

Title:"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=20,
                temperature=0.3
            )
            
            title = response.choices[0].message.content.strip()
            # Remove quotes if the AI added them
            title = title.strip('"').strip("'")
            
            # Ensure title isn't too long (max 100 characters for Notion)
            if len(title) > 100:
                title = title[:97] + "..."
            
            logger.info(f"Generated AI title: {title}")
            return title
            
        except Exception as e:
            logger.warning(f"Failed to generate AI title: {e}")
            # Fallback to truncated transcript
            fallback_title = transcript[:50] + "..." if len(transcript) > 50 else transcript
            return fallback_title
    
    def create_voice_memo_page(self, transcript: str, duration: int, user_name: str) -> dict:
        """Create a new page in the Voice Memos database."""
        if not self.client:
            return {
                "success": False,
                "error": "Notion client not configured",
                "page_url": None
            }
        
        try:
            # Generate an AI-powered title for the transcript
            title = self.generate_ai_title(transcript)
            if not title.strip():
                title = f"Voice memo from {user_name}"
            
            # Create the page
            page_data = {
                "parent": {"database_id": self.database_id},
                "properties": {
                    "Title": {
                        "title": [
                            {
                                "text": {
                                    "content": title
                                }
                            }
                        ]
                    },
                    "Transcript": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": transcript
                                }
                            }
                        ]
                    },
                    "Duration": {
                        "number": duration
                    },
                    "Source": {
                        "select": {
                            "name": "Telegram"
                        }
                    }
                }
            }
            
            response = self.client.pages.create(**page_data)
            page_url = response.get("url")
            
            logger.info(f"Successfully created Notion page: {page_url}")
            
            return {
                "success": True,
                "error": None,
                "page_url": page_url
            }
            
        except Exception as e:
            logger.error(f"Error creating Notion page: {e}")
            return {
                "success": False,
                "error": str(e),
                "page_url": None
            }

class NotionVoxBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.transcriber = WhisperTranscriber()
        self.notion = NotionIntegrator()
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
            "Send me a voice message and I'll:\n"
            "• Log detailed information about it\n"
            "• Transcribe it using OpenAI Whisper\n"
            "• Generate an AI-powered title (3-8 words)\n"
            "• Save to your Notion database with smart title\n"
            "• Save the audio file locally\n\n"
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
            "• Send a voice message to analyze it\n"
            "• The bot will download the audio file\n"
            "• Voice will be transcribed using OpenAI Whisper\n"
            "• AI generates a smart title (3-8 words)\n"
            "• Everything gets saved to your Notion database\n"
            "• You'll receive the transcript and Notion link\n\n"
            "✅ Current features:\n"
            "• Voice message logging and analysis\n"
            "• Automatic transcription with OpenAI Whisper\n"
            "• **AI-generated smart titles using GPT-4o-mini**\n"
            "• File conversion (OGA to MP3)\n"
            "• **Full Notion integration with organized data**\n\n"
            "🚀 Future features:\n"
            "• Enhanced Notion formatting and organization\n"
            "• Multiple database support"
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
            
            # Send initial confirmation to user
            initial_response = (
                f"✅ Voice message received!\n\n"
                f"👤 From: {details['user_name']}\n"
                f"⏱️ Duration: {details['voice_duration']} seconds\n"
                f"📁 File size: {details['actual_file_size']} bytes\n"
                f"💾 Saved as: {filename}\n"
                f"📅 Received at: {details['message_date'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🔄 Transcribing audio..."
            )
            
            sent_message = await update.message.reply_text(initial_response)
            
            # Transcribe the audio
            transcription_result = self.transcriber.transcribe_audio(file_path)
            
            if transcription_result["success"]:
                transcript = transcription_result["transcript"]
                details["transcript"] = transcript
                logger.info(f"Transcription: {transcript}")
                
                # Save to Notion
                notion_result = self.notion.create_voice_memo_page(
                    transcript=transcript,
                    duration=details['voice_duration'],
                    user_name=details['user_name']
                )
                
                # Prepare final response
                final_response = (
                    f"✅ Voice message processed!\n\n"
                    f"👤 From: {details['user_name']}\n"
                    f"⏱️ Duration: {details['voice_duration']} seconds\n"
                    f"📁 File size: {details['actual_file_size']} bytes\n"
                    f"💾 Saved as: {filename}\n"
                    f"📅 Received at: {details['message_date'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"📝 **Transcript:**\n{transcript}"
                )
                
                # Add Notion status to response
                if notion_result["success"]:
                    final_response += f"\n\n📔 **Saved to Notion:** [View Page]({notion_result['page_url']})"
                    details["notion_url"] = notion_result['page_url']
                else:
                    final_response += f"\n\n⚠️ **Notion save failed:** {notion_result['error']}"
                
                await sent_message.edit_text(final_response)
                
            else:
                error_msg = transcription_result["error"]
                logger.error(f"Transcription failed: {error_msg}")
                
                # Update message with error
                error_response = (
                    f"✅ Voice message received!\n\n"
                    f"👤 From: {details['user_name']}\n"
                    f"⏱️ Duration: {details['voice_duration']} seconds\n"
                    f"📁 File size: {details['actual_file_size']} bytes\n"
                    f"💾 Saved as: {filename}\n"
                    f"📅 Received at: {details['message_date'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"❌ Transcription failed: {error_msg}"
                )
                
                await sent_message.edit_text(error_response)
            
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
