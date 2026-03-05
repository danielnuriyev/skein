#!/bin/bash

# Start Goose services in Kubernetes

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Goose services in Kubernetes...${NC}"

# Scale deployments to 1 replica
deployments=("litellm" "goose-server" "slack-server" "slack-events" "github-pr-reviewer")

for deployment in "${deployments[@]}"; do
    echo -e "${YELLOW}Starting ${deployment}...${NC}"
    kubectl scale deployment "${deployment}" --replicas=1 -n goose-system

    # Wait for deployment to be ready
    kubectl rollout status deployment/"${deployment}" -n goose-system --timeout=60s
done

echo
echo -e "${GREEN}✅ All Goose services started!${NC}"
echo
echo -e "${BLUE}📊 Service Status:${NC}"
kubectl get pods -n goose-system
kubectl get services -n goose-system