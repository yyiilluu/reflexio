# AWS SES Email Verification Setup for ECS

This guide adds email verification capabilities to your existing ECS deployment.

## Prerequisites

- Completed [AWS ECS Deployment](./aws-ecs-deployment.md)
- Email address verified in AWS SES (or SES out of sandbox mode)

## Step 1: Add SES Permissions to ECS Task Role

```bash
# Set environment variables (from your deployment)
export AWS_REGION=us-west-2
export APP_NAME=reflexio

# Create SES policy
cat > /tmp/ses-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Attach policy to the ECS task role
aws iam put-role-policy \
    --role-name ecsTaskRole-$APP_NAME \
    --policy-name SESEmailAccess \
    --policy-document file:///tmp/ses-policy.json

echo "SES permissions added to ecsTaskRole-$APP_NAME"
```

## Step 2: Update Secrets in AWS Secrets Manager

Add the email configuration to your existing secrets:

```bash
# Get current secrets
aws secretsmanager get-secret-value \
    --secret-id $APP_NAME/prod/env \
    --query SecretString --output text > /tmp/current-secrets.json

# View current secrets (to merge with new ones)
cat /tmp/current-secrets.json | python3 -m json.tool

# Update secrets with email configuration
# Replace values with your actual configuration
cat > /tmp/updated-secrets.json << 'EOF'
{
    "OPENAI_API_KEY": "sk-proj-...",
    "LOGIN_SUPABASE_URL": "https://<project-id>.supabase.co",
    "LOGIN_SUPABASE_KEY": "eyJ...",
    "FRONTEND_URL": "https://reflexio.com",
    "AWS_REGION": "us-west-2",
    "SES_SENDER_EMAIL": "noreply@reflexio.com"
}
EOF

# Update the secret
aws secretsmanager update-secret \
    --secret-id $APP_NAME/prod/env \
    --secret-string file:///tmp/updated-secrets.json

# Clean up
rm /tmp/current-secrets.json /tmp/updated-secrets.json

echo "Secrets updated"
```

## Step 3: Update ECS Task Definition

Update the task definition to include the new environment variables:

```bash
# Get current task definition
aws ecs describe-task-definition \
    --task-definition $APP_NAME-task \
    --query 'taskDefinition' > /tmp/current-task-def.json

# Get required ARNs
export EXECUTION_ROLE_ARN=$(aws iam get-role \
    --role-name ecsTaskExecutionRole-$APP_NAME \
    --query Role.Arn --output text)
export TASK_ROLE_ARN=$(aws iam get-role \
    --role-name ecsTaskRole-$APP_NAME \
    --query Role.Arn --output text)
export SECRET_ARN=$(aws secretsmanager describe-secret \
    --secret-id $APP_NAME/prod/env \
    --query ARN --output text)
export ECR_URI=$(aws ecr describe-repositories \
    --repository-names $APP_NAME \
    --query 'repositories[0].repositoryUri' --output text)

# Create updated task definition with email secrets
cat > /tmp/task-definition.json << EOF
{
    "family": "${APP_NAME}-task",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "executionRoleArn": "${EXECUTION_ROLE_ARN}",
    "taskRoleArn": "${TASK_ROLE_ARN}",
    "containerDefinitions": [
        {
            "name": "${APP_NAME}",
            "image": "${ECR_URI}:latest",
            "essential": true,
            "portMappings": [
                {"containerPort": 8080, "protocol": "tcp", "name": "frontend"},
                {"containerPort": 8081, "protocol": "tcp", "name": "api"}
            ],
            "environment": [
                {"name": "NODE_ENV", "value": "production"},
                {"name": "ENVIRONMENT", "value": "production"}
            ],
            "secrets": [
                {"name": "OPENAI_API_KEY", "valueFrom": "${SECRET_ARN}:OPENAI_API_KEY::"},
                {"name": "ANTHROPIC_API_KEY", "valueFrom": "${SECRET_ARN}:ANTHROPIC_API_KEY::"},
                {"name": "LOGIN_SUPABASE_URL", "valueFrom": "${SECRET_ARN}:LOGIN_SUPABASE_URL::"},
                {"name": "LOGIN_SUPABASE_KEY", "valueFrom": "${SECRET_ARN}:LOGIN_SUPABASE_KEY::"},
                {"name": "FRONTEND_URL", "valueFrom": "${SECRET_ARN}:FRONTEND_URL::"},
                {"name": "AWS_REGION", "valueFrom": "${SECRET_ARN}:AWS_REGION::"},
                {"name": "SES_SENDER_EMAIL", "valueFrom": "${SECRET_ARN}:SES_SENDER_EMAIL::"}
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/${APP_NAME}",
                    "awslogs-region": "${AWS_REGION}",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8081/health || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
EOF

# Register new task definition
aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region $AWS_REGION

echo "Task definition updated"
```

## Step 4: Deploy Updated Service

```bash
# Force new deployment with updated task definition
aws ecs update-service \
    --cluster $APP_NAME-cluster \
    --service $APP_NAME-service \
    --force-new-deployment

# Wait for deployment to complete
echo "Waiting for deployment..."
aws ecs wait services-stable \
    --cluster $APP_NAME-cluster \
    --services $APP_NAME-service

echo "Deployment complete!"
```

## Step 5: Verify Email Sending

Test the email verification endpoint:

```bash
# Test with a valid email (replace with your test email)
curl -X POST https://reflexio.com/api/resend-verification \
    -H "Content-Type: application/json" \
    -d '{"email": "your-test@example.com"}'
```

Check CloudWatch logs for email sending status:

```bash
aws logs tail /ecs/$APP_NAME --since 5m | grep -i "email\|ses"
```

## Troubleshooting

### SES Sandbox Mode

If your SES account is in sandbox mode, you can only send to verified emails:

```bash
# Verify a recipient email for testing
aws ses verify-email-identity --email-address recipient@example.com --region $AWS_REGION
```

To request production access: AWS Console → SES → Account Dashboard → Request Production Access

### Check IAM Permissions

```bash
# Verify SES policy is attached
aws iam get-role-policy \
    --role-name ecsTaskRole-$APP_NAME \
    --policy-name SESEmailAccess
```

### Check Secrets

```bash
# Verify secrets contain email config
aws secretsmanager get-secret-value \
    --secret-id $APP_NAME/prod/env \
    --query SecretString --output text | python3 -c "import sys,json; d=json.load(sys.stdin); print('FRONTEND_URL:', d.get('FRONTEND_URL', 'MISSING')); print('SES_SENDER_EMAIL:', d.get('SES_SENDER_EMAIL', 'MISSING'))"
```

## Summary

| Component | Change |
|-----------|--------|
| IAM Policy | Added `SESEmailAccess` to `ecsTaskRole-reflexio` |
| Secrets | Added `FRONTEND_URL`, `AWS_REGION`, `SES_SENDER_EMAIL` |
| Task Definition | Added 3 new secret references |
