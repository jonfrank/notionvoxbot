#!/bin/bash

# NotionVoxBot AWS Deployment Script
# This script prepares and deploys the bot to AWS Lambda

set -e

echo "🚀 NotionVoxBot AWS Deployment Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_dependencies() {
    print_status "Checking dependencies..."
    
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed."
        exit 1
    fi
    
    print_status "All dependencies found ✓"
}

# Check if .env file exists
check_env_file() {
    print_status "Checking environment file..."
    
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create it with your API keys."
        exit 1
    fi
    
    print_status "Environment file found ✓"
}

# Load environment variables
load_env() {
    print_status "Loading environment variables..."
    set -a
    source .env
    set +a
    
    # Check required variables
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$OPENAI_API_KEY" ] || [ -z "$NOTION_TOKEN" ] || [ -z "$NOTION_DATABASE_ID" ]; then
        print_error "Missing required environment variables. Please check your .env file."
        exit 1
    fi
    
    print_status "Environment variables loaded ✓"
}

# Create deployment directories
create_directories() {
    print_status "Creating deployment directories..."
    
    rm -rf lambda_package lambda_layer.zip lambda_function.zip layer
    mkdir -p lambda_package
    mkdir -p layer/python
    
    print_status "Directories created ✓"
}

# Install Python dependencies
install_dependencies() {
    print_status "Installing Python dependencies for Lambda layer..."
    
    pip install --target layer/python -r requirements.txt
    
    # Remove unnecessary files to reduce package size
    print_status "Cleaning up unnecessary files..."
    find layer/python -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find layer/python -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find layer/python -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find layer/python -name "*.pyc" -delete 2>/dev/null || true
    
    print_status "Dependencies installed and cleaned ✓"
}

# Copy Lambda function code
copy_function_code() {
    print_status "Copying Lambda function code..."
    
    cp lambda_handler.py lambda_package/
    
    print_status "Function code copied ✓"
}

# Initialize Terraform
init_terraform() {
    print_status "Initializing Terraform..."
    
    cd terraform
    terraform init
    cd ..
    
    print_status "Terraform initialized ✓"
}

# Plan Terraform deployment
plan_terraform() {
    print_status "Planning Terraform deployment..."
    
    cd terraform
    terraform plan \
        -var="telegram_bot_token=$TELEGRAM_BOT_TOKEN" \
        -var="openai_api_key=$OPENAI_API_KEY" \
        -var="notion_token=$NOTION_TOKEN" \
        -var="notion_database_id=$NOTION_DATABASE_ID" \
        -out=tfplan
    cd ..
    
    print_status "Terraform plan completed ✓"
}

# Apply Terraform deployment
apply_terraform() {
    print_status "Applying Terraform deployment..."
    
    cd terraform
    terraform apply tfplan
    
    # Get the Lambda function URL
    FUNCTION_URL=$(terraform output -raw lambda_function_url)
    print_status "Lambda Function URL: $FUNCTION_URL"
    cd ..
    
    print_status "Terraform deployment completed ✓"
    echo "FUNCTION_URL=$FUNCTION_URL"
}

# Set Telegram webhook
set_webhook() {
    print_status "Setting Telegram webhook..."
    
    if [ -z "$FUNCTION_URL" ]; then
        cd terraform
        FUNCTION_URL=$(terraform output -raw lambda_function_url)
        cd ..
    fi
    
    curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"$FUNCTION_URL\"}"
    
    echo ""
    print_status "Telegram webhook set ✓"
}

# Test the deployment
test_deployment() {
    print_status "Testing deployment..."
    
    if [ -z "$FUNCTION_URL" ]; then
        cd terraform
        FUNCTION_URL=$(terraform output -raw lambda_function_url)
        cd ..
    fi
    
    echo "Testing Lambda function..."
    curl -X GET "$FUNCTION_URL"
    echo ""
    
    print_status "Deployment test completed ✓"
}

# Main deployment function
deploy() {
    print_status "Starting deployment process..."
    
    check_dependencies
    check_env_file
    load_env
    create_directories
    install_dependencies
    copy_function_code
    init_terraform
    plan_terraform
    apply_terraform
    set_webhook
    test_deployment
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "Your NotionVoxBot is now running on AWS Lambda!"
    echo "Function URL: $FUNCTION_URL"
    echo ""
    echo "You can now send voice messages to your Telegram bot."
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "plan")
        check_dependencies
        check_env_file
        load_env
        create_directories
        install_dependencies
        copy_function_code
        init_terraform
        plan_terraform
        ;;
    "destroy")
        print_warning "This will destroy all AWS resources. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            load_env
            cd terraform
            terraform destroy \
                -var="telegram_bot_token=$TELEGRAM_BOT_TOKEN" \
                -var="openai_api_key=$OPENAI_API_KEY" \
                -var="notion_token=$NOTION_TOKEN" \
                -var="notion_database_id=$NOTION_DATABASE_ID"
            cd ..
            print_status "Resources destroyed ✓"
        fi
        ;;
    "clean")
        print_status "Cleaning up build artifacts..."
        rm -rf lambda_package lambda_layer.zip lambda_function.zip layer
        print_status "Cleanup completed ✓"
        ;;
    *)
        echo "Usage: $0 {deploy|plan|destroy|clean}"
        echo ""
        echo "Commands:"
        echo "  deploy  - Deploy the bot to AWS (default)"
        echo "  plan    - Plan the deployment without applying"
        echo "  destroy - Destroy all AWS resources"
        echo "  clean   - Clean up build artifacts"
        exit 1
        ;;
esac
