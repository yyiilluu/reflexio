# Onboarding

## Information needed
- aws access
- openai/anthropic key

## AWS
once get aws console access
### 1: Get AWS cli access
- Create the access key
- Go to IAM
- Users → click your username
- Security credentials tab
- Access keys → Create access key
- Choose Command Line Interface (CLI)
- Create access key
- Copy: Access key ID and Secret access key (only shown once)

then run `aws configure --profile myaccount`.
First unset any existing variables `unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN`
To use this profile going forward: `export AWS_PROFILE=myaccount`
