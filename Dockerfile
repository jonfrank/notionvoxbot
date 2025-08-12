# Use the official AWS Lambda Python runtime as base image
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements first for better caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Lambda function code
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD ["lambda_handler.handler"]
