# NotionVoxBot - AWS Deployment Guide

Complete guide for deploying NotionVoxBot to AWS Lambda with automated CI/CD.

## 🏗️ Architecture

- **AWS Lambda** - Serverless function hosting the bot
- **Lambda Function URL** - HTTPS endpoint for Telegram webhooks
- **Lambda Layer** - Shared dependencies (python packages)
- **CloudWatch Logs** - Centralized logging
- **Terraform** - Infrastructure as Code
- **GitHub Actions** - Automated deployment

## 🚀 Quick Deployment

### Prerequisites

1. **AWS Account** with CLI configured
2. **Terraform** installed (`brew install terraform`)
3. **GitHub repository** with your code

### Local Deployment (One-Time Setup)

```bash
# 1. Configure AWS credentials
aws configure

# 2. Run deployment script
./deploy.sh

# 3. Test your bot in Telegram!
```

### GitHub Actions Deployment (Automated)

1. **Set up GitHub Secrets** (Repository Settings → Secrets and variables → Actions):

```
AWS_ACCESS_KEY_ID          - Your AWS access key
AWS_SECRET_ACCESS_KEY      - Your AWS secret key
TELEGRAM_BOT_TOKEN         - Your Telegram bot token
OPENAI_API_KEY            - Your OpenAI API key
NOTION_TOKEN              - Your Notion integration token
NOTION_DATABASE_ID        - Your Notion database ID
```

2. **Push to main branch** - Deployment happens automatically!

```bash
git add .
git commit -m "🚀 feat: Deploy to AWS Lambda"
git push origin main
```

## 📁 Project Structure

```
notionvoxbot/
├── terraform/
│   └── main.tf                 # AWS infrastructure definition
├── .github/workflows/
│   └── deploy.yml              # GitHub Actions CI/CD pipeline
├── lambda_handler.py           # Lambda-optimized bot code
├── deploy.sh                   # Local deployment script
├── bot.py                      # Original local bot code
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (local only)
```

## 🔧 Deployment Options

### 1. Manual Deployment Script

```bash
# Deploy everything
./deploy.sh

# Plan deployment (dry run)
./deploy.sh plan

# Destroy resources
./deploy.sh destroy

# Clean build artifacts
./deploy.sh clean
```

### 2. GitHub Actions (Recommended)

- **Automatic deployment** on push to `main`
- **Infrastructure validation** on pull requests  
- **Webhook configuration** handled automatically
- **Rollback capabilities** built-in

### 3. Manual Terraform

```bash
cd terraform

# Initialize
terraform init

# Plan
terraform plan \
  -var="telegram_bot_token=$TELEGRAM_BOT_TOKEN" \
  -var="openai_api_key=$OPENAI_API_KEY" \
  -var="notion_token=$NOTION_TOKEN" \
  -var="notion_database_id=$NOTION_DATABASE_ID"

# Apply
terraform apply
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `OPENAI_API_KEY` | OpenAI API key for Whisper & GPT | ✅ |
| `NOTION_TOKEN` | Notion integration token | ✅ |
| `NOTION_DATABASE_ID` | Notion database ID | ✅ |
| `AWS_REGION` | AWS region (default: us-east-1) | ❌ |

### Terraform Variables

All environment variables can be overridden in `terraform/main.tf`:

```hcl
variable "aws_region" {
  default = "us-west-2"  # Change default region
}

variable "environment" {
  default = "staging"    # Change environment name
}
```

## 📊 Monitoring & Logs

### CloudWatch Logs

```bash
# View logs
aws logs describe-log-groups --log-group-name-prefix="/aws/lambda/notionvoxbot"

# Tail logs in real-time
aws logs tail /aws/lambda/notionvoxbot-prod --follow
```

### Lambda Metrics

- **Duration** - Function execution time
- **Invocations** - Number of webhook calls
- **Errors** - Failed executions
- **Memory Usage** - RAM consumption

## 🔍 Troubleshooting

### Common Issues

1. **"Could not find database"** - Notion database not shared with integration
2. **"Invalid bot token"** - Wrong Telegram token in environment
3. **"OpenAI API error"** - Invalid OpenAI key or rate limits
4. **"Lambda timeout"** - Large voice files (increase timeout in terraform)

### Debug Commands

```bash
# Test Lambda function directly
curl -X GET "$(terraform output -raw lambda_function_url)"

# Check webhook status
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"

# View CloudWatch logs
aws logs tail /aws/lambda/notionvoxbot-prod --since 1h
```

### Reset Webhook

```bash
# Clear webhook
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"

# Set new webhook
FUNCTION_URL=$(cd terraform && terraform output -raw lambda_function_url)
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$FUNCTION_URL\"}"
```

## 💰 Cost Estimation

### AWS Lambda Costs (us-east-1)

- **Requests**: $0.20 per 1M requests
- **Duration**: $0.0000166667 per GB-second
- **Free Tier**: 1M requests + 400,000 GB-seconds/month

### Example Monthly Cost

| Usage | Requests | Duration | Cost |
|-------|----------|----------|------|
| Light | 1,000 | 5s avg | FREE |
| Medium | 10,000 | 10s avg | ~$1.50 |
| Heavy | 100,000 | 15s avg | ~$15.00 |

### Additional Costs

- **OpenAI Whisper**: ~$0.006/minute of audio
- **OpenAI GPT-4o-mini**: ~$0.00015/1K tokens
- **CloudWatch Logs**: ~$0.50/GB stored

## 🔐 Security

### Lambda Security

- **IAM Roles** - Least privilege access
- **Environment Variables** - Encrypted at rest
- **VPC** - Optional network isolation
- **Function URLs** - HTTPS only, CORS configured

### Secrets Management

- **GitHub Secrets** - Encrypted in repository
- **AWS Systems Manager** - Optional parameter store
- **Terraform State** - Stored securely

## 🚀 Advanced Features

### Auto-scaling

Lambda automatically scales from 0 to 1000+ concurrent executions.

### Custom Domains

```hcl
# Add to terraform/main.tf
resource "aws_apigatewayv2_domain_name" "notionvoxbot" {
  domain_name = "bot.yourdomain.com"
  
  domain_name_configuration {
    certificate_arn = aws_acm_certificate.cert.arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}
```

### Dead Letter Queues

```hcl
# Add to Lambda resource
dead_letter_config {
  target_arn = aws_sqs_queue.dlq.arn
}
```

### Multiple Environments

```bash
# Deploy to staging
terraform workspace new staging
terraform apply -var="environment=staging"

# Deploy to production  
terraform workspace new production
terraform apply -var="environment=production"
```

## 🎯 Next Steps

1. **Monitor logs** for the first few voice messages
2. **Set up alerts** for errors in CloudWatch
3. **Consider** setting up a custom domain
4. **Implement** automated testing with GitHub Actions
5. **Scale** to multiple environments if needed

Your NotionVoxBot is now running serverlessly on AWS! 🎉
