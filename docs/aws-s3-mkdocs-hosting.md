# Hosting Static MkDocs Website on AWS S3

This guide provides step-by-step instructions to host, update, and delete a static MkDocs documentation website on AWS S3.

## Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Python and pip installed
- MkDocs installed (`pip install mkdocs`)
- An AWS account with S3 permissions

## Step 1: Build the MkDocs Site

First, build your MkDocs documentation into static HTML files:

```bash
# Navigate to your MkDocs project directory (where mkdocs.yml is located)
cd reflexio/public_docs

# Build the static site
mkdocs build
```

This creates a `site/` directory containing all the static HTML, CSS, and JavaScript files.

## Step 2: Create an S3 Bucket

Create a new S3 bucket for hosting your documentation:

```bash
# Create the bucket
aws s3 mb s3://reflexio --region us-east-1
```

## Step 3: Configure S3 Bucket for Static Website Hosting

### Enable Static Website Hosting

```bash
aws s3 website s3://reflexio \
  --index-document index.html \
  --error-document 404.html
```

### Disable Block Public Access

```bash
aws s3api put-public-access-block \
  --bucket reflexio \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

### Add Bucket Policy for Public Read Access

Create a file named `bucket-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::reflexio/*"
    }
  ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
  --bucket reflexio \
  --policy file://bucket-policy.json
```

## Step 4: Upload the MkDocs Site to S3

Upload all files from the `site/` directory to your S3 bucket:

```bash
aws s3 sync site/ s3://reflexio --delete
```

The `--delete` flag removes files from S3 that no longer exist in the local `site/` directory.

## Step 5: Access Your Website

Your documentation is now available at:

```
http://reflexio.s3-website-us-west-2.amazonaws.com/

```

Follow this format:
```
http://YOUR_BUCKET_NAME.s3-website-REGION.amazonaws.com
```

---

## Updating the Documentation

When you make changes to your documentation:

### Option 1: Full Rebuild and Sync

```bash
# Rebuild the site
mkdocs build

# Sync to S3 (uploads changed files, removes deleted files)
aws s3 sync site/ s3://reflexio --delete
```

### Option 2: Upload Only Changed Files

```bash
# Rebuild the site
mkdocs build

# Sync without deleting (keeps old files)
aws s3 sync site/ s3://reflexio
```

### Option 3: Upload Specific Files

```bash
# Upload a single file
aws s3 cp site/index.html s3://reflexio/index.html

# Upload a specific directory
aws s3 sync site/guides/ s3://reflexio/guides/
```

---

## Deleting the Website

### Option 1: Delete All Contents but Keep Bucket

```bash
# Remove all objects from the bucket
aws s3 rm s3://reflexio --recursive
```

### Option 2: Delete Bucket and All Contents

```bash
# First, remove all objects (required before bucket deletion)
aws s3 rm s3://reflexio --recursive

# Then delete the bucket
aws s3 rb s3://reflexio
```

### Option 3: Force Delete (Shortcut)

```bash
# Delete bucket and all contents in one command
aws s3 rb s3://reflexio --force
```

---

## Optional: Add CloudFront CDN

For better performance and HTTPS support, add CloudFront in front of your S3 bucket:

### Create CloudFront Distribution

```bash
aws cloudfront create-distribution \
  --origin-domain-name YOUR_BUCKET_NAME.s3-website-us-east-1.amazonaws.com \
  --default-root-object index.html
```

### Invalidate CloudFront Cache After Updates

When you update your documentation, invalidate the CloudFront cache:

```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

---

## Optional: Custom Domain Setup

To use a custom domain (e.g., `docs.example.com`):

1. **Create/Update Route 53 Record** (if using Route 53):
   ```bash
   # Create an alias record pointing to your S3 website endpoint
   aws route53 change-resource-record-sets \
     --hosted-zone-id YOUR_HOSTED_ZONE_ID \
     --change-batch file://dns-record.json
   ```

2. **Bucket Name Requirement**: Your bucket name must match your domain name exactly (e.g., `docs.example.com`).

---

## Automation Script

Create a deployment script `deploy-docs.sh`:

```bash
#!/bin/bash
set -e

BUCKET_NAME="YOUR_BUCKET_NAME"

echo "Building MkDocs site..."
mkdocs build

echo "Deploying to S3..."
aws s3 sync site/ s3://$BUCKET_NAME --delete

echo "Deployment complete!"
echo "Site available at: http://$BUCKET_NAME.s3-website-us-east-1.amazonaws.com"
```

Make it executable:

```bash
chmod +x deploy-docs.sh
```

Run the deployment:

```bash
./deploy-docs.sh
```

---

## Troubleshooting

### 403 Forbidden Error
- Ensure the bucket policy allows public read access
- Verify Block Public Access settings are disabled
- Check that the bucket policy JSON is correctly formatted

### 404 Not Found Error
- Verify `index.html` exists in the bucket root
- Check that static website hosting is enabled
- Ensure the correct index document is configured

### Changes Not Appearing
- Wait a few seconds for S3 propagation
- If using CloudFront, invalidate the cache
- Clear your browser cache

### Access Denied When Uploading
- Verify your AWS CLI credentials have `s3:PutObject` permission
- Check IAM policies attached to your user/role
