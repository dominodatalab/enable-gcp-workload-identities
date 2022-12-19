from flask import Flask, request, Response  # type: ignore
import logging
import os
import utils


DEFAULT_PLATFORM_NS = 'domino-platform'
DEFAULT_COMPUTE_NS = 'domino-compute'


logger = logging.getLogger("gcpworkloadidentity")
app = Flask(__name__)

@app.route("/map_org_to_gcp_sa", methods=["POST"])
def map_org_to_gcp_sa() -> object:
    platform_ns = os.environ.get('DEFAULT_PLATFORM_NS',DEFAULT_PLATFORM_NS)

    domino_api_key = request.headers["X-Domino-Api-Key"]
    is_caller_admin = utils.is_user_admin(domino_api_key)
    payload = request.json

    if not is_caller_admin:
        return Response(
            str('Not Authorized. Only a Domino Admin can map orgs to GCP SAs'),
            403)
    if not ('domino_org' in payload and 'gcp_sa' in payload):
        return Response(
            str('Pay load must contain a domino org and a svc_account'),
            404)
    else:
        domino_org = payload['domino_org']
        gcp_sa = payload['gcp_sa']
        if not domino_org or not gcp_sa:
            return Response(
                str('Pay load must contain a non-empty domino org and a not-empty svc_account'),
                404)
        old_gcp_sa, new_gcp_sa = utils.update_orgs_gcp_service_accounts_mapping(domino_org,gcp_sa,platform_ns)
        return Response(
            str(f'Domino Org {domino_org} mapping updated from GCP SA {old_gcp_sa} to {new_gcp_sa}'),
            200)
    '''
    payload = request.json
    run_id = payload['run_id']
    org = None
    if 'domino_org' in payload:
        org = payload['domino_org']
    if not org:
        org = utils.get_user_default_org(domino_api_key,platform_ns)
    logger.debug(f'Run Id {run_id}')
    logger.debug(f'Org Id {org}')

    status, message = utils.apply_service_account(domino_api_key,run_id,org,compute_ns,platform_ns)
    if status:
        return Response(
            str(message),
            200)
    else:
        return Response(
            str(message),
            404)
    '''

@app.route("/assume_service_account", methods=["POST"])
def apply_service_account() -> object:
    platform_ns = os.environ.get('DEFAULT_PLATFORM_NS',DEFAULT_PLATFORM_NS)
    compute_ns = os.environ.get('DEFAULT_COMPUTE_NS', DEFAULT_COMPUTE_NS)
    domino_api_key = request.headers["X-Domino-Api-Key"]
    payload = request.json
    run_id = payload['run_id']
    org = None
    if 'domino_org' in payload:
        org = payload['domino_org']
    if not org:
        org = utils.get_user_default_org(domino_api_key,platform_ns)
    logger.debug(f'Run Id {run_id}')
    logger.debug(f'Org Id {org}')
    #First remove existing service account
    status, message = utils.remove_service_account(domino_api_key, run_id, compute_ns)

    status, message = utils.apply_service_account(domino_api_key,run_id,org,compute_ns,platform_ns)
    if status:
        return Response(
            str(message),
            200)
    else:
        return Response(
            str(message),
            404)

@app.route("/reset_service_account", methods=["DELETE"])
def remove_service_account() -> object:
    compute_ns = os.environ.get('DEFAULT_COMPUTE_NS', DEFAULT_COMPUTE_NS)
    domino_api_key = request.headers["X-Domino-Api-Key"]
    payload = request.json

    status, message = utils.remove_service_account(domino_api_key,payload['run_id'],compute_ns)
    if status:
        return Response(
            str(message),
            200)
    else:
        return Response(
            str(message),
            404)

@app.route("/get_my_orgs", methods=["GET"])
def get_my_orgs() -> object:
    platform_ns = os.environ.get('DEFAULT_PLATFORM_NS', DEFAULT_PLATFORM_NS)
    domino_api_key = request.headers["X-Domino-Api-Key"]
    user_orgs = utils.get_user_orgs(domino_api_key)

    orgs_to_service_accounts_map = utils.get_orgs_gcp_service_accounts_mapping(platform_ns)
    my_orgs = {}
    for org in user_orgs:
        my_orgs[org] = orgs_to_service_accounts_map[org]
    return my_orgs


@app.route("/healthz")
def alive():
    return "{'status': 'Healthy'}"


if __name__ == "__main__":
    lvl: str = logging.getLevelName(os.environ.get("LOG_LEVEL", "ERROR"))
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    debug: bool = os.environ.get("FLASK_ENV") == "development"
    ssl_off = os.environ.get('SSL_OFF',"true")=="true"
    port = 6000
    if ssl_off:
        print(f'Running only http on port{port}')
        app.run(
            host=os.environ.get("FLASK_HOST", "0.0.0.0"),
            port=6000,
            debug=debug,
        )
    else:
        print(f'Running on port{port}')
        app.run(
            host=os.environ.get("FLASK_HOST", "0.0.0.0"),
            port=6000,
            debug=debug,
            ssl_context=("/ssl/tls.crt", "/ssl/tls.key"),
        )
