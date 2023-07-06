"""ZohoInventory target sink class, which handles writing streams."""

from target_hotglue.client import HotglueSink
import requests
import base64
import time
import json
from difflib import SequenceMatcher
from heapq import nlargest as _nlargest
from datetime import datetime


class ZohoInventorySink(HotglueSink):
    
    @property 
    def http_headers(self):
        
        expired = not self.access_token or (self.granted_on + self.expires_in < time.time())

        if expired:
            self.logger.info("Access token expired. POSTing new OAuth Token.")
            auth_uri = "https://accounts.zoho.com/oauth/v2/token"
            token_payload =  {
                "scope": "ZohoInventory.purchaseorders.CREATE,ZohoInventory.purchaseorders.UPDATE,ZohoInventory.contacts.READ,ZohoInventory.items.READ",
                "redirect_uri": self.config["redirect_uri"],
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "refresh_token": self.config["refresh_token"],
                "grant_type": "refresh_token",
            }

            resp = requests.post(auth_uri,data=token_payload)
            self.access_token = json.loads(resp.content)['access_token']
            self.expires_in = json.loads(resp.content)['expires_in']
            self.granted_on = time.time()


        result = {}
        result["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
       

        return result
    
    
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
        resp = self.request_api("GET",path,headers=headers,params=params)
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
            resp = self.request_api("GET",path,headers=headers,params=params)
            parsed_resp = json.loads(resp.content)
            records += parsed_resp[record_jsonpath]
            more_pages = parsed_resp['page_context']['has_more_page']
        
        return records


    def search_vendors(self,vendor_name):
        vendors = self.paginated_search("/vendors",vendor_name,"company_name.contains")
        vendor_names = [v['vendor_name'] for v in vendors]
        matches = list(self.get_close_matches(vendor_name,vendor_names,n=1,cutoff=0.8).keys())
        result = list(filter(lambda x: x['vendor_name'] == matches[0],vendors))
        return result



class PurchaseOrderSink(ZohoInventorySink):
    
    """ZohoInventory target sink class."""
    name = "Bills"

    def preprocess_record(self,record: dict,context: dict) -> dict:
        return record
    

    def process_record(self, record: dict, context: dict) -> None:
        if self.stream_name == "Bills":
            self.process_bills(record,context)
       
        
    def process_bills(self,record,context):
        """Process the record."""
        path = '/purchaseorders'
        vendor_id = record.get('vendorId')

        if type(record['lineItems']) == str:
            record['lineItems'] = json.loads(record['lineItems'])
    
        if 'vendorName' in record and not vendor_id:
            matches = self.search_vendors(record['vendorName'])
            if matches:
                vendor_id = matches[0]['contact_id']
            else: 
                raise Exception(f"No matches found for vendor {record['vendorName']}")
                
        elif 'vendorNum' in record:
            vendor_id = record.get('vendorNum')
        
        is_taxable = record.get("taxCode")
        line_items = [
            self.parse_line(line) for line in record['lineItems']
        ]

        request_data = {
            "vendor_id": vendor_id,
            "reference_number": record.get("id"),
            "purchaseorder_number": record.get('billNum'),
            "date": datetime.fromisoformat(record.get('createdAt')).strftime("%Y-%m-%d"),
            "currency_code": record.get("currency"),
            "line_items": line_items
        }

        headers = self.http_headers

        self.logger.info(f"Posting record to {path}")

        resp = self.request_api("POST",path,request_data=request_data,headers=headers)

    def parse_line(self,line):
        if not line.get("productId"):
            items = self.paginated_search("/items",line.get("productName"),'name.contains')
            names = [v['name'] for v in items]
            matches = list(self.get_close_matches(line.get("productName"),names,n=1,cutoff=0.8).keys())
            result = list(filter(lambda x: x['name'] == matches[0],items))
        
            line['productId'] = result[0]['item_id']

        
        
        return {   
                "name": line.get('productName'),
                "item_id": line.get("productId"),
                "quantity": line.get("quantity"),
                "unit_price": line.get("unitPrice"),
                "discount": line.get("discountAmount"),
                "tax_name": line.get("taxCode"),
                "description": line.get("description"),

        } 

    @property
    def base_url(self):
        return "https://inventory.zoho.com/api/v1"

        
        
