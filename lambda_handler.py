#!/usr/bin/env python3
"""
Lambda handler for NotionVoxBot - Webhook-based deployment
"""

import json
import logging
import asyncio
import os
from datetime import datetime
from pathlib import Path
import tempfile
import base64

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
from openai import OpenAI
from notion_client import Client as NotionClient

# Configure logging for Lambda
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Authorization configuration - Only allow specific user IDs
# Add your user ID here after first interaction
ALLOWED_USER_IDS = {
    8314097969  # @stratovate
}

def is_authorized_user(user_id: int, username: str = None) -> bool:
    """Check if user is authorized to use the bot."""
    if user_id in ALLOWED_USER_IDS:
        return True
    
    # Log unauthorized access attempts
    logger.warning(f"Unauthorized access attempt - User ID: {user_id}, Username: {username}")
    return False

class WhisperTranscriber:
    """Handles voice transcription using OpenAI Whisper API."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. Transcription will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
    
    def transcribe_audio(self, audio_path: Path) -> dict:
        """Transcribe audio file using OpenAI Whisper API."""
        if not self.client:
            return {
                "success": False,
                "error": "OpenAI API key not configured",
                "transcript": None
            }
        
        try:
            # Transcribe using Whisper API (directly supports OGA format)
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
    def __init__(self):
        # Create custom HTTP client with better settings for Lambda
        request = HTTPXRequest(
            connection_pool_size=1,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0
        )
        
        self.bot = Bot(
            token=os.getenv("TELEGRAM_BOT_TOKEN"),
            request=request
        )
        self.transcriber = WhisperTranscriber()
        self.notion = NotionIntegrator()

    async def handle_voice_message(self, update: Update):
        """Handle voice messages from Telegram updates."""
        try:
            voice = update.message.voice
            user = update.message.from_user
            
            # Authorization check
            if not is_authorized_user(user.id, user.username):
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text="🚫 Unauthorized access. This bot is private."
                )
                return
            
            # Log voice message details
            logger.info(f"Received voice message from {user.first_name} ({user.id})")
            logger.info(f"Voice details: duration={voice.duration}s, file_size={voice.file_size} bytes")
            
            # Create temporary directory for this request
            with tempfile.TemporaryDirectory() as temp_dir:
                # Get file info from Telegram
                file_info = await self.bot.get_file(voice.file_id)
                
                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"voice_{user.id}_{timestamp}.oga"
                file_path = Path(temp_dir) / filename
                
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
                
                sent_message = await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=initial_response
                )
                
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
                    
                    await self.bot.edit_message_text(
                        chat_id=update.message.chat_id,
                        message_id=sent_message.message_id,
                        text=final_response
                    )
                    
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
                    
                    await self.bot.edit_message_text(
                        chat_id=update.message.chat_id,
                        message_id=sent_message.message_id,
                        text=error_response
                    )
                
        except Exception as e:
            logger.error(f"Error handling voice message: {e}")
            await self.bot.send_message(
                chat_id=update.message.chat_id,
                text="❌ Sorry, there was an error processing your voice message. Please try again."
            )

    async def handle_text_message(self, update: Update):
        """Handle text messages (commands)."""
        try:
            user = update.message.from_user
            text = update.message.text
            
            # Special command to help get user ID - bypasses authorization
            if text == "/myid":
                logger.info(f"User ID request - User: {user.username or user.first_name}, ID: {user.id}")
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=f"🆔 **Your Telegram User Info:**\n\n"
                         f"👤 Name: {user.first_name} {user.last_name or ''}".strip() + "\n"
                         f"📛 Username: @{user.username or 'None'}\n"
                         f"🔢 User ID: `{user.id}`\n\n"
                         f"*Add your User ID to the ALLOWED_USER_IDS set in the code to gain access.*"
                )
                return
            
            # Authorization check for all other commands
            if not is_authorized_user(user.id, user.username):
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text="🚫 Unauthorized access. This bot is private.\n\n"
                         "Use /myid to see your user ID for access."
                )
                return
            
            if text == "/start":
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
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=welcome_message
                )
                
            elif text == "/help":
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
                    "• Direct OGA audio file processing\n"
                    "• **Full Notion integration with organized data**\n\n"
                    "🚀 Future features:\n"
                    "• Enhanced Notion formatting and organization\n"
                    "• Multiple database support"
                )
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=help_message
                )
            else:
                await self.bot.send_message(
                    chat_id=update.message.chat_id,
                    text="🎤 Please send me a voice message to log its details!\n"
                         "Use /help for more information."
                )
                
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            await self.bot.send_message(
                chat_id=update.message.chat_id,
                text="❌ Sorry, there was an error processing your message. Please try again."
            )

    async def process_update(self, update_data):
        """Process a Telegram update."""
        try:
            update = Update.de_json(update_data, self.bot)
            
            if update.message:
                if update.message.voice:
                    await self.handle_voice_message(update)
                elif update.message.text:
                    await self.handle_text_message(update)
                    
        except Exception as e:
            logger.error(f"Error processing update: {e}")


def handler(event, context):
    """Lambda handler function."""
    logger.info("Lambda handler called")
    
    try:
        # Handle HTTP requests from Telegram webhook
        if 'body' in event:
            # Parse the webhook payload
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
            
            logger.info(f"Received webhook payload: {json.dumps(body, default=str)}")
            
            # Initialize bot instance for each request to avoid connection pool issues
            bot_instance = NotionVoxBot()
            
            # Process the update asynchronously
            asyncio.run(bot_instance.process_update(body))
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                },
                'body': json.dumps({'status': 'ok'})
            }
        
        # Handle direct invocation for testing
        else:
            logger.info("Direct invocation - returning test response")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                },
                'body': json.dumps({
                    'status': 'ok',
                    'message': 'NotionVoxBot Lambda is running',
                    'environment': os.getenv('ENVIRONMENT', 'unknown')
                })
            }
            
    except Exception as e:
        logger.error(f"Error in Lambda handler: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({
                'status': 'error', 
                'message': str(e)
            })
        }
