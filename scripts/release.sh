#!/bin/bash
# Release script for AgentGuard
# Usage: ./scripts/release.sh [patch|minor|major]

set -e

VERSION_BUMP=${1:-patch}
echo "🚀 Releasing AgentGuard with $VERSION_BUMP version bump..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "${RED}❌ python3 not found${NC}"
    exit 1
fi

if ! command -v pip &> /dev/null; then
    echo "${RED}❌ pip not found${NC}"
    exit 1
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info

# Install build dependencies
echo "📦 Installing build dependencies..."
pip install --quiet build twine bump2version

# Run tests
echo "🧪 Running tests..."
python3 -m pytest tests/ -q --tb=short
if [ $? -ne 0 ]; then
    echo "${RED}❌ Tests failed. Aborting release.${NC}"
    exit 1
fi
echo "${GREEN}✅ Tests passed${NC}"

# Build package
echo "🔨 Building package..."
python3 -m build

# Check package
echo "🔍 Checking package..."
twine check dist/*

# Show what will be uploaded
echo ""
echo "📤 Package ready for upload:"
ls -lh dist/
echo ""

# Upload to PyPI (test first)
echo "📝 To upload to Test PyPI first:"
echo "   twine upload --repository testpypi dist/*"
echo ""
echo "🚀 To upload to Production PyPI:"
echo "   twine upload dist/*"
echo ""

# Optional: Auto-upload with confirmation
read -p "Upload to PyPI now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Uploading to PyPI..."
    twine upload dist/*
    echo "${GREEN}✅ Released successfully!${NC}"
else
    echo "${YELLOW}⏸️ Upload skipped. Run 'twine upload dist/*' manually when ready.${NC}"
fi
