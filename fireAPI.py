#!/python3
from datetime import datetime
import requests
import hashlib
import logging


def toLinuxMS(dt):
    return round(dt.timestamp() * 1000)


## (extremely) basic api client to fire business api
class FireBusinessAPI(object):
    baseurl = "https://api.fire.com/business/v1"
    access_token = None

    def __init__(self, client_id, refresh_token, client_key):
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.client_key = client_key

    def sendRequest(self, path, method, data=None):
        headers = {'Content-Type': 'application/json'}
        if self.access_token is not None:
            self.checkExpiry()
            headers['Authorization'] = f"Bearer {self.access_token}"

        endpoint = self.baseurl + "/" + path
        if method == 'GET': 
            response = requests.get(endpoint, headers=headers, params=data)
        elif method == 'POST': 
            response = requests.post(endpoint, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(endpoint, headers=headers, json=data)

        response.raise_for_status()
        # some endpoints (looking at you, submitBatch) don't return body, just HTTP204
        try:
            return response.json()
        except Exception as e:
            return None

    def authenticate(self):
        nonce = toLinuxMS(datetime.utcnow())
        data = {
            'clientId': self.client_id,
            'refreshToken': self.refresh_token,
            'nonce': nonce,
            'grantType': 'AccessToken',
            'clientSecret': hashlib.sha256(
                (str(nonce) + self.client_key).encode('utf-8')
            ).hexdigest()
        }
        response = self.sendRequest('apps/accesstokens', 'POST', data)
        # docs say this is unix time, application actually returns ISO8601
        self.expiry = toLinuxMS(datetime.strptime(response['expiry'], "%Y-%m-%dT%H:%M:%S.%fZ"))
        self.businessId = response['businessId']
        self.permissions = response['permissions']  
        self.access_token = response['accessToken']
        try:
            self.applicationId = response['applicationId']
        except KeyError as e:
            pass

    def checkExpiry(self, seconds=1):
        timenow = toLinuxMS(datetime.utcnow())
        # give 1-second window
        if timenow >= self.expiry - (seconds * 1000):
            self.authenticate()

    def makeBatch(self, name):
        path = "batches"
        data = {
            'type': 'BANK_TRANSFER',
            'currency': 'EUR', 
            'batchName': name
        }
        response = self.sendRequest(path, 'POST', data)
        return response

    def addBatchPayment(self, batch_uuid, from_account, payee, amount, myref, yourref):
        path = f"batches/{batch_uuid}/banktransfers"
        data = {
            'icanFrom': from_account,
            'payeeId': payee,
            'amount': amount,
            'myRef': myref,
            'yourRef': yourref,
            'payeeType': 'PAYEE_ID'
        }
        response = self.sendRequest(path, 'POST', data)
        return response

    def submitBatch(self, batch_uuid):
        path = f"batches/{batch_uuid}"
        return self.sendRequest(path, 'PUT')

    def makePaymentRequest(self, 
        ican, ref, description, 
        curr='EUR', max_cust_payments=1, max_total_payments=None
    ):
        path = 'paymentrequests'
        data = {
            'icanTo': ican,
            'currency': 'EUR',
            'amount': 1,
            'myRef': ref,
            'description': description,
            'maxNumberCustomerPayments': max_cust_payments,
            'maxNumberPayments': max_total_payments,
        }
        response = self.sendRequest(path, 'POST', data)
        return response

    def getAccounts(self):
        return self.sendRequest('accounts', 'GET')

    def getFilteredTransactions(self, ref, ican, start_time=None, end_time=None, window=1000*60*15):
        if end_time is None:
            end_time = datetime.utcnow()
        end_time_ms = toLinuxMS(end_time)
        if start_time is not None:
            start_time_ms = toLinuxMS(start_time)
        else:
            start_time_ms = end_time_ms - window
        
        path = f"accounts/{ican}/transactions/filter"
        data = {
            'dateRangeFrom': start_time_ms,
            'dateRangeTo': end_time_ms, 
            'searchKeyword': ref
        }

        response = self.sendRequest(path, 'GET', data)
        return response


