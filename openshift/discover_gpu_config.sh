#!/bin/bash
# Run when logged in to OCP: oc login ...
# Discovers GPU resource name, node labels, and taints so you can match deployment.yaml

set -e
echo "=== 1. Node allocatable resources (look for nvidia.com/gpu or amd.com/gpu) ==="
oc get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{.status.allocatable}{"\n---\n"}{end}' 2>/dev/null || true

echo ""
echo "=== 2. Nodes that advertise GPU ==="
for n in $(oc get nodes -o jsonpath='{.items[*].metadata.name}'); do
  gpu=$(oc get node "$n" -o jsonpath='{.status.allocatable.nvidia\.com/gpu}' 2>/dev/null)
  amd=$(oc get node "$n" -o jsonpath='{.status.allocatable.amd\.com/gpu}' 2>/dev/null)
  if [[ -n "$gpu" && "$gpu" != "0" ]] || [[ -n "$amd" && "$amd" != "0" ]]; then
    echo "Node: $n  nvidia.com/gpu=$gpu  amd.com/gpu=$amd"
  fi
done

echo ""
echo "=== 3. Labels on first GPU node (for nodeSelector) ==="
gpu_node=$(oc get nodes -o jsonpath='{range .items[*]}{@.metadata.name}{" "}{@.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | awk '$2>0 {print $1; exit}')
if [[ -z "$gpu_node" ]]; then
  gpu_node=$(oc get nodes -o jsonpath='{range .items[*]}{@.metadata.name}{" "}{@.status.allocatable.amd\.com/gpu}{"\n"}{end}' 2>/dev/null | awk '$2>0 {print $1; exit}')
fi
if [[ -n "$gpu_node" ]]; then
  oc get node "$gpu_node" -o jsonpath='{range .metadata.labels}{@.key}{"="}{@.value}{"\n"}{end}' 2>/dev/null | grep -E 'gpu|nvidia|amd|accelerator' || true
else
  echo "No GPU node found in allocatable. Listing all node labels for first node:"
  oc get nodes -o jsonpath='{.items[0].metadata.name}' | xargs -I {} oc get node {} -o jsonpath='{range .metadata.labels}{@.key}{"="}{@.value}{"\n"}{end}' 2>/dev/null | head -30
fi

echo ""
echo "=== 4. Taints on nodes (if GPU nodes are tainted, deployment may need tolerations) ==="
oc get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.taints}{"\n"}{end}' 2>/dev/null || true

echo ""
echo "=== 5. Example: use nvidia.com/gpu in deployment ==="
echo "  resources:"
echo "    limits:"
echo "      nvidia.com/gpu: \"1\""
echo "    requests:"
echo "      nvidia.com/gpu: \"1\""
echo "If your cluster uses amd.com/gpu, replace nvidia.com/gpu in deployment.yaml"
