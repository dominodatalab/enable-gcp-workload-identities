from kubernetes import client, config
from kubernetes.client import V1ObjectMeta, V1PodList
from kubernetes.client.models.v1_service_account import V1ServiceAccount
from kubernetes.client.models.v1_config_map import  V1ConfigMap
import requests
import os
import gcp_utils

DEFAULT_PLATFORM_NS = 'domino-platform'
DEFAULT_COMPUTE_NS = 'domino-compute'
CONFIG_MAP_ORG_TO_GCP_SVC_ACCOUNT_MAPPING = 'domino-org-gcp-svc-account-mapping'
CONFIG_MAP_DOMINO_USER_CURRENT_ORG_MAPPING = 'domino-user-current-org-mapping'

def save_user_default_org(domino_user_id,domino_org,platform_ns: DEFAULT_PLATFORM_NS):

    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    domino_user_to_org_mapping: V1ConfigMap = v1.read_namespaced_config_map(CONFIG_MAP_DOMINO_USER_CURRENT_ORG_MAPPING,
                                                                     platform_ns)
    if not domino_user_to_org_mapping.data:
        domino_user_to_org_mapping.data = {}
    domino_user_to_org_mapping.data[domino_user_id] = domino_org
    v1.patch_namespaced_config_map(CONFIG_MAP_DOMINO_USER_CURRENT_ORG_MAPPING,
                                                                     platform_ns,domino_user_to_org_mapping.to_dict())

def get_user_default_org(domino_api_key,platform_ns: DEFAULT_PLATFORM_NS):
    domino_user_id = get_user_id(domino_api_key)
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    domino_user_to_org_mapping: V1ConfigMap = v1.read_namespaced_config_map(CONFIG_MAP_DOMINO_USER_CURRENT_ORG_MAPPING,
                                                                     platform_ns)
    if domino_user_to_org_mapping.data and \
            domino_user_id in domino_user_to_org_mapping.data:
        return domino_user_to_org_mapping.data[domino_user_id]
    return None

def annotate_pod_service_account(pod_svc_account,gcp_service_account,pod_namespace=DEFAULT_COMPUTE_NS):
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    svc_account:V1ServiceAccount = v1.read_namespaced_service_account(pod_svc_account,pod_namespace)
    svc_meta:V1ObjectMeta = svc_account.metadata
    if not svc_meta.annotations:
        svc_meta.annotations = {}
    if gcp_service_account:
        svc_meta.annotations['iam.gke.io/gcp-service-account']=gcp_service_account
    else:
        svc_meta.annotations['iam.gke.io/gcp-service-account']=''
    print(v1.patch_namespaced_service_account(pod_svc_account,pod_namespace,svc_account.to_dict()))

def pod_svc_account_annotations(pod_svc_account,pod_namespace=DEFAULT_COMPUTE_NS):
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    svc_account:V1ServiceAccount = v1.read_namespaced_service_account(pod_svc_account,pod_namespace)
    svc_meta:V1ObjectMeta = svc_account.metadata
    if not svc_meta.annotations:
        svc_meta.annotations = {}
    return svc_meta.annotations

def get_orgs_gcp_service_accounts_mapping(platform_ns:DEFAULT_PLATFORM_NS):
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    org_gcp_svc_mapping:V1ConfigMap = v1.read_namespaced_config_map(CONFIG_MAP_ORG_TO_GCP_SVC_ACCOUNT_MAPPING,
                                                                    platform_ns)
    return org_gcp_svc_mapping.data

def update_orgs_gcp_service_accounts_mapping(domino_org,gcp_sa,platform_ns:DEFAULT_PLATFORM_NS):
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    org_gcp_svc_mapping:V1ConfigMap = v1.read_namespaced_config_map(CONFIG_MAP_ORG_TO_GCP_SVC_ACCOUNT_MAPPING,
                                                                    platform_ns)
    if not org_gcp_svc_mapping.data:
        org_gcp_svc_mapping.data = {}
    old_gcp_sa =  org_gcp_svc_mapping.data[domino_org]
    org_gcp_svc_mapping.data[domino_org] = gcp_sa
    v1.patch_namespaced_config_map(CONFIG_MAP_ORG_TO_GCP_SVC_ACCOUNT_MAPPING,
                                   platform_ns, org_gcp_svc_mapping.to_dict())
    return old_gcp_sa, gcp_sa

def apply_service_account(domino_api_key,run_id,domino_org,pod_namespace=DEFAULT_COMPUTE_NS,
                                                         platform_namespace=DEFAULT_PLATFORM_NS):
    orgs_gcp_service_accounts_map = get_orgs_gcp_service_accounts_mapping(platform_namespace)
    if not domino_org:
        return True, f'No org passed.'

    if not org_belongs_to_user(domino_api_key,domino_org):
        return False,f'User does not belong to org {domino_org}'

    if not domino_org in orgs_gcp_service_accounts_map:
        return False,'Domino Org Not Mapped to GCP Service Account'
    else:
        gcp_service_account = orgs_gcp_service_accounts_map[domino_org]

    if gcp_service_account:
        domino_user_id = get_user_id(domino_api_key)
        pod_service_account = get_pod_service_account(domino_api_key,run_id,pod_namespace)
        gcp_utils.add_iam_policy_binding(gcp_service_account, pod_namespace,pod_service_account)
        annotate_pod_service_account(pod_service_account,gcp_service_account,pod_namespace)
        save_user_default_org(domino_user_id,domino_org,platform_namespace)
        return True, f'User now assumes the GCP Service Account {gcp_service_account}'
    else:
        return False, f'Unknown error, gcp_service_account not found'

def remove_service_account(domino_api_key,run_id,pod_namespace=DEFAULT_COMPUTE_NS):
    pod_service_account = get_pod_service_account(domino_api_key,run_id,pod_namespace)

    if pod_service_account:
        annotations = pod_svc_account_annotations(pod_service_account,pod_namespace)
        if 'iam.gke.io/gcp-service-account' in annotations:
            gcp_service_account = annotations['iam.gke.io/gcp-service-account']
            if gcp_service_account:
                gcp_utils.remove_iam_policy_binding(pod_service_account, gcp_service_account, pod_namespace)
                annotate_pod_service_account(pod_service_account,None,pod_namespace)
            return True, f'GCP Service Account Workload Identity Removed'
        else:
            return False, f'GCP Service Account Workload Identity Could Not Be Removed. Possibly not a owner or no GSA mapped to Pod'
    return False, f'Cannot find Pod. Possibly not a owner'

def get_pod_service_account(domino_api_key,run_id,pod_namespace=DEFAULT_COMPUTE_NS):
    user_id = get_user_id(domino_api_key)
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    podLst:V1PodList = v1.list_namespaced_pod(pod_namespace)

    for p in podLst.items:
        pod:V1PodList = p
        m:V1ObjectMeta = pod.metadata
        metadata = m.to_dict()

        if metadata['labels'] and 'dominodatalab.com/execution-id' in metadata['labels'].keys():
            execution_id = metadata['labels']['dominodatalab.com/execution-id']
            if execution_id==run_id:
                pod_user_id = metadata['labels']['dominodatalab.com/starting-user-id']
                if pod_user_id==user_id:
                    return p.spec.service_account
    return None

def org_belongs_to_user(domino_api_key,org_name):
    orgs = get_user_orgs(domino_api_key)
    if org_name in orgs:
        return True
    return False

def is_user_admin(domino_api_key):
    domino_host = os.environ.get('DOMINO_USER_HOST','http://nucleus-frontend.domino-platform:80')
    resp = requests.get(f'{domino_host}/v4/auth/principal',
                 headers={'X-Domino-Api-Key':domino_api_key})
    if(resp.status_code==200):
        return "ActAsProjectAdmin" in resp.json()['allowedSystemOperations']

def get_user_id(domino_api_key):
    domino_host = os.environ.get('DOMINO_USER_HOST','http://nucleus-frontend.domino-platform:80')
    resp = requests.get(f'{domino_host}/v4/auth/principal',
                 headers={'X-Domino-Api-Key':domino_api_key})
    if(resp.status_code==200):
        return resp.json()['canonicalId']

def get_user_orgs(domino_api_key):
    domino_host = os.environ.get('DOMINO_USER_HOST','http://nucleus-frontend.domino-platform:80')

    url = f'{domino_host}/api/organizations/v1/organizations'

    resp = requests.get(url,
                 headers={'X-Domino-Api-Key':domino_api_key})

    if(resp.status_code==200):
        data =  resp.json()
        lst = []
        for o in data['orgs']:
            lst.append(o['name'])
    return lst

def get_user_default_org(domino_api_key,platform_ns:DEFAULT_PLATFORM_NS):
    orgs = get_user_orgs(domino_api_key)
    user_id = get_user_id(domino_api_key)
    try:
        config.load_incluster_config()
    except:
        print("Loading local k8s config")
        config.load_kube_config()
    v1 = client.CoreV1Api()
    user_current_org_mapping:V1ConfigMap = v1.read_namespaced_config_map(CONFIG_MAP_DOMINO_USER_CURRENT_ORG_MAPPING,
                                                                    platform_ns)

    if user_current_org_mapping.data and \
            user_id in user_current_org_mapping.data:
        default_org = user_current_org_mapping.data[user_id]
        if default_org in orgs:
            return default_org
    return None


if __name__ == "__main__":
    ns = 'gcp-aes4085-compute'
    pod_svc_account = 'sw-k8s-svc'
    pod_svc_account = 'run-638a213dde8619509891556e'
    gcp_service_account = 'sw-svc-gcp@domino-eng-platform-dev.iam.gserviceaccount.com'
    annotate_pod_service_account(pod_svc_account,gcp_service_account,ns)

    os.environ['DOMINO_USER_HOST'] = 'https://gcp-aes4085.eng-platform-dev.domino.tech/'
    API_KEY = '49fe95b5e93d150d51da51b33081965dd5e8951285d4174d68a6931ae4b191f8'
    print(get_user_orgs(API_KEY))

'''
#Steps
1. Verify user identify and if pod belongs to the user
2. Verify if user belongs to requested org
3. Get org to gcp service account mapping
4. Patch the service account of the pod
5. Update config map for the user default

Done
'''
