#!/usr/bin/env bash
set -euo pipefail

REGION="ap-northeast-2"
remaining=0
errors=0

export AWS_PAGER=""

check_count() {
  local label="$1"
  local count
  shift

  if count="$(aws "$@" --region "$REGION" --output json)"; then
    if [[ "$count" =~ ^[0-9]+$ ]]; then
      if [[ "$count" -eq 0 ]]; then
        printf '[OK] %s: 0\n' "$label"
      else
        printf '[CHECK] %s: %s\n' "$label" "$count"
        remaining=1
      fi
    else
      printf '[ERROR] %s: unexpected response\n' "$label"
      errors=1
    fi
  else
    printf '[ERROR] %s: query failed\n' "$label"
    errors=1
  fi
}

echo "Read-only cleanup check: $REGION"
echo "AWS identity:"
aws sts get-caller-identity \
  --region "$REGION" \
  --query '{Account:Account,Arn:Arn}' \
  --output json

check_count "EKS clusters" \
  eks list-clusters \
  --query 'length(clusters)'

check_count "Non-terminated EC2 instances" \
  ec2 describe-instances \
  --filters "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down" \
  --query 'length(Reservations[].Instances[])'

check_count "EBS volumes" \
  ec2 describe-volumes \
  --query 'length(Volumes)'

check_count "ALB/NLB/GWLB" \
  elbv2 describe-load-balancers \
  --query 'length(LoadBalancers)'

check_count "Non-deleted NAT gateways" \
  ec2 describe-nat-gateways \
  --filter "Name=state,Values=pending,available,deleting,failed" \
  --query 'length(NatGateways)'

check_count "Elastic IP allocations" \
  ec2 describe-addresses \
  --query 'length(Addresses)'

echo "Scope: these six resource categories in this region only."
echo "ECR storage, other services/regions and accrued charges are not checked."

if [[ "$errors" -ne 0 ]]; then
  echo "INCOMPLETE: one or more queries failed."
  exit 2
fi

if [[ "$remaining" -ne 0 ]]; then
  echo "REVIEW: resources remain. Nothing was deleted."
  exit 1
fi

echo "PASS: all six queried resource categories are empty."
