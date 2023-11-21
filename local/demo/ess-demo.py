#  Copyright (c) 2021,2022,2023
#        2022: ZF Friedrichshafen AG
#        2022: ISTOS GmbH
#        2022,2023: Bayerische Motoren Werke Aktiengesellschaft (BMW AG)
#        2022,2023: BOSCH AG
#  Copyright (c) 2021,2022,2023 Contributors to the Eclipse Foundation
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  This program and the accompanying materials are made available under the
#  terms of the Apache License, Version 2.0 which is available at
#  https://www.apache.org/licenses/LICENSE-2.0.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#
#  SPDX-License-Identifier: Apache-2.0
import argparse
import json
import logging
import time
from datetime import datetime
from types import SimpleNamespace

import jwt
import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests.adapters import HTTPAdapter, Retry
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session


def get_semantic_ids_from_twin(digital_twin_):
    semantic_ids_ = []
    for submodel_descriptor in digital_twin_.submodelDescriptors:
        keys = submodel_descriptor.semanticId.keys
        for key in keys:
            semantic_ids_.append(key.value)
    return semantic_ids_


def get_bpn_from_twin(digital_twin_):
    bpn_ = None
    for specific_asset_id in digital_twin_.specificAssetIds:
        if "manufacturerId" == specific_asset_id.name:
            bpn_ = specific_asset_id.value
    return bpn_


def fetch_all_registry_data(registry_url_, bpn_):
    twins_ = []
    cursor = None
    while True:
        params = {'cursor': cursor} if cursor else None
        registry_response = fetch_registry_data(registry_url_, bpn_, params)

        if not registry_response:
            logging.info(f"No registry response: '{registry_response}'")
            break

        result = registry_response.result
        logging.info(f"Adding {len(result)} twins to result list.")
        twins_.extend(result)

        if hasattr(registry_response.paging_metadata, 'cursor'):
            cursor = registry_response.paging_metadata.cursor
            logging.info(f"Setting cursor: '{cursor}'")
        else:
            logging.info("No cursor found.")
            break
    logging.info(f"Returning {len(twins_)} twins.")
    return twins_


def fetch_registry_data(registry_url_, bpn_, params_=None):
    headers_ = {"Edc-Bpn": bpn_}
    response_ = session.get(registry_url_, headers=headers_, params=params_)
    if response_.status_code == 200:
        registry_response = json.loads(response_.text, object_hook=lambda d: SimpleNamespace(**d))
        return registry_response
    else:
        logging.error(f"Failed to fetch registry data. Status code: {response_.status_code}")
        return None


def filter_for_as_planned_and_bpn(search_bpn_):
    filtered_twins_ = []
    for twin in digital_twins:
        semantic_ids = get_semantic_ids_from_twin(twin)
        if any("AsPlanned" in x for x in semantic_ids):
            global_asset_id = twin.globalAssetId
            bpn = get_bpn_from_twin(twin)
            if bpn in search_bpn_:
                logging.info(global_asset_id)
                logging.info(bpn)
                x = {
                    "globalAssetId": global_asset_id,
                    "bpn": bpn
                }
                filtered_twins_.append(x)
    return filtered_twins_


def poll_batch_job(batch_url, token_):
    header_ = create_header_with_token(token_)
    while True:
        try:
            response_ = session.get(batch_url, headers=header_)
            response_json = response_.json()
            print_order(response_json)

            state = response_json.get("state")
            if state in ("COMPLETED", "ERROR", "CANCELED"):
                logging.info(f"ESS Batch Investigation completed in state '{state}'")
                return response_json

            time.sleep(5)
        except requests.exceptions.RequestException as e:
            logging.error(f"Error: {e}")
            break


def create_header_with_token(token_):
    header_ = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_or_refresh_oauth_token(token_url, client_id, client_secret, token_)}"
    }
    return header_


def print_order(response_json):
    fields_to_print = ["orderId", "state", "batches"]
    fields_to_print_nested = ["batchId", "batchUrl", "batchProcessingState"]
    selected_fields = {key: response_json[key] for key in fields_to_print if key in response_json}
    if "batches" in response_json:
        selected_fields["batches"] = [
            {nested_key: item[nested_key] for nested_key in fields_to_print_nested if nested_key in item}
            for item in response_json["batches"]
        ]
    # Pretty print the selected fields
    pretty_selected_fields = json.dumps(selected_fields, indent=4)
    logging.info("Polling ESS Batch. Status: " + pretty_selected_fields)


def get_oauth_token(token_url_, client_id_, client_secret_):
    client = BackendApplicationClient(client_id=client_id_)
    oauth_ = OAuth2Session(client=client)
    token_ = oauth_.fetch_token(token_url=token_url_, auth=HTTPBasicAuth(client_id_, client_secret_))["access_token"]
    return token_


def get_or_refresh_oauth_token(token_url_, client_id_, client_secret_, token_: None):
    if token_ is None:
        return get_oauth_token(token_url_, client_id_, client_secret_)
    else:
        decoded_token = jwt.decode(token_, options={"verify_signature": False})
        exp_timestamp = datetime.fromtimestamp(decoded_token["exp"])
        current_timestamp = datetime.now()
        if exp_timestamp < current_timestamp:
            logging.info("Token expired. Requesting new.")
            return get_oauth_token(token_url_, client_id_, client_secret_)
        else:
            return token_


class ESSException(Exception):
    def __init__(self, *args, **kwargs):  # real signature unknown
        pass

    @staticmethod  # known case of __new__
    def __new__(*args, **kwargs):
        """ Create and return a new object.  See help(type) for accurate signature. """
        pass


def start_ess_investigation(irs_ess_url_, incident_bpns_, filtered_twins_, token_):
    payload_ = {
        "batchSize": 10,
        "batchStrategy": "PRESERVE_BATCH_JOB_ORDER",
        "incidentBPNSs": incident_bpns_,
        "keys": filtered_twins_
    }
    headers_ = create_header_with_token(token_)
    logging.info(f"Starting ESS batch investigation with \n{json.dumps(payload_, indent=4)}")
    response_ = session.post(url=irs_ess_url_, json=payload_, headers=headers_)

    if response_.status_code != 201:
        logging.error(f"Failed to start ESS Batch Investigation. Status code: {response_.status_code}")
        logging.info(response_.text)
        raise ESSException("Failed to start ESS Batch Investigation")
    else:
        batch_id_ = response_.json().get("id")
        logging.info(f"Started ESS Batch Investigation with id {batch_id_}")
        return batch_id_


def get_jobs_for_batch(url_, token_):
    headers_ = create_header_with_token(token_)
    response_ = session.get(url_, headers=headers_)
    return response_.json().get("jobs")


def get_job_for_id(url_, token_):
    headers_ = create_header_with_token(token_)
    response_ = session.get(url_, headers=headers_)

    return response_.json()


def prepare_arguments():
    parser = argparse.ArgumentParser(description="Script to demonstrate the ESS Batch Investigation flow.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--aas", type=str, help="AAS registry URL", required=True)
    parser.add_argument("--ownBPN", type=str, help="BPN of the requesting Company", required=True)
    parser.add_argument("--searchBPN", type=str, help="BPN of the Company to search for", required=True)
    parser.add_argument("--incidentBPNS", type=str, nargs="*",
                        help="List of BPNS of the Companies where the incidents occurred", required=True)
    parser.add_argument("--irs", type=str, help="IRS base URL", required=True)
    parser.add_argument("--tokenurl", type=str, help="OAuth2 token URL", required=True)
    parser.add_argument("--clientid", type=str, help="Client ID", required=True)
    parser.add_argument("--clientsecret", type=str, help="Client Secret", required=True)
    parser.add_argument("--debug", help="debug logging", action='store_true', required=False)
    args = parser.parse_args()
    return vars(args)

# Demo Cases:
#  Case 1 (incident and no issues in tree):
#  searchBPN: BPNL00ARBITRARY4
#  incidentBPNS: BPNS00ARBITRARY6

#  Case 2 (no incident and no issues in tree):
#  searchBPN: BPNL00ARBITRARY4
#  incidentBPNS: BPNS00ARBITRARY8

#  Case 3 (incident and not resolvable path in tree):
#  searchBPN: BPNL00ARBITRARY8
#  incidentBPNS: BPNS0ARBITRARY10

#  Case 4 (no incident and not resolvable path in tree):
#  searchBPN: BPNL00ARBITRARY8
#  incidentBPNS: BPNS0ARBITRARY12


if __name__ == "__main__":
    config = prepare_arguments()
    registry_url = config.get("aas")
    own_BPN = config.get("ownBPN")
    search_BPN = config.get("searchBPN")
    incident_BPNSs = config.get("incidentBPNS")
    irs_base_url = config.get("irs")
    token_url = config.get("tokenurl")
    client_id = config.get("clientid")
    client_secret = config.get("clientsecret")
    is_debug = config.get("debug")

    irs_ess_url = f"{irs_base_url}/ess/bpn/investigations"
    irs_ess_batch_url = f"{irs_base_url}/irs/ess/orders"
    irs_batch_url = f"{irs_base_url}/irs/orders"

    logging_level = logging.INFO
    if is_debug:
        logging_level = logging.DEBUG

    logging.basicConfig(level=logging_level, format='%(asctime)s [%(levelname)-5.5s] %(message)s')
    retries = Retry(total=3,
                    backoff_factor=0.1)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retries))

    # TODO eval, if it makes sense to filter via lookup/shells endpoint or filter by getting the entire list of twins

    # Fetch all digital Twins from the DTR
    digital_twins = fetch_all_registry_data(registry_url, own_BPN)

    # Filter for bomLifecycle "asPlanned" and the provided BPN
    filtered_twins = filter_for_as_planned_and_bpn(search_BPN)
    logging.info(f"Found {len(filtered_twins)} twin(s) after filtering.")
    logging.info(json.dumps(filtered_twins, indent=4))

    # Authenticate
    token = get_oauth_token(token_url, client_id, client_secret)

    # Start IRS batch job
    batch_id = start_ess_investigation(irs_ess_batch_url, incident_BPNSs, filtered_twins, token)

    # Poll batch until it is completed
    completed_batch = poll_batch_job(f"{irs_batch_url}/{batch_id}", token)
    for batch in completed_batch.get("batches"):
        url = batch.get("batchUrl")
        jobs = get_jobs_for_batch(url, token)
        for job in jobs:
            job_id = job.get("id")

            job = get_job_for_id(f"{irs_ess_url}/{job_id}", token)

            submodels = job.get("submodels")
            for submodel in submodels:
                submodel_payload = submodel.get('payload')
                impacted = submodel_payload.get("supplyChainImpacted")
                impacted_suppliers = submodel_payload.get("impactedSuppliersOnFirstTier")
                logging.info(f"Investigation result for Job {job_id} resulted in {impacted}.")
                if impacted_suppliers:
                    logging.info(f"Impacted Suppliers on first level: {impacted_suppliers}.")
