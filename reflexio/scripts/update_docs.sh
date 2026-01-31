#!/bin/bash
# Script to update MkDocs documentation website on AWS (S3 + CloudFront)
#
# Usage:
#   ./update_docs.sh           # Build and deploy docs
#   ./update_docs.sh --build   # Only build docs locally (no deploy)
#   ./update_docs.sh --deploy  # Only deploy (skip build, use existing site/)
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - mkdocs and mkdocs-material installed (poetry install)
#   - S3 bucket and CloudFront distribution already set up
#
# Reference: docs/aws-ecs-upgrade-option-a.md (Step 16)

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
S3_BUCKET_NAME="${S3_BUCKET_NAME:-agenticmem}"
CF_DISTRIBUTION_ID="${CF_DISTRIBUTION_ID:-E15WBN9QYYCSND}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCS_DIR="$PROJECT_ROOT/reflexio/public_docs"
SITE_DIR="$DOCS_DIR/site"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Update MkDocs documentation website on AWS (S3 + CloudFront).

Options:
    --build     Only build docs locally (no deploy)
    --deploy    Only deploy (skip build, use existing site/)
    --help      Show this help message

Examples:
    $(basename "$0")           # Build and deploy docs
    $(basename "$0") --build   # Only build docs locally
    $(basename "$0") --deploy  # Deploy existing build

Configuration (via environment variables):
    AWS_REGION          AWS region (default: us-west-2)
    S3_BUCKET_NAME      S3 bucket name (default: reflexio)
    CF_DISTRIBUTION_ID  CloudFront distribution ID (default: E15WBN9QYYCSND)
EOF
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Check mkdocs
    if ! command -v mkdocs &> /dev/null; then
        log_error "mkdocs is not installed. Run 'poetry install' first."
        exit 1
    fi

    log_success "All prerequisites met."
}

build_docs() {
    log_info "Building MkDocs documentation..."

    cd "$DOCS_DIR"

    # Check if mkdocs.yml exists
    if [[ ! -f "mkdocs.yml" ]]; then
        log_error "mkdocs.yml not found in $DOCS_DIR"
        exit 1
    fi

    # Build the site
    mkdocs build --clean

    if [[ -d "$SITE_DIR" ]]; then
        local file_count=$(find "$SITE_DIR" -type f | wc -l | tr -d ' ')
        log_success "Documentation built successfully ($file_count files in $SITE_DIR)"
    else
        log_error "Build failed: $SITE_DIR directory not created"
        exit 1
    fi
}

deploy_to_s3() {
    log_info "Uploading documentation to S3..."

    # Check if site directory exists
    if [[ ! -d "$SITE_DIR" ]]; then
        log_error "$SITE_DIR directory not found. Run with --build first or without flags."
        exit 1
    fi

    # Sync to S3 with /docs/ prefix
    aws s3 sync "$SITE_DIR/" "s3://$S3_BUCKET_NAME/docs/" \
        --delete \
        --region "$AWS_REGION"

    log_success "Documentation uploaded to s3://$S3_BUCKET_NAME/docs/"
}

invalidate_cloudfront() {
    log_info "Invalidating CloudFront cache..."

    # Create invalidation for /docs/* path
    local invalidation_id=$(aws cloudfront create-invalidation \
        --distribution-id "$CF_DISTRIBUTION_ID" \
        --paths "/docs/*" \
        --query 'Invalidation.Id' \
        --output text)

    log_success "CloudFront invalidation created: $invalidation_id"
    log_info "Cache invalidation typically takes 1-5 minutes to complete."
}

print_summary() {
    echo ""
    echo "=========================================="
    log_success "Documentation update complete!"
    echo "=========================================="
    echo ""
    echo "URLs:"
    echo "  - Production: https://reflexio.com/docs/"
    echo "  - S3 Direct:  http://$S3_BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/docs/"
    echo ""
    echo "CloudFront Distribution: $CF_DISTRIBUTION_ID"
    echo ""
}

# Parse arguments
BUILD_ONLY=false
DEPLOY_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_ONLY=true
            shift
            ;;
        --deploy)
            DEPLOY_ONLY=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate mutually exclusive options
if [[ "$BUILD_ONLY" == true && "$DEPLOY_ONLY" == true ]]; then
    log_error "--build and --deploy are mutually exclusive"
    exit 1
fi

# Main execution
echo ""
echo "=========================================="
echo "  MkDocs Documentation Update Script"
echo "=========================================="
echo ""
log_info "AWS Region: $AWS_REGION"
log_info "S3 Bucket: $S3_BUCKET_NAME"
log_info "CloudFront Distribution: $CF_DISTRIBUTION_ID"
echo ""

if [[ "$BUILD_ONLY" == true ]]; then
    check_prerequisites
    build_docs
    log_success "Build complete. Run with --deploy to upload."
elif [[ "$DEPLOY_ONLY" == true ]]; then
    check_prerequisites
    deploy_to_s3
    invalidate_cloudfront
    print_summary
else
    # Full build and deploy
    check_prerequisites
    build_docs
    deploy_to_s3
    invalidate_cloudfront
    print_summary
fi
