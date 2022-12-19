import requests

import os
org = 'org4'
url = 'http://gcpworkloadidentity-svc.gcp-aes4085-platform/get_my_orgs'
headers = {           "X-Domino-Api-Key": os.environ['DOMINO_USER_API_KEY']
          }
print(headers)

resp = requests.get(url,headers=headers)
print(resp.status_code)
print(resp.content)