import requests
import os

org = 'org1'
url = 'http://gcpworkloadidentity-svc.gcp-aes4085-platform/assume_service_account'
headers = {"Content-Type" : "application/json",
           "X-Domino-Api-Key": os.environ['DOMINO_USER_API_KEY']
          }
print(headers)
data = {
    "domino_org" : org,
    "run_id" : os.environ['DOMINO_RUN_ID']
}

resp = requests.post(url,headers=headers,json=data)
print(resp.status_code)
print(resp.content)