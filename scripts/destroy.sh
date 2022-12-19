#!/bin/bash
set -x
echo "USAGE: ./destroy.sh"

platform_namespace="${platform_namespace:-domino-platform}"
compute_namespace="${compute_namespace:-domino-compute}"
deployment_name="gcpworkloadidentity"
secret="${name}-webhook-certs"
service="${deployment_name}-svc"

kubectl delete secret ${secret} -n ${platform_namespace}
kubectl delete serviceaccount ${deployment_name} -n ${platform_namespace}
kubectl delete role ${deployment_name}-1 -n ${platform_namespace}
kubectl delete rolebinding ${deployment_name}-1  -n ${platform_namespace}
kubectl delete role ${deployment_name}-2  -n ${compute_namespace}
kubectl delete rolebinding ${deployment_name}-2  -n ${compute_namespace}

kubectl delete deployment -n ${platform_namespace} "${deployment_name}"
kubectl delete service -n ${platform_namespace} ${service}
kubectl delete networkpolicy -n ${platform_namespace} "${deployment_name}"

kubectl delete configmap -n ${platform_namespace} domino-org-gcp-svc-account-mapping
kubectl delete configmap -n ${platform_namespace} domino-user-current-org-mapping