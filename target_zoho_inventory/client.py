from target_hotglue.client import HotglueSink
import json
from singer_sdk.plugin_base import PluginBase
from typing import Dict, List, Optional
import json
from difflib import SequenceMatcher
from heapq import nlargest as _nlargest
from target_zoho_inventory.auth import ZohoInventoryAuthenticator 
import ast
from urllib.parse import urlparse

class ZohoInventorySink(HotglueSink):
    def __init__(
        self,
        target: PluginBase,
        stream_name: str,
        schema: Dict,
        key_properties: Optional[List[str]],
    ) -> None:
        """Initialize target sink."""
        self._target = target
        super().__init__(target, stream_name, schema, key_properties)

    auth_state = {}

    @property
    def base_url(self):
        accounts_server = self.config.get("accounts-server")
        if accounts_server:
            region = accounts_server.split(".")[-1]
            return f"https://inventory.zoho.{region}/api/v1"
        return "https://inventory.zoho.com/api/v1"
    
    @property
    def authenticator(self):
        if self.config.get("auth_url"):
            url = self.config.get("auth_url")
        elif self.config.get("accounts-server"):
            url = f"{self.config.get('accounts-server')}/oauth/v2/token"
        else:
            url = "https://accounts.zoho.com/oauth/v2/token"
        #validate url
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            url = "https://accounts.zoho.com/oauth/v2/token"
        return ZohoInventoryAuthenticator(
            self._target, self.auth_state, url
        )
    
    @property
    def http_headers(self) -> dict:
        """Return the http headers needed."""
        headers = {}
        headers.update(self.authenticator.auth_headers or {})
        return headers
    
    def parse_objs(self, obj):
        parsed_obj = None
        try:
            parsed_obj = ast.literal_eval(obj)
        except:
            parsed_obj = json.loads(obj)
        finally:
            return parsed_obj

    def get_close_matches(self, word, possibilities, n=20, cutoff=0.7):
        if not n >  0:
            raise ValueError("n must be > 0: %r" % (n,))
        if not 0.0 <= cutoff <= 1.0:
            raise ValueError("cutoff must be in [0.0, 1.0]: %r" % (cutoff,))
        result = []
        s = SequenceMatcher()
        s.set_seq2(word)
        for x in possibilities:
            s.set_seq1(x)
            if s.real_quick_ratio() >= cutoff and \
            s.quick_ratio() >= cutoff and \
            s.ratio() >= cutoff:
                result.append((s.ratio(), x))
        result = _nlargest(n, result)

        return {v: k for (k, v) in result}
    

    def paginated_search(self,path,name,field):
        self.logger.info(f"Searching {path} for {name}")
        params = {
            field: name
        }
        record_jsonpath = path.split("/")[1]
        
        if record_jsonpath == 'vendors':
            record_jsonpath = 'contacts'
        
        headers = self.http_headers
        if self.config.get('organization_id'):
            params['organization_id'] = self.config.get('organization_id')
        resp = self.request_api("GET", path, params=params)
        parsed_resp = json.loads(resp.content)
        records = []
        records += parsed_resp[record_jsonpath]
        more_pages = parsed_resp['page_context']['has_more_page']
        while more_pages:
            self.logger.info(f"Found page(s) {parsed_resp['page_context']['page']}")
            params = {
                field:name,
                "page": parsed_resp['page_context']['page'] + 1
            }
            if self.config.get('organization_id'):
                params['organization_id'] = self.config.get('organization_id')
            resp = self.request_api("GET",path,headers=headers,params=params)
            parsed_resp = json.loads(resp.content)
            records += parsed_resp[record_jsonpath]
            more_pages = parsed_resp['page_context']['has_more_page']
        
        return records


    def search_vendors(self,vendor_name):
        result = []
        vendors = self.paginated_search("/vendors",vendor_name,"company_name.contains")
        vendor_names = [v['vendor_name'] for v in vendors]
        matches = list(self.get_close_matches(vendor_name,vendor_names,n=1,cutoff=0.8).keys())
        if matches:
            result = list(filter(lambda x: x['vendor_name'] == matches[0],vendors))
        return result
