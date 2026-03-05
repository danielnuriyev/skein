#!/bin/bash

# Stop Goose services in Kubernetes

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Goose services in Kubernetes...${NC}"

# Scale deployments to 0 replicas
deployments=("litellm" "goose-server" "slack-server" "slack-events" "github-pr-reviewer")

for deployment in "${deployments[@]}"; do
    echo -e "${YELLOW}Stopping ${deployment}...${NC}"
    kubectl scale deployment "${deployment}" --replicas=0 -n goose-system
done

echo
echo -e "${GREEN}✅ All Goose services stopped!${NC}"
echo
echo -e "${BLUE}📊 Service Status:${NC}"
kubectl get pods -n goose-system