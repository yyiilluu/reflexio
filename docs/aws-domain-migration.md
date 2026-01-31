# Domain Migration: agenticmem.com → reflexio.ai

Step-by-step guide for changing the domain from `agenticmem.com` to `reflexio.ai` on the existing AWS ECS Fargate + CloudFront deployment.

## What Needs to Change

| Resource | Change Required |
|----------|----------------|
| ACM Certificate (us-west-2, for ALB) | New cert for `reflexio.ai` |
| ACM Certificate (us-east-1, for CloudFront) | New cert for `reflexio.ai` |
| ALB HTTPS Listener | Swap to new certificate |
| CloudFront Distribution | Update aliases + certificate |
| DNS Records | Add `reflexio.ai` records, remove old `agenticmem.com` records |

**No changes needed**: ECR, ECS cluster/service/task, IAM roles, VPC, security groups, S3 bucket, Secrets Manager.

---

## Prerequisites

```bash
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export APP_NAME=agenticmem
export DOMAIN_NAME=reflexio.ai
export CF_DISTRIBUTION_ID=E15WBN9QYYCSND

# Get existing ALB ARN
export ALB_ARN=$(aws elbv2 describe-load-balancers \
    --names $APP_NAME-alb \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text \
    --region $AWS_REGION)

# Get existing HTTPS listener ARN
export HTTPS_LISTENER_ARN=$(aws elbv2 describe-listeners \
    --load-balancer-arn $ALB_ARN \
    --query "Listeners[?Protocol=='HTTPS'].ListenerArn" --output text \
    --region $AWS_REGION)

echo "ALB ARN: $ALB_ARN"
echo "HTTPS Listener: $HTTPS_LISTENER_ARN"
echo "CloudFront Distribution: $CF_DISTRIBUTION_ID"
```

ALB ARN: arn:aws:elasticloadbalancing:us-west-2:348297466724:loadbalancer/app/agenticmem-alb/d3395fec01672eac
HTTPS Listener: arn:aws:elasticloadbalancing:us-west-2:348297466724:listener/app/agenticmem-alb/d3395fec01672eac/7dd63bd9edb63336
CloudFront Distribution: E15WBN9QYYCSND

---

## Step 1: Request New ACM Certificate for ALB (us-west-2)

```bash
export NEW_CERT_ARN=$(aws acm request-certificate \
    --domain-name $DOMAIN_NAME \
    --subject-alternative-names "www.$DOMAIN_NAME" \
    --validation-method DNS \
    --query CertificateArn --output text \
    --region $AWS_REGION)

echo "New ALB Certificate ARN: $NEW_CERT_ARN"

# Get DNS validation records
aws acm describe-certificate \
    --certificate-arn $NEW_CERT_ARN \
    --region $AWS_REGION \
    --query 'Certificate.DomainValidationOptions[*].{Domain:DomainName,Name:ResourceRecord.Name,Value:ResourceRecord.Value}' \
    --output table
```

---

## Step 2: Request New ACM Certificate for CloudFront (us-east-1)

CloudFront requires certificates in **us-east-1**.

```bash
export NEW_CF_CERT_ARN=$(aws acm request-certificate \
    --domain-name $DOMAIN_NAME \
    --subject-alternative-names "www.$DOMAIN_NAME" \
    --validation-method DNS \
    --query CertificateArn --output text \
    --region us-east-1)

echo "New CloudFront Certificate ARN: $NEW_CF_CERT_ARN"

# Get DNS validation records (may be same CNAME as Step 1)
aws acm describe-certificate \
    --certificate-arn $NEW_CF_CERT_ARN \
    --region us-east-1 \
    --query 'Certificate.DomainValidationOptions[*].{Domain:DomainName,Name:ResourceRecord.Name,Value:ResourceRecord.Value}' \
    --output table
```

---

## Step 3: Add DNS Validation Records for reflexio.ai

If you already ran Steps 1 and 2 in a previous session, retrieve the certificate ARNs first:

```bash
# Get NEW_CERT_ARN (us-west-2, for ALB)
export NEW_CERT_ARN=$(aws acm list-certificates --region $AWS_REGION \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN_NAME'].CertificateArn" --output text)
echo "ALB Certificate ARN: $NEW_CERT_ARN"

# Get NEW_CF_CERT_ARN (us-east-1, for CloudFront)
export NEW_CF_CERT_ARN=$(aws acm list-certificates --region us-east-1 \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN_NAME'].CertificateArn" --output text)
echo "CloudFront Certificate ARN: $NEW_CF_CERT_ARN"
```

Add the CNAME records from Steps 1 and 2 at your **reflexio.ai** DNS provider.

> **Note**: Both ACM certificates (us-west-2 and us-east-1) for the same domain typically require the same CNAME validation record, so you likely only need to add it once.

1. Go to your DNS provider for `reflexio.ai`
2. Add CNAME record:
   - **Name**: The `Name` value from ACM output (remove the domain suffix, e.g. `_abc123` from `_abc123.reflexio.ai.`)
   - **Value**: The `Value` from ACM output
   - **TTL**: 600

```bash
# Wait for both certificates to validate
echo "Waiting for ALB certificate validation..."
aws acm wait certificate-validated --certificate-arn $NEW_CERT_ARN --region $AWS_REGION
echo "ALB certificate validated!"

echo "Waiting for CloudFront certificate validation..."
aws acm wait certificate-validated --certificate-arn $NEW_CF_CERT_ARN --region us-east-1
echo "CloudFront certificate validated!"
```

---

## Step 4: Update ALB HTTPS Listener Certificate

```bash
# Swap the certificate on the HTTPS listener
aws elbv2 modify-listener \
    --listener-arn $HTTPS_LISTENER_ARN \
    --certificates CertificateArn=$NEW_CERT_ARN \
    --region $AWS_REGION

echo "ALB HTTPS listener updated with new certificate"
```

---

## Step 5: Update CloudFront Distribution

### 5.1 Get Current Config

```bash
aws cloudfront get-distribution-config \
    --id $CF_DISTRIBUTION_ID \
    --output json > /tmp/cf-current.json

# Extract ETag (required for updates)
export CF_ETAG=$(cat /tmp/cf-current.json | jq -r '.ETag')

# Extract just the DistributionConfig
cat /tmp/cf-current.json | jq '.DistributionConfig' > /tmp/cf-config.json

echo "Current ETag: $CF_ETAG"
```

### 5.2 Update Aliases and Certificate

```bash
# Update the aliases to the new domain
cat /tmp/cf-config.json | jq \
    --arg domain "$DOMAIN_NAME" \
    --arg cert "$NEW_CF_CERT_ARN" \
    '.Aliases = {"Quantity": 2, "Items": [$domain, "www." + $domain]} |
     .ViewerCertificate.ACMCertificateArn = $cert' \
    > /tmp/cf-updated.json

# Verify the changes look correct
echo "Updated aliases:"
cat /tmp/cf-updated.json | jq '.Aliases'
echo "Updated certificate:"
cat /tmp/cf-updated.json | jq '.ViewerCertificate.ACMCertificateArn'
```

### 5.3 Apply the Update

```bash
aws cloudfront update-distribution \
    --id $CF_DISTRIBUTION_ID \
    --if-match $CF_ETAG \
    --distribution-config file:///tmp/cf-updated.json

echo "CloudFront distribution update initiated"

# Wait for deployment (can take 5-15 minutes)
echo "Waiting for CloudFront to deploy..."
aws cloudfront wait distribution-deployed --id $CF_DISTRIBUTION_ID
echo "CloudFront distribution deployed!"
```

---

## Step 6: Update DNS Records for reflexio.ai

Get the CloudFront distribution domain name:

```bash
export CF_DOMAIN=$(aws cloudfront get-distribution \
    --id $CF_DISTRIBUTION_ID \
    --query 'Distribution.DomainName' --output text)

echo "Point DNS to: $CF_DOMAIN"
```

In **Squarespace**:

1. Go to **Settings** → **Domains** → **reflexio.ai** → **DNS Settings**
2. Add a **CNAME** record for `www`:
   - **Host**: `www`
   - **Value**: Your `CF_DOMAIN` value (e.g., `d1234567890.cloudfront.net`)
3. Add a **CNAME** record for the root domain (`@`):
   - Squarespace does not support ALIAS/ANAME records, so use a **CNAME** with **Host**: `@` and **Value**: the CloudFront domain
   - **Note**: Squarespace allows CNAME on `@` which some providers don't. If it doesn't work, set up a **URL redirect** from `reflexio.ai` → `www.reflexio.ai` under **Settings** → **Domains** → **reflexio.ai** → **URL Forwarding**

> **Also**: If you added the ACM validation CNAME in Step 3 at a different DNS provider, make sure it also exists in Squarespace if Squarespace is the authoritative DNS for `reflexio.ai`.

---

## Step 7: Remove Old DNS Records for agenticmem.com

At **GoDaddy** (or wherever `agenticmem.com` DNS is managed):

1. Remove the **www** CNAME record pointing to CloudFront
2. Remove any root domain forwarding to `www.agenticmem.com`
3. Optionally keep the ACM validation CNAME records (they're harmless, but can be removed after old certs are deleted)

---

## Step 8: Verify

```bash
echo "=== Testing new domain ==="

echo "Frontend:"
curl -I https://$DOMAIN_NAME/

echo "API Health:"
curl https://$DOMAIN_NAME/health

echo "Documentation:"
curl -I https://$DOMAIN_NAME/docs/

echo "www redirect:"
curl -I https://www.$DOMAIN_NAME/
```

---

## Step 9: Clean Up Old Certificates

After verifying everything works on the new domain:

```bash
# Get old certificate ARNs
echo "Listing certificates for cleanup..."

# List us-west-2 certificates
aws acm list-certificates --region $AWS_REGION \
    --query 'CertificateSummaryList[*].{Domain:DomainName,ARN:CertificateArn}' \
    --output table

# List us-east-1 certificates
aws acm list-certificates --region us-east-1 \
    --query 'CertificateSummaryList[*].{Domain:DomainName,ARN:CertificateArn}' \
    --output table

# Delete old ALB certificate (replace with actual ARN of old agenticmem.com cert)
# aws acm delete-certificate --certificate-arn <OLD_CERT_ARN> --region $AWS_REGION

# Delete old CloudFront certificate (replace with actual ARN of old agenticmem.com cert)
# aws acm delete-certificate --certificate-arn <OLD_CF_CERT_ARN> --region us-east-1
```

---

## Step 10: Update Environment Variables Reference

Update your saved environment variables for future deployments:

```bash
echo "=== Updated values ==="
echo "export DOMAIN_NAME=reflexio.ai"
echo "export CERT_ARN=$NEW_CERT_ARN"
echo "export CF_CERT_ARN=$NEW_CF_CERT_ARN"
```

---

## Summary

| Step | Action | Status |
|------|--------|--------|
| 1 | Request ACM cert for ALB (us-west-2) | |
| 2 | Request ACM cert for CloudFront (us-east-1) | |
| 3 | Add DNS validation CNAME at reflexio.ai DNS provider | |
| 4 | Swap ALB HTTPS listener to new cert | |
| 5 | Update CloudFront aliases + cert | |
| 6 | Add www CNAME + root domain DNS for reflexio.ai | |
| 7 | Remove old agenticmem.com DNS records | |
| 8 | Verify all endpoints on new domain | |
| 9 | Delete old ACM certificates | |
| 10 | Update saved env vars | |

> **Downtime**: Zero downtime. The old domain continues to work until you remove its DNS records in Step 7. You can run the old and new domains in parallel during the transition.
