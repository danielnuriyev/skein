#!/bin/bash

# Monitor Goose services in Kubernetes

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Monitoring Goose services in Kubernetes...${NC}"
echo

# Function to check pod status
check_pod_status() {
    local pod_name="$1"
    local status

    status=$(kubectl get pod -n goose-system -l "app=${pod_name}" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")

    case "${status}" in
        "Running")
            echo -e "${GREEN}✅ ${pod_name}: ${status}${NC}"
            ;;
        "Pending"|"ContainerCreating")
            echo -e "${YELLOW}⏳ ${pod_name}: ${status}${NC}"
            ;;
        "Failed"|"CrashLoopBackOff")
            echo -e "${RED}❌ ${pod_name}: ${status}${NC}"
            ;;
        "NotFound")
            echo -e "${RED}❌ ${pod_name}: Not deployed${NC}"
            ;;
        *)
            echo -e "${YELLOW}⚠️  ${pod_name}: ${status}${NC}"
            ;;
    esac
}

# Function to check service health
check_service_health() {
    local service_name="$1"
    local port="$2"

    # Get service cluster IP
    local cluster_ip
    cluster_ip=$(kubectl get service "${service_name}" -n goose-system -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")

    if [ -z "${cluster_ip}" ]; then
        echo -e "${RED}❌ ${service_name}: Service not found${NC}"
        return
    fi

    # Check if service is responding
    if kubectl run test-pod --image=busybox --rm -i --restart=Never -- sh -c "nc -z ${cluster_ip} ${port} && echo 'OK'" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ${service_name}: Healthy${NC}"
    else
        echo -e "${RED}❌ ${service_name}: Unhealthy${NC}"
    fi
}

echo -e "${BLUE}🔍 Pod Status:${NC}"
check_pod_status "litellm"
check_pod_status "goose-server"
check_pod_status "slack-server"
check_pod_status "slack-events"
check_pod_status "github-pr-reviewer"

echo
echo -e "${BLUE}🏥 Service Health:${NC}"
check_service_health "litellm-service" "4321"
check_service_health "goose-server-service" "8765"
check_service_health "slack-server-service" "3000"
check_service_health "slack-events-service" "3001"
check_service_health "github-pr-reviewer-service" "4000"

echo
echo -e "${BLUE}📋 Detailed Information:${NC}"

# Show resource usage
echo
echo -e "${YELLOW}Resource Usage:${NC}"
kubectl top pods -n goose-system 2>/dev/null || echo "Metrics not available (metrics-server not installed)"

# Show recent events
echo
echo -e "${YELLOW}Recent Events:${NC}"
kubectl get events -n goose-system --sort-by='.lastTimestamp' | tail -10

# Show logs summary (last few lines from each pod)
echo
echo -e "${YELLOW}Recent Logs:${NC}"
pods=$(kubectl get pods -n goose-system -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

for pod in ${pods}; do
    echo -e "${BLUE}${pod}:${NC}"
    kubectl logs --tail=3 "${pod}" -n goose-system 2>/dev/null | head -3 || echo "  No logs available"
    echo
done

echo -e "${GREEN}📊 Monitoring complete!${NC}"