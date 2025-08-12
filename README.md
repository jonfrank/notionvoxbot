# NotionVoxBot

A Telegram bot that converts voice messages to text using OpenAI's Whisper API and automatically saves them to a Notion database.

## Features

- 🎤 **Voice to Text**: Converts Telegram voice messages to text using OpenAI Whisper
- 📝 **Notion Integration**: Automatically saves transcriptions to your Notion database
- ☁️ **AWS Lambda**: Serverless deployment with automatic scaling
- 🔐 **Secure**: Environment variables and secrets management
- 🚀 **CI/CD**: Automated deployment with GitHub Actions
- 🔄 **Format Conversion**: Automatically converts OGA to MP3 format

## Prerequisites

Before deploying, you'll need:

1. **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/BotFather)
2. **OpenAI API Key**: Get one from [OpenAI](https://platform.openai.com/api-keys)
3. **Notion Integration**: Set up a Notion integration and database
4. **AWS Account**: For Lambda deployment
5. **GitHub Account**: For automated deployment

## Setup Instructions

### 1. Notion Setup

1. Create a new Notion page with a database
2. Add these columns to your database:
   - **Message** (Text): For the transcribed voice message
   - **Date** (Date): When the message was received
   - **User** (Text): Telegram username
   - **Duration** (Number): Voice message duration in seconds

3. Create a Notion integration:
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Give it a name (e.g., "NotionVoxBot")
   - Copy the integration token

4. Share your database with the integration:
   - Go to your database page
   - Click "Share" → "Invite"
   - Add your integration

5. Get your database ID from the URL:
   ```
   https://notion.so/your-workspace/DATABASE_ID?v=...
   ```

### 2. GitHub Repository Setup

1. Fork or clone this repository to your GitHub account

2. Set up the following repository secrets (Settings → Secrets and variables → Actions):

   **AWS Credentials:**
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

   **Bot Configuration:**
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `NOTION_TOKEN`: Your Notion integration token
   - `NOTION_DATABASE_ID`: Your Notion database ID

### 3. Deploy to AWS

The deployment is fully automated using GitHub Actions:

#### Automatic Deployment
- **Push to main branch**: Automatically deploys to AWS
- **Pull requests**: Runs validation and planning only

#### Manual Deployment
1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Deploy NotionVoxBot to AWS"
4. Click "Run workflow"
5. Select the main branch and click "Run workflow"

The workflow will:
- Build the Lambda function and dependencies layer using Docker
- Deploy infrastructure using Terraform
- Set up the Telegram webhook automatically
- Test the deployment

### 4. Verify Deployment

After successful deployment:

1. Check the GitHub Actions logs for the Lambda function URL
2. Send a voice message to your Telegram bot
3. Check your Notion database for the transcribed message

## Project Structure

```
notionvoxbot/
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions workflow
├── terraform/
│   ├── main.tf            # Terraform infrastructure
│   ├── variables.tf       # Input variables
│   └── outputs.tf         # Output values
├── lambda_handler.py      # Main bot logic
├── requirements.txt       # Python dependencies
├── deploy.sh             # Local deployment script (optional)
└── README.md             # This file
```

## Local Development

If you want to test locally before deploying:

1. Create a `.env` file with your credentials:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_token
   OPENAI_API_KEY=your_openai_key
   NOTION_TOKEN=your_notion_token
   NOTION_DATABASE_ID=your_database_id
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run locally using the deployment script:
   ```bash
   ./deploy.sh deploy
   ```

## Cost Estimation

The AWS resources used by this bot are:
- **Lambda Function**: Pay per request (free tier: 1M requests/month)
- **Lambda Layer**: No additional cost
- **CloudWatch Logs**: Minimal cost for logging

Estimated monthly cost: **$0-5** for typical personal use.

## Troubleshooting

### Common Issues

1. **"Runtime.ImportModuleError"**: Usually indicates dependency issues
   - The workflow uses Docker to ensure compatible dependencies
   - Check GitHub Actions logs for build errors

2. **Webhook not set**: 
   - Check if the deployment completed successfully
   - Verify your Telegram bot token is correct

3. **Notion API errors**:
   - Ensure your integration has access to the database
   - Check that database ID is correct
   - Verify column names match the code

### Debugging

1. Check GitHub Actions workflow logs
2. View AWS CloudWatch logs for the Lambda function
3. Test the Lambda function URL directly

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
