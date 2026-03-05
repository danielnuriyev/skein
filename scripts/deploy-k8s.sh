#!/bin/bash

# Deploy Goose ecosystem to Kubernetes
# This script deploys all services to the k8s cluster

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
K8S_DIR="${PROJECT_DIR}/k8s"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to apply Kubernetes manifests
apply_manifest() {
    local file="$1"
    local description="$2"

    echo -e "${YELLOW}Applying ${description}...${NC}"
    if kubectl apply -f "${file}"; then
        echo -e "${GREEN}✅ ${description} applied successfully${NC}"
    else
        echo -e "${RED}❌ Failed to apply ${description}${NC}"
        exit 1
    fi
}

# Function to wait for deployment rollout
wait_for_deployment() {
    local deployment="$1"
    local namespace="$2"

    echo -e "${YELLOW}Waiting for ${deployment} to be ready...${NC}"
    if kubectl rollout status deployment/"${deployment}" -n "${namespace}" --timeout=300s; then
        echo -e "${GREEN}✅ ${deployment} is ready${NC}"
    else
        echo -e "${RED}❌ ${deployment} failed to become ready${NC}"
        exit 1
    fi
}

echo -e "${BLUE}🚀 Deploying Goose ecosystem to Kubernetes...${NC}"
echo

# Check if kubectl is available
if ! command -v kubectl >/dev/null 2>&1; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if we're connected to a cluster
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${RED}❌ Not connected to a Kubernetes cluster.${NC}"
    echo "Please ensure you're connected to your k8s cluster."
    exit 1
fi

echo -e "${BLUE}📋 Applying Kubernetes manifests...${NC}"

# Apply manifests in order
apply_manifest "${K8S_DIR}/namespace.yaml" "namespace"
apply_manifest "${K8S_DIR}/configmap.yaml" "config maps"
apply_manifest "${K8S_DIR}/secret.yaml" "secrets"
apply_manifest "${K8S_DIR}/litellm-configmap.yaml" "LiteLLM config"
apply_manifest "${K8S_DIR}/goose-configmaps.yaml" "Goose config maps"

# Deploy services
apply_manifest "${K8S_DIR}/litellm-deployment.yaml" "LiteLLM deployment"
apply_manifest "${K8S_DIR}/goose-server-deployment.yaml" "Goose server deployment"
apply_manifest "${K8S_DIR}/slack-server-deployment.yaml" "Slack server deployment"
apply_manifest "${K8S_DIR}/slack-events-deployment.yaml" "Slack events deployment"
apply_manifest "${K8S_DIR}/github-pr-reviewer-deployment.yaml" "GitHub PR reviewer deployment"

echo
echo -e "${BLUE}⏳ Waiting for deployments to be ready...${NC}"

# Wait for all deployments
wait_for_deployment "litellm" "goose-system"
wait_for_deployment "goose-server" "goose-system"
wait_for_deployment "slack-server" "goose-system"
wait_for_deployment "slack-events" "goose-system"
wait_for_deployment "github-pr-reviewer" "goose-system"

echo
echo -e "${BLUE}📊 Deployment Status:${NC}"
kubectl get pods -n goose-system
kubectl get services -n goose-system

echo
echo -e "${GREEN}🎉 Goose ecosystem deployed successfully!${NC}"
echo
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Update secrets with your actual API keys:"
echo "   kubectl edit secret goose-secrets -n goose-system"
echo
echo "2. Get service URLs:"
echo "   kubectl get services -n goose-system"
echo
echo "3. Check logs:"
echo "   kubectl logs -f deployment/litellm -n goose-system"
echo "   kubectl logs -f deployment/goose-server -n goose-system"
echo
echo -e "${BLUE}💡 Management commands:${NC}"
echo "  ./scripts/start-k8s.sh    # Start all services"
echo "  ./scripts/stop-k8s.sh     # Stop all services"
echo "  ./scripts/monitor-k8s.sh  # Monitor all services"