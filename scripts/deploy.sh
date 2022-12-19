#!/bin/bash
set -e
echo "USAGE: ./deploy.sh VERSION"



image="${image:-quay.io/domino/gcpworkloadidentity}"
platform_namespace="${platform_namespace:-domino-platform}"
compute_namespace="${compute_namespace:-domino-compute}"


deployment_name="gcpworkloadidentity"

VERSION=$1
GCP_PROJECT_ID=$2
GCP_REGION=$3
GCP_GKE_ID=$4


if [ -z "$VERSION" ]
then
      echo "Please specify a version."
      exit 1
fi

secret="${deployment_name}-certs"
service="${deployment_name}-svc"
echo "Creating Service Account"

if [ ! -x "$(command -v openssl)" ]; then
    echo "openssl not found"
    exit 1
fi


csrName=${service}.${platform_namespace}
tmpdir=$(mktemp -d)
echo "creating certs in tmpdir ${tmpdir} "

cat <<EOF >> ${tmpdir}/req.conf
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = ${service}
DNS.2 = ${service}.${platform_namespace}
DNS.3 = ${service}.${platform_namespace}.svc
EOF


# Create CA Key
openssl genrsa -out ${tmpdir}/ca.key 2048

# Create CA Cert
openssl req -new -key ${tmpdir}/ca.key -x509 -out ${tmpdir}/ca.crt -days 3650 -subj "/CN=ca"


# Create Server Key and Signing Request
openssl req -new -nodes -newkey rsa:2048 -keyout ${tmpdir}/server.key -out ${tmpdir}/server.req -batch -config ${tmpdir}/req.conf -subj "/"

# Create Signed Server Cert
openssl x509 -req -in ${tmpdir}/server.req -CA ${tmpdir}/ca.crt -CAkey ${tmpdir}/ca.key -CAcreateserial -out ${tmpdir}/server.crt -days 3650 -sha256 -extensions v3_req -extfile ${tmpdir}/req.conf


# create the secret with CA cert and server cert/key
kubectl create secret generic ${secret} \
        --from-file=tls.key=${tmpdir}/server.key \
        --from-file=tls.crt=${tmpdir}/server.crt \
        --dry-run -o yaml |
    kubectl -n ${platform_namespace} apply -f -

CA_BUNDLE=$(cat ${tmpdir}/server.crt | base64 | tr -d '\n\r')


cat <<EOF | kubectl create -n ${platform_namespace} -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${deployment_name}
  namespace: ${platform_namespace}
EOF

cat <<EOF | kubectl create -n ${platform_namespace} -f -
kind: Role
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: ${deployment_name}-1
  namespace: ${platform_namespace}
rules:
- apiGroups:
  - ""
  resources:
  - "configmaps"
  verbs:
  - "get"
  - "update"
  - "patch"
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: ${deployment_name}-1
  namespace: ${platform_namespace}
subjects:
- kind: ServiceAccount
  name: ${deployment_name}
  namespace: ${platform_namespace}
roleRef:
  kind: Role
  name: ${deployment_name}-1
  apiGroup: rbac.authorization.k8s.io
EOF

cat <<EOF | kubectl create -n ${compute_namespace} -f -
kind: Role
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: ${deployment_name}-2
  namespace: ${compute_namespace}
rules:
- apiGroups:
  - ""
  resources:
  - "serviceaccounts"
  verbs:
  - "get"
  - "create"
  - "patch"
- apiGroups:
  - ""
  resources:
  - "pods"
  verbs:
  - "get"
  - "watch"
  - "list"
- apiGroups:
  - ""
  resources:
  - "services"
  verbs:
  - "get"
- apiGroups:
  - "rbac.authorization.k8s.io"
  resources:
  - "rolebindings"
  verbs:
  - "patch"
- apiGroups:
  - ""
  resources:
  - "configmaps"
  verbs:
  - "create"
  - "get"
  - "update"
  - "patch"
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: ${deployment_name}-2
  namespace: ${compute_namespace}
subjects:
- kind: ServiceAccount
  name: ${deployment_name}
  namespace: ${platform_namespace}
roleRef:
  kind: Role
  name: ${deployment_name}-2
  apiGroup: rbac.authorization.k8s.io
EOF

echo "Creating Deployment"
cat <<EOF | kubectl create -n ${platform_namespace} -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${deployment_name}
  namespace: ${platform_namespace}
  labels:
    app: ${deployment_name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${deployment_name}
  template:
    metadata:
      labels:
        app: ${deployment_name}
        nucleus-client: "true"
        security.istio.io/tlsMode: "istio"
    spec:
      serviceAccountName: ${deployment_name}
      automountServiceAccountToken: true
      nodeSelector:
        dominodatalab.com/node-pool: platform

      containers:
      - name: ${deployment_name}
        securityContext:
          runAsUser: 1000
          runAsGroup: 1000
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - all
        image: ${image}:${VERSION}
        env:
        - name: DOMINO_USER_HOST
          value: http://nucleus-frontend.${platform_namespace}
        - name: DEFAULT_PLATFORM_NS
          value: ${platform_namespace}
        - name: DEFAULT_COMPUTE_NS
          value: ${compute_namespace}
        - name: GCP_PROJECT_ID
          value: ${GCP_PROJECT_ID}
        - name: GCP_PROJECT_LOCATION
          value: ${GCP_REGION}
        - name: GCP_GKE_ID
          value: ${GCP_GKE_ID}
        ports:
        - containerPort: 6000
        livenessProbe:
          httpGet:
            path: /healthz
            port: 6000
            scheme: HTTP
          initialDelaySeconds: 20
          failureThreshold: 2
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /healthz
            port: 6000
            scheme: HTTP
          initialDelaySeconds: 20
          failureThreshold: 2
          timeoutSeconds: 5
        imagePullPolicy: Always
        volumeMounts:
          - name: certs
            mountPath: /ssl
            readOnly: true
      volumes:
        - name: certs
          secret:
            secretName: ${secret}
EOF



# Wait for the app to actually be up before starting the webhook.
let tries=1
availreps=""
while [[ ${tries} -lt 10 && "${availreps}" != "1" ]]; do
  echo "Checking deployment, try $tries"
  kubectl get deployment -n ${platform_namespace} ${deployment_name}
  availreps=$(kubectl get deployment -n ${platform_namespace} ${deployment_name} -o jsonpath='{.status.availableReplicas}')
  let tries+=1
  sleep 10
done

echo "Creating Service"

cat <<EOF | kubectl create -n ${platform_namespace} -f -
apiVersion: v1
kind: Service
metadata:
  labels:
    app: ${deployment_name}
  name: ${service}
spec:
  ports:
  - name: http
    port: 80
    targetPort: 6000
  selector:
    app: ${deployment_name}
  sessionAffinity: None
  type: ClusterIP
EOF

if [[ ${availreps} != "1" ]]; then
  echo "Deployment never became available, exiting."
  exit 1
fi

cat <<EOF | kubectl create -n ${platform_namespace} -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: domino-org-gcp-svc-account-mapping
data:
EOF

cat <<EOF | kubectl create -n ${platform_namespace} -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: domino-user-current-org-mapping
data: {
}
EOF

echo "Creating Network Policy"


cat <<EOF | kubectl create -n ${platform_namespace} -f -
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata:
    name: ${deployment_name}
    namespace: ${platform_namespace}
  spec:
    ingress:
     - ports:
          - protocol: TCP
            port: 6000
       from:
          - podSelector:
              matchLabels:
                nucleus-client: 'true'
            namespaceSelector:
              matchLabels:
                domino-platform: 'true'
          - podSelector:
              matchLabels:
                nucleus-client: 'true'
            namespaceSelector:
              matchLabels:
                domino-compute: 'true'
    podSelector:
      matchLabels:
        app: ${deployment_name}
    policyTypes:
    - Ingress
EOF


