terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "notionvoxbot"
}

# Data sources
data "aws_caller_identity" "current" {}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Lambda basic execution
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = 14
}

# Lambda Layer for dependencies
resource "aws_lambda_layer_version" "dependencies" {
  filename         = "../lambda_layer.zip"
  layer_name       = "${var.project_name}-dependencies"
  description      = "Dependencies for NotionVoxBot"
  
  compatible_runtimes = ["python3.12"]
  
  depends_on = [data.archive_file.lambda_layer]
}

# Archive for Lambda layer (dependencies)
data "archive_file" "lambda_layer" {
  type        = "zip"
  source_dir  = "../layer"
  output_path = "../lambda_layer.zip"
}

# Archive for Lambda function
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda_package"
  output_path = "../lambda_function.zip"
}

# Lambda function
resource "aws_lambda_function" "notionvoxbot" {
  filename         = "../lambda_function.zip"
  function_name    = "${var.project_name}-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_handler.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.12"
  timeout         = 300
  memory_size     = 512

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN   = var.telegram_bot_token
      OPENAI_API_KEY      = var.openai_api_key
      NOTION_TOKEN        = var.notion_token
      NOTION_DATABASE_ID  = var.notion_database_id
      ENVIRONMENT         = var.environment
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_cloudwatch_log_group.lambda_logs
  ]
}

# Lambda Function URL
resource "aws_lambda_function_url" "notionvoxbot_url" {
  function_name      = aws_lambda_function.notionvoxbot.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_methods     = ["POST", "GET"]
    allow_origins     = ["*"]
    expose_headers    = ["date", "keep-alive"]
    max_age          = 86400
  }
}

# Environment variables (mark as sensitive)
variable "telegram_bot_token" {
  description = "Telegram Bot Token"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
}

variable "notion_token" {
  description = "Notion Integration Token"
  type        = string
  sensitive   = true
}

variable "notion_database_id" {
  description = "Notion Database ID"
  type        = string
  sensitive   = true
}

# Outputs
output "lambda_function_url" {
  description = "URL of the Lambda function"
  value       = aws_lambda_function_url.notionvoxbot_url.function_url
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.notionvoxbot.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.notionvoxbot.arn
}
