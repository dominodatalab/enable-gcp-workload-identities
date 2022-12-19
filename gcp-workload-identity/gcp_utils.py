from pprint import pprint

from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
import os
import google.auth.transport.requests
import google.auth

def get_service():
    if os.environ.get("GCP_KEYS_PATH"):
        key_file_path = os.environ.get("GCP_KEYS_PATH")
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
                key_file_path)
    else:
        auth_req = google.auth.transport.requests.Request()
        credentials, project = google.auth.default()
        credentials.refresh(auth_req)
    service = discovery.build('iam', 'v1', credentials=credentials)

    return service

def add_iam_policy_binding(gcp_service_account,domino_compute_namespace,domino_service_account):
    service = get_service()
    project_id =  os.environ.get('GCP_PROJECT_ID')
    project_location = os.environ.get('GCP_PROJECT_LOCATION',"")
    gke_id = os.environ.get('GCP_GKE_ID', "")
    providerId= f"https://container.googleapis.com/v1/projects/{project_id}/locations/{project_location}/clusters/{gke_id}"
    # REQUIRED: The resource for which the policy is being specified.
    # See the operation documentation for the appropriate value for this field.
    resource = f'projects/{project_id}/serviceAccounts/{gcp_service_account}'  # TODO: Update placeholder value.

    print(resource)
    print(providerId)
    set_iam_policy_request_body = {"policy":
                                       {"bindings": [
                                           {"members":
                                                ["serviceAccount:domino-eng-platform-dev.svc.id.goog[domino-platform/test]"],
                                                 "role": "roles/iam.workloadIdentityUser",
                                                 "condition": {
                                                    "title": f"single-cluster-acl-{domino_service_account}",
                                                    "description": "single-cluster-acl",
                                                    "expression": f"request.auth.claims.google.providerId=='{providerId}'",
                                                }
                                         }],
                                        "version": 3
                                       }

                                 }
    s = f"serviceAccount:{project_id}.svc.id.goog[{domino_compute_namespace}/{domino_service_account}]"
    set_iam_policy_request_body["policy"]["bindings"][0]["members"] = [s]
    request = service.projects().serviceAccounts().setIamPolicy(resource=resource, body=set_iam_policy_request_body)
    response = request.execute()
    return response

def remove_iam_policy_binding(domino_service_account,gcp_service_account,domino_compute_namespace):
    service = get_service()
    project_id =  os.environ.get('GCP_PROJECT_ID')


    # REQUIRED: The resource for which the policy is being specified.
    # See the operation documentation for the appropriate value for this field.
    resource = f'projects/{project_id}/serviceAccounts/{gcp_service_account}'  # TODO: Update placeholder value.
    print(resource)
    set_iam_policy_request_body = {"policy":
                                       {"bindings": [
                                           {"members":
                                                ["serviceAccount:domino-eng-platform-dev.svc.id.goog[domino-platform/test]"],
                                             "role": "roles/iam.workloadIdentityUser"
                                            }]}
                                 }
    member = f"serviceAccount:{project_id}.svc.id.goog[{domino_compute_namespace}/{domino_service_account}]"
    set_iam_policy_request_body["policy"]["bindings"][0]["members"] = []
    request = service.projects().serviceAccounts().getIamPolicy(resource=resource)
    j = request.execute()
    """Removes a  member from a role binding."""
    binding = next(b for b in j["bindings"] if b["role"].startswith('roles/iam.workloadIdentityUser'))
    if "members" in binding and member in binding["members"]:
        binding["members"].remove(member)
    request = service.projects().serviceAccounts().setIamPolicy(resource=resource, body= {"policy":j})
    request.execute()



if __name__ == "__main__":
    os.environ['GCP_KEYS_PATH'] = '/Users/sameerwadkar/Documents/GitHub2/enable-workload-identities-service/root/etc/keys/key.json'
    os.environ['GCP_PROJECT_ID'] = 'domino-eng-platform-dev'
    domino_compute_namespace = 'gcp-aes4085-compute'
    gcp_service_account = 'sw-aes-1@domino-eng-platform-dev.iam.gserviceaccount.com'
    domino_service_account = 'run-638f3e24de86195098915616'

    add_iam_policy_binding(gcp_service_account,domino_compute_namespace,domino_service_account)
    print(remove_iam_policy_binding(gcp_service_account, domino_compute_namespace, domino_service_account))

