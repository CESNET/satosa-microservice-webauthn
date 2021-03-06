import json
import logging
import random
import string
import requests
import hmac
from jwkest.jwk import rsa_load, RSAKey
from jwkest.jws import JWS

from satosa.internal import InternalData
from ..micro_services.base import ResponseMicroService
from ..response import Redirect
import time

logger = logging.getLogger(__name__)


class Webauthn(ResponseMicroService):

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redirect_url = config["redirect_url"]
        self.api_url = config["api_url"]
        self.exclude = config["exclude"]
        self.user_id = config["user_identificator"]
        self.conflict_compatibility = config["conflict_compatibility"]
        self.included_requesters = config["included_requesters"] or []
        self.excluded_requesters = config["excluded_requesters"] or []
        self.signing_key = RSAKey(key=rsa_load(config["private_key"]), use="sig", alg="RS256")
        self.endpoint = "/process"
        self.id_to_attr = config.get("id_to_attr", None)
        logger.info("Webauthn is active")

    def _handle_webauthn_response(self, context):
        saved_state = context.state[self.name]
        internal_response = InternalData.from_dict(saved_state)
        message = {"user_id": internal_response["attributes"][self.user_id][0], "nonce": internal_response['nonce'],
                   "time": str(int(time.time()))}
        message_json = json.dumps(message)
        jws = JWS(message_json, alg=self.signing_key.alg).sign_compact([self.signing_key])
        request = self.api_url + "/" + jws
        response = requests.get(request)
        response_dict = json.loads(response.text)
        if response_dict["result"] != "okay" or not hmac.compare_digest(response_dict["nonce"], internal_response["nonce"]):
            raise Exception("Authentication was unsuccessful.")
        if "authn_context_class_ref" in context.state:
            internal_response["auth_info"]["auth_class_ref"] = context.state["authn_context_class_ref"]
        return super().process(context, internal_response)

    def process(self, context, internal_response):
        client_mfa_requested = False
        client_sfa_requested = False
        if "authn_context_class_ref" in context.state and "mfa" in context.state["authn_context_class_ref"]:
            client_mfa_requested = True
        if "authn_context_class_ref" in context.state and (
                "sfa" in context.state["authn_context_class_ref"] or
                "PasswordProtectedTransport" in context.state["authn_context_class_ref"]):
            client_sfa_requested = True

        config_mfa_requested = True
        internal_dict = internal_response.to_dict()
        if self.exclude and internal_dict.get("requester") in self.excluded_requesters:
            config_mfa_requested = False
        if not self.exclude and not (internal_dict.get("requester") in self.included_requesters):
            config_mfa_requested = False

        if not client_mfa_requested and not config_mfa_requested:
            return super().process(context, internal_response)

        if client_sfa_requested and config_mfa_requested:
            context.state["conflict"] = True
        else:
            context.state["conflict"] = False

        if not self.conflict_compatibility and context.state["conflict"]:
            raise Exception("CONFLICT - SP and the Request are in a conflict - authentication could not take place.")

        user_id = internal_response["attributes"][self.user_id][0]
        letters = string.ascii_lowercase
        actual_time = str(int(time.time()))
        rand = random.SystemRandom()
        random_string = actual_time + ''.join(rand.choice(letters) for i in range(54))
        internal_response['nonce'] = random_string
        context.state[self.name] = internal_response.to_dict()
        message = {"user_id": user_id, "nonce": random_string, "time": actual_time}
        message_json = json.dumps(message)
        jws = JWS(message_json, alg=self.signing_key.alg).sign_compact([self.signing_key])

        return Redirect("%s/%s" % (self.redirect_url + "/" + jws, ""))

    def register_endpoints(self):
        return [("^webauthn%s$" % self.endpoint, self._handle_webauthn_response)]
