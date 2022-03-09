import time
import json
import requests
from requests.auth import HTTPBasicAuth
from multiprocessing import Process
from datetime import datetime, timedelta
from NetAppApiConfig import Config
# Evolved 5G SDK
from evolved5g import swagger_client
from evolved5g.swagger_client import LoginApi, User, UEsApi
from evolved5g.swagger_client.models import Token
from evolved5g.sdk import LocationSubscriber
from evolved5g.swagger_client.rest import ApiException
from evolved5g.sdk import QosAwareness
from evolved5g.swagger_client import UsageThreshold
from evolved5g.swagger_client.api.qo_s_information_api import QoSInformationApi

class ApiError(Exception):

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
    
class MonSubError(Exception):

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class QoSSubError(Exception):

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ApiClient:

    def __init__(self, token=None, type=None, log='', config={}):

        self.config           = config
        self.log              = log
        self.token            = token
        self.type             = type
        self.ipv4             = {}
        self.monSubId         = {}
        self.qosSubId         = {}

        # Define static paths and urls
        self.CALLBACK_PATH   = '/api/v1/utils/monitoring/callback/'
        self.CALLBACK_MON    = self.CALLBACK_PATH + 'mon/'
        self.CALLBACK_QOS    = self.CALLBACK_PATH + 'qos/'
        self.NET_API_URL     = self.config.NET_API_PROT + '://' + self.config.NET_API_HOST + ':' + self.config.NET_API_PORT
        self.url_callback    = ''

        # SDK
        self.configuration = swagger_client.Configuration()
        self.configuration.host = self.NET_API_URL

        # Check if token needs to be obtained again
        if self.token == None:
            self.token, self.type = self.loginNefGetTokenSDK()


    def loginNefGetTokenSDK(self):

        api_client = swagger_client.ApiClient(configuration=self.configuration)
        api_client.select_header_content_type(["application/x-www-form-urlencoded"])
        api = LoginApi(api_client)
        token = None
        try:
            token = api.login_access_token_api_v1_login_access_token_post("", self.config.NET_API_USER, self.config.NET_API_PASS, "", "", "")
            self.log.debug(Config.LOG_NEF_SDK, 'Token: ' + str(token))
        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            raise ApiError("loginNefGetTokenSDK -> " + str(e))
            

        return token.access_token, token.token_type

    def validateTokenSDK(self):
        self.configuration.access_token = self.token
        api_client = swagger_client.ApiClient(configuration=self.configuration)
        api = LoginApi(api_client)
        response = api.test_token_api_v1_login_test_token_post_with_http_info()

        try:
            return response[0].is_active
        except:
            None

        # Generate new token again
        self.token, self.type = self.loginNefGetTokenSDK()
        if self.token != None: 
            return True
        
        return False

    def createMonitorEventSubsLocationSDK(self, externalId):

        # Callback Monitor Location URL
        url_callback = 'http://' + self.config.CALLBACK_HOST + ':' + self.config.CALLBACK_PORT + self.CALLBACK_MON + externalId
        self.log.debug(Config.LOG_NET_APP, 'Callback Monitor Location URL: ' + url_callback)

        # Expire time set, 24h from now
        expireTime = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%f')

        location_subscriber = LocationSubscriber(self.NET_API_URL, self.token)
        try:
            # Create subscription                                               
            result = location_subscriber.create_subscription(self.config.NET_APP_NAME,
                                                            externalId,
                                                            url_callback,
                                                            10000,
                                                            expireTime)                           
            
            self.ipv4[externalId] = result.ipv4_addr
            self.log.debug(Config.LOG_NEF_SDK, 'Retrieving IPv4 address: ' + self.ipv4[externalId])
            subs_id = result.link.split('/')[-1]
            self.log.debug(Config.LOG_NEF_SDK, 'Monitoring Location Event Subscription OK, ID: ' + subs_id)
            self.monSubId[externalId] = subs_id

        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            if e.status==409:
                raise MonSubError ("UE does not exist!")
            else:
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("createMonitorEventSubsLocationSDK -> " + str(e))

    def readActiveAndDeleteQosSubscriptionsSDK(self):

        qos_awereness = QosAwareness(self.NET_API_URL, self.token)

        try:
            all_subscriptions = qos_awereness.get_all_subscriptions(self.config.NET_APP_NAME)

            for subscription in all_subscriptions:
                id = subscription.link.split("/")[-1]
                self.log.debug(Config.LOG_NEF_SDK, "Deleting QoS subscription with ID: " + id)
                qos_awereness.delete_subscription(self.config.NET_APP_NAME, id)
                
            self.qosSubId = {}
        except ApiException as e:
            if e.status == 404:
                self.log.debug(Config.LOG_NEF_SDK, "No active subscriptions found")
            else: 
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("readActiveAndDeleteQosSubscriptionsSDK -> " + str(e))

    def createMonitorEventSubsQosSDK(self, externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold):

        qos_awereness = QosAwareness(self.NET_API_URL, self.token)

        equipment_network_identifier = self.ipv4[externalId]
        network_identifier = QosAwareness.NetworkIdentifier.IP_V4_ADDRESS

        usage_threshold = UsageThreshold(duration=None,  # not supported
                                        total_volume=0,  
                                        downlink_volume=0,  
                                        uplink_volume=0  
                                        )

        url_callback = 'http://' + self.config.CALLBACK_HOST + ':' + self.config.CALLBACK_PORT + self.CALLBACK_QOS + externalId

        try:
            self.log.debug(Config.LOG_NEF_SDK, 'Create guaranteed bit rate subscription')

            # Create subscription
            subscription = qos_awereness.create_guaranteed_bit_rate_subscription(self.config.NET_APP_NAME,
                equipment_network_identifier=equipment_network_identifier,
                network_identifier=network_identifier,
                notification_destination=url_callback,
                gbr_qos_reference=QosAwareness.GBRQosReference(qos_reference),
                usage_threshold=usage_threshold,
                qos_monitoring_parameter=QosAwareness.QosMonitoringParameter(qos_monitoring_parameter),
                threshold=qos_parameter_threshold,
                wait_time_between_reports=10)
        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            raise QoSSubError (str(e))
        # except Exception as e:
        #     self.log.error(self.configLOG_ERROR, str(e))
        #     raise ApiError("createMonitorEventSubsQosSDK -> " +  str(e))

        subscription_id = subscription.link.split("/")[-1]
        self.qosSubId[externalId] = subscription_id
        self.log.debug(Config.LOG_NEF_SDK, 'Monitoring QoS Event Subscription OK, ID: ' + subscription_id)

        # Request information about a subscription
        subscription_info = qos_awereness.get_subscription(self.config.NET_APP_NAME, subscription_id)
        self.log.debug(Config.LOG_NEF_SDK, 'Monitoring QoS Event Subscription INFO: ' + str(subscription_info))

    def readActiveAndDeleteLocSubscriptionsSDK(self):

        location_subscriber = LocationSubscriber(self.NET_API_URL, self.token)
        subs_list = []

        try:
            # Get all subscriptions
            all_subscriptions = location_subscriber.get_all_subscriptions(self.config.NET_APP_NAME, 0, 100)

            # Delete all subscriptions
            for subscription in all_subscriptions:
                subscription_id = subscription.link.split("/")[-1]
                subs_list.append(subscription_id)
                self.deleteActiveSubscriptionsSDK(subscription_id)

            self.monSubId = {}    
        except Exception as e:
            None

        return subs_list
        
    def deleteActiveMonSubscriptionSDK(self, external_id):

        location_subscriber = LocationSubscriber(self.NET_API_URL, self.token)
                    
        try:
            if external_id in self.monSubId:
                subscription = self.monSubId[external_id]

                if subscription:
                    # Delete subscription
                    location_subscriber.delete_subscription(self.config.NET_APP_NAME, subscription)
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Monitor Location subscription with ID: " + subscription)
                    del self.monSubId[external_id]
        except Exception as e:
            None

    def deleteActiveQosSubscriptionSDK(self, external_id):

        qos_awereness = QosAwareness(self.NET_API_URL, self.token)
        try:
            if external_id in self.qosSubId:
                subscription = self.qosSubId[external_id]
                if subscription:
                    # Delete subscription
                    qos_awereness.delete_subscription(self.config.NET_APP_NAME, subscription)
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting QoS subscription with ID: " + subscription)
                    del self.qosSubId[external_id]
        except Exception as e:
            None

    def eventMonitorSubClientLocation(self, externalId):

        # Delete active subscriptions
        self.readActiveAndDeleteLocSubscriptionsSDK()

        # Create monitoring event Location subscription
        self.createMonitorEventSubsLocationSDK(externalId)

    def eventMonitorSubClientQoS(self, externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold):

        # Delete active subscriptions
        self.readActiveAndDeleteQosSubscriptionsSDK()

        # Create monitoring event QoS subscription
        self.createMonitorEventSubsQosSDK(externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold)