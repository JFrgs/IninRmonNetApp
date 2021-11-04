import time
import json
import requests
from requests.auth import HTTPBasicAuth
from multiprocessing import Process
from datetime import datetime, timedelta
from NetAppApiConfig import Config

class ApiClient:

    def __init__(self, token=None, type=None, log='', config={}):

        self.config           = config
        self.log              = log

        self.ueipv4           = ''
        self.token            = token
        self.type             = type

        # Define static paths and urls
        self.CALLBACK_PATH   = '/api/v1/utils/monitoring/callback/'
        self.CALLBACK_URL    = 'http://' + self.config.CALLBACK_HOST + ':' + self.config.CALLBACK_PORT + self.CALLBACK_PATH
        self.NET_API_URL     = self.config.NET_API_PROT + '://' + self.config.NET_API_HOST + ':' + self.config.NET_API_PORT
        self.url_callback    = ''


        # Check if token needs to be obtained again
        if self.token == None:
            self.token, self.type = self.loginNefGetToken()
            self.log.debug(Config.LOG_5G_NEF, 'Token: ' + str(self.token))

    def loginNefGetToken(self):

        self.log.debug(Config.LOG_5G_NEF, 'Authentication pending')

        # Server path
        path='/api/v1/login/access-token'

        # Header set
        header = {
            'accept': 'application/json', 
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Body set
        body = {
            'grant_type': '', 
            'username': Config.NET_API_USER, 
            'password': Config.NET_API_PASS, 
            'scope': '', 
            'client_id': '', 
            'client_secret': ''
        }

        # URL set
        url = self.NET_API_URL + path

        # Get Authentication Token from 5G NEF API
        result = None, None
        try:
            response = requests.post(url, data=body, headers=header)
            if response.status_code == 200:
                result = response.json()['access_token'], response.json()['token_type']
                self.log.debug(Config.LOG_5G_NEF, 'Token successfully obtained!')
            else:
                self.log.debug(Config.LOG_5G_NEF, 'Token status code not OK: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'Token can not be not obtained!')

        return result

    def validateToken(self):

        #self.log.debug(Config.LOG_5G_NEF, 'Check if token is valid')

        # Server path
        path='/api/v1/login/test-token'

        # Header token set
        auth_token = self.type + ' ' + self.token

        # Header set
        header = {
            'accept': 'application/json', 
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization' : auth_token
        }

        # URL set
        url = self.NET_API_URL + path

        # Check validation token
        try:
            response = requests.post(url, headers=header)
            if response.status_code == 200:
                if response.json()['is_active']:
                    return True
                    #self.log.debug(Config.LOG_5G_NEF, 'Token is valid!')
                else:
                    self.log.debug(Config.LOG_5G_NEF, 'Token is not valid.')
            else:
                self.log.debug(Config.LOG_5G_NEF, 'Token is not valid: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'Token can not be validated.')


        # Generate new token again
        self.token, self.type = self.loginNefGetToken()
        if self.token != None: 
            return True

        return False  

    def getUeSupi(self, supi):

        # Check if token is valid
        if self.validateToken() == False:
            return None

        # Server path
        path='/api/v1/UEs/'

        # Header token set
        auth_token = self.type + ' ' + self.token

        # Header set
        header = {
            'accept': 'application/json', 
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization' : auth_token
        }

        # URL set
        url = self.NET_API_URL + path + supi

        # Get UE SUPI from 5G NEF API  
        result = None
        try:
            response = requests.get(url, headers=header)
            if response.status_code == 200:
                result = response.json()
                self.ueipv4 = result['ip_address_v4']
                self.log.debug(Config.LOG_5G_NEF, 'IPv4 UE: ' + self.ueipv4)
            else:
                self.log.debug(Config.LOG_5G_NEF, 'IPv4 UE status code not OK: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'SUPI be not obtained!')

        return result

    def prepareJsonBodyForMonitorSubscription(self, supi, ipv4):

        url_callback     = self.CALLBACK_URL + supi
        self.log.debug(Config.LOG_NET_APP, 'Callback URL: ' + url_callback)

        # Expire time set, 24h from now
        expireTime = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%f')

        # Body set
        body = {
            'externalId': '',
            'msisdn': supi,
            'ipv4Addr': ipv4,
            'ipv6Addr': '0:0:0:0:0:0:0:1',
            'notificationDestination': url_callback,
            'monitoringType': 'LOCATION_REPORTING',
            'maximumNumberOfReports': 100,
            'monitorExpireTime': expireTime
        }

        self.log.debug(Config.LOG_NET_APP, 'Monitoring request JSON: ' + str(body))

        return body

    def createMonitorEventSubs(self, supi, ueipv4):

        # Check if token is valid
        if self.validateToken() == False:
            return None

        # Server path
        path='/api/v1/3gpp-monitoring-event/v1/'+self.config.NET_APP_NAME+'/subscriptions'

        # Header token set
        auth_token = self.type + ' ' + self.token

        header = {
            'accept': 'application/json', 
            'Content-Type': 'application/json',
            'Authorization' : auth_token
        }

        # Prepare JSON body
        body = self.prepareJsonBodyForMonitorSubscription(supi, ueipv4)

        # URL set
        url = self.NET_API_URL + path

        try:
            response = requests.post(url, data=json.dumps(body),headers=header)
            if response.status_code == 201:
                self.log.debug(Config.LOG_5G_NEF, 'Create Monitor Event OK')
                self.log.debug(Config.LOG_5G_NEF, 'Response: ' + str(response.json()))
            else:
                self.log.debug(Config.LOG_5G_NEF, 'Create Monitor Event OK status code not OK: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'Create Monitor Event not OK!')
  
    def readActiveSubscriptions(self):

        # Check if token is valid
        if self.validateToken() == False:
            return None

        # Server path
        path='/api/v1/3gpp-monitoring-event/v1/'+self.config.NET_APP_NAME+'/subscriptions'

        # /api/v1/3gpp-as-session-with-qos/v1/{scsAsId}/subscriptions
        # Header token set
        auth_token = self.type + ' ' + self.token

        header = {
            'accept': 'application/json', 
            'Authorization' : auth_token
        }

        # URL set
        url = self.NET_API_URL + path

        # List of all active subscriptions
        subs_id = []

        try:
            response = requests.get(url, headers=header)
            if response.status_code == 200:
                self.log.debug(Config.LOG_5G_NEF, 'Read active subscriptions OK')
                self.log.debug(Config.LOG_5G_NEF, 'Number of all active subscriptions: ' + str(len(response.json())))
                for i in response.json():
                    subs_id.append(i['link'].split('/')[-1])
            else:
                self.log.debug(Config.LOG_5G_NEF, 'Read active subscriptions not OK: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'Read active subscriptions not OK!')

        return subs_id

    def deleteActiveSubscriptions(self, subscription):

        # Check if token is valid
        if self.validateToken() == False:
            return None

        # Server path
        path='/api/v1/3gpp-monitoring-event/v1/'+self.config.NET_APP_NAME+'/subscriptions'

        # Header token set
        auth_token = self.type + ' ' + self.token

        header = {
            'accept': 'application/json', 
            'Authorization' : auth_token
        }

        # URL set
        url = self.NET_API_URL + path + '/' + subscription
        try:
            response = requests.delete(url, headers=header)
            if response.status_code == 200:
                self.log.debug(Config.LOG_5G_NEF, 'Delete active subscription ' + subscription +  ' OK')
            else:
                self.log.debug(Config.LOG_5G_NEF, 'Delete active subscription not OK: ' + str(response.status_code))
        except:
            self.log.debug(Config.LOG_5G_NEF, 'Delete active subscription not OK!')

    def initClientSupi(self, supi):

        self.log.debug(Config.LOG_5G_NEF, 'Init client connection')
        # self.log.debug(supi)

        result = False

        # Test if UE exist and get initial UE values
        try:
            self.getUeSupi(supi)
            result = True
        except:
            self.log.debug(Config.LOG_5G_NEF, 'SUPI does not exist!')

        return result


    def eventMonitorSubClient(self, supi):

        # Create monitoring event subscription
        self.createMonitorEventSubs(supi, self.ueipv4)

    def setSliceSupi(self, net_slice, supi):

        result = False
        # Test if UE exist and get initial UE values
        try:
            self.log.debug(Config.LOG_5G_NEF, 'Slice set to: ' + net_slice + ', SUPI: ' + supi)
            result = True
        except:
            self.log.debug(Config.LOG_5G_NEF, 'SUPI does not exist!')

        return result