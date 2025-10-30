import requests
from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC
import veracode_api_signing.credentials as vcreds

headers = {"User-Agent": "Python HMAC"}
api_base = "https://api.veracode.com/"

"""
Setup environment variables ID, Key
"""
def envSetup(id=None, key=None, profile=None, auth_file=None):
    

    api_key_id = id
    api_key_secret = key
    vcreds.PROFILE_DEFAULT=profile if profile else 'default'

    if not (id or key):
        api_key_id, api_key_secret = vcreds.get_credentials()
 
    return api_key_id, api_key_secret