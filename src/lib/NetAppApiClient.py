import time
import json
import requests
import random
import string
from requests.auth import HTTPBasicAuth
from multiprocessing import Process
from datetime import datetime, timedelta
from NetAppApiConfig import Config
# Evolved 5G SDK
from evolved5g import swagger_client
from evolved5g.swagger_client import LoginApi, User, UEsApi
from evolved5g.swagger_client.models import Token
from evolved5g.swagger_client.rest import ApiException
from evolved5g.sdk import LocationSubscriber
from evolved5g.sdk import QosAwareness
from evolved5g.sdk import ConnectionMonitor
from evolved5g.sdk import ServiceDiscoverer
from evolved5g.sdk import CAPIFInvokerConnector
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

        self.config            = config
        self.log               = log
        self.token             = token
        self.type              = type
        self.ipv4              = {}
        self.monLocSubId       = {}
        self.monConnLossSubId  = {}
        self.monConnReachSubId = {}
        self.qosSubId          = {}

        # Define static paths and urls
        self.CALLBACK_PATH   = '/api/v1/utils/monitoring/callback/'
        self.CALLBACK_LOC    = self.CALLBACK_PATH + 'loc/'
        self.CALLBACK_CON    = self.CALLBACK_PATH + 'con/'
        self.CALLBACK_QOS    = self.CALLBACK_PATH + 'qos/'
        self.NET_API_URL     = self.config.NET_API_PROT + '://' + self.config.NET_API_ADDRESS
        self.url_callback    = ''

        # CAPIF CONFIG JSON
        try:
            self.capif_path_certificates = self.config.CAPIF_PATH
            self.capif_host = self.config.CAPIF_HOSTNAME
            self.capif_https_port = self.config.CAPIF_PORT_HTTPS
        except Exception as e:
            raise ApiError("capif config -> " + str(e)) 

        # CAPIF CONNECTOR 
        self.capif_connector()

        # CAPIF DISCOVERY 
        self.capif_discovery = self.capif_service_discovery()

        # SDK
        self.configuration = swagger_client.Configuration()
        self.configuration.host = self.NET_API_URL

        # Check if token needs to be obtained again
        if self.token == None:
            self.token, self.type = self.register_netapp_to_nef()

    def register_netapp_to_nef(self):
        api_client = swagger_client.ApiClient(configuration=self.configuration)
        api_client.select_header_content_type(["application/x-www-form-urlencoded"])
        api = LoginApi(api_client)
        token = None
        try:
            token = api.login_access_token_api_v1_login_access_token_post("", self.config.NET_API_USER, self.config.NET_API_PASS, "", "", "")
            self.log.debug(Config.LOG_NEF_SDK, 'Token: ' + str(token))
        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))     

        return token.access_token, token.token_type

    def parse_capif_config_json(self):
        
        capif_json = {}
        try:
            with open(self.config.CAPIF_JSON_PATH, 'r') as config_file:
                capif_json = json.load(config_file)
                self.log.debug(Config.LOG_NET_APP, 'Capif config: ' + str(capif_json))
        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))

        return capif_json

    def capif_connector(self):

        try:
            capif_connector = CAPIFInvokerConnector(
                                                folder_to_store_certificates=self.config.CAPIF_PATH,
                                                capif_host=self.config.CAPIF_HOSTNAME,
                                                capif_http_port=int(self.config.CAPIF_PORT_HTTP),
                                                capif_https_port=int(self.config.CAPIF_PORT_HTTPS),
                                                capif_netapp_username=self.generate_user_pass(),
                                                capif_netapp_password=self.generate_user_pass(),
                                                capif_callback_url="http://localhost:5000",
                                                description= "test_app_description",
                                                csr_common_name="test_app_common_name",
                                                csr_organizational_unit="test_app_ou",
                                                csr_organization="test_app_o",
                                                crs_locality="Ljubljana",
                                                csr_state_or_province_name="Ljubljana",
                                                csr_country_name="SI",
                                                csr_email_address="test@example.com",
                                                )

            connection = capif_connector.register_and_onboard_netapp()
            self.log.debug(Config.LOG_NET_APP, 'CAPIF connection OK!')
        except Exception as e:
            self.log.error(Config.LOG_ERROR, 'CAPIF connector error: ' + str(e))
            raise ApiError("CAPIF connector error -> " + str(e)) 

    def generate_user_pass(self):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(10))

    def capif_service_discovery(self):

        endpoints = None
        service_discoverer = ServiceDiscoverer(folder_path_for_certificates_and_api_key=self.capif_path_certificates,
                                                capif_host=self.capif_host,
                                                capif_https_port=self.capif_https_port)
        try:
            endpoints = service_discoverer.discover_service_apis()
            self.log.debug(Config.LOG_NET_APP, 'CAPIF endpoints: ' + str(endpoints))
        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            raise ApiError("CAPIF service_discoverer error -> " + str(e)) 

        return endpoints

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
        self.token, self.type = self.register_netapp_to_nef()
        if self.token != None: 
            return True
        
        return False

    def createMonitorEventSubsConnectionLossSDK(self, externalId):

        # Callback Monitor Location URL
        url_callback = 'http://' + self.config.CALLBACK_ADDRESS + self.CALLBACK_CON + externalId
        self.log.debug(Config.LOG_NET_APP, 'Callback Monitor Connection URL: ' + url_callback)

        # Expire time set, 24h from now
        expireTime = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%f')

        connection_subscriber = ConnectionMonitor(nef_url=self.NET_API_URL, 
                                                nef_bearer_access_token=self.token,
                                                folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                                capif_host=self.capif_host,
                                                capif_https_port=self.capif_https_port)


        try:
            # Create subscription   
            result = connection_subscriber.create_subscription(netapp_id=self.config.NET_APP_NAME,
                            external_id=externalId,
                            notification_destination=url_callback,monitoring_type=ConnectionMonitor.MonitoringType.INFORM_WHEN_NOT_CONNECTED,
                            wait_time_before_sending_notification_in_seconds=1,
                            maximum_number_of_reports=1000,
                            monitor_expire_time=expireTime)     
            
            self.ipv4[externalId] = result.ipv4_addr
            self.log.debug(Config.LOG_NEF_SDK, 'Retrieving IPv4 address: ' + self.ipv4[externalId])
            subs_id = result.link.split('/')[-1]
            self.log.debug(Config.LOG_NEF_SDK, 'Monitoring Connection Event Subscription OK, ID: ' + subs_id)
            self.monConnLossSubId[externalId] = subs_id

        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            if e.status==409:
                raise MonSubError ("UE does not exist!")
            else:
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("createMonitorEventSubsConnectionLossSDK -> " + str(e))

    def createMonitorEventSubsConnectionReachabilitySDK(self, externalId):

        # Callback Monitor Location URL
        url_callback = 'http://' + self.config.CALLBACK_ADDRESS + self.CALLBACK_CON + externalId
        self.log.debug(Config.LOG_NET_APP, 'Callback Monitor Connection URL: ' + url_callback)

        # Expire time set, 24h from now
        expireTime = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%f')

        connection_subscriber = ConnectionMonitor(nef_url=self.NET_API_URL, 
                                                nef_bearer_access_token=self.token,
                                                folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                                capif_host=self.capif_host,
                                                capif_https_port=self.capif_https_port)

        try:
            # Create subscription   
            result = connection_subscriber.create_subscription(netapp_id=self.config.NET_APP_NAME,
                            external_id=externalId,
                            notification_destination=url_callback,monitoring_type=ConnectionMonitor.MonitoringType.INFORM_WHEN_CONNECTED,
                            wait_time_before_sending_notification_in_seconds=1,
                            maximum_number_of_reports=1000,
                            monitor_expire_time=expireTime)     
            
            self.ipv4[externalId] = result.ipv4_addr
            self.log.debug(Config.LOG_NEF_SDK, 'Retrieving IPv4 address: ' + self.ipv4[externalId])
            subs_id = result.link.split('/')[-1]
            self.log.debug(Config.LOG_NEF_SDK, 'Monitoring Connection Event Subscription OK, ID: ' + subs_id)
            self.monConnReachSubId[externalId] = subs_id

        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            if e.status==409:
                raise MonSubError ("UE does not exist!")
            else:
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("createMonitorEventSubsConnectionReachabilitySDK -> " + str(e))

    def monitor_subscription(self, externalId):
        # createMonitorEventSubsLocationSDK

        # Callback Monitor Location URL
        url_callback = 'http://' + self.config.CALLBACK_ADDRESS + self.CALLBACK_LOC + externalId
        self.log.debug(Config.LOG_NET_APP, 'Callback Monitor Location URL: ' + url_callback)

        # Expire time set, 24h from now
        expireTime = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%f')

        location_subscriber = LocationSubscriber(nef_url=self.NET_API_URL, 
                                                nef_bearer_access_token=self.token,
                                                folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                                capif_host=self.capif_host,
                                                capif_https_port=self.capif_https_port)
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
            self.monLocSubId[externalId] = subs_id

        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            if e.status==409:
                raise MonSubError ("UE does not exist!")
            else:
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("monitor_subscription -> " + str(e))

    def readActiveAndDeleteQosSubscriptionsSDK(self):

        qos_awereness = QosAwareness(nef_url=self.NET_API_URL, 
                                    nef_bearer_access_token=self.token,
                                    folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                    capif_host=self.capif_host,
                                    capif_https_port=self.capif_https_port)

        try:
            all_subscriptions = qos_awereness.get_all_subscriptions(self.config.NET_APP_NAME)

            for subscription in all_subscriptions:
                id = subscription.link.split("/")[-1]
                self.log.debug(Config.LOG_NEF_SDK, "Deleting QoS subscription with ID: " + id)
                qos_awereness.delete_subscription(self.config.NET_APP_NAME, id)
                
            self.qosSubId = {}
        except ApiException as e:
            if e.status == 404:
                self.log.debug(Config.LOG_NEF_SDK, "No active QoS subscriptions found")
            else: 
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("readActiveAndDeleteQosSubscriptionsSDK -> " + str(e))

    def sessionqos_subscription(self, externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold, qos_reporting_mode):
        # createMonitorEventSubsQosSDK

        qos_awereness = QosAwareness(nef_url=self.NET_API_URL, 
                                    nef_bearer_access_token=self.token,
                                    folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                    capif_host=self.capif_host,
                                    capif_https_port=self.capif_https_port)

        equipment_network_identifier = self.ipv4[externalId]
        network_identifier = QosAwareness.NetworkIdentifier.IP_V4_ADDRESS

        usage_threshold = UsageThreshold(duration=None,  # not supported
                                        total_volume=0,  
                                        downlink_volume=0,  
                                        uplink_volume=0  
                                        )

        if qos_reporting_mode == 'EVENT_TRIGGERED':
            reporting_mode = QosAwareness.EventTriggeredReportingConfiguration(wait_time_in_seconds=10)
        else:
            reporting_mode = QosAwareness.PeriodicReportConfiguration(repetition_period_in_seconds=10)


        url_callback = 'http://' + self.config.CALLBACK_ADDRESS + self.CALLBACK_QOS + externalId

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
                # BREAKING CHANGE - v0.8.0 
                #reporting_mode= QosAwareness.EventTriggeredReportingConfiguration(wait_time_in_seconds=10))
                #reporting_mode= QosAwareness.PeriodicReportConfiguration(repetition_period_in_seconds=10))
                reporting_mode=reporting_mode)
                #wait_time_between_reports=10)

        except Exception as e:
            self.log.error(Config.LOG_ERROR, str(e))
            raise QoSSubError (str(e))

        subscription_id = subscription.link.split("/")[-1]
        self.qosSubId[externalId] = subscription_id
        self.log.debug(Config.LOG_NEF_SDK, 'Monitoring QoS Event Subscription OK, ID: ' + subscription_id)

        # Request information about a subscription
        subscription_info = qos_awereness.get_subscription(self.config.NET_APP_NAME, subscription_id)
        self.log.debug(Config.LOG_NEF_SDK, 'Monitoring QoS Event Subscription INFO: ' + str(subscription_info))

    def readActiveAndDeleteLocSubscriptionsSDK(self):

        location_subscriber = LocationSubscriber(nef_url=self.NET_API_URL, 
                                        nef_bearer_access_token=self.token,
                                        folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                        capif_host=self.capif_host,
                                        capif_https_port=self.capif_https_port)

        try:
            # Get all subscriptions
            all_subscriptions = location_subscriber.get_all_subscriptions(self.config.NET_APP_NAME, 0, 100)

            for subscription in all_subscriptions:

                # Check, Loc and Con monitor has same subscriptions list
                if id not in self.monConnLossSubId.values() or id not in self.monConnReachSubId.values():
                    id = subscription.link.split("/")[-1]
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Location subscription with ID: " + id)
                    location_subscriber.delete_subscription(self.config.NET_APP_NAME, id)
                
            self.monLocSubId = {}
        except ApiException as e:
            if e.status == 404:
                self.log.debug(Config.LOG_NEF_SDK, "No active Location subscriptions found")
            else: 
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("readActiveAndDeleteLocSubscriptionsSDK -> " + str(e))

    def readActiveAndDeleteConnectionSubscriptionsSDK(self):

        connection_subscriber = ConnectionMonitor(nef_url=self.NET_API_URL, 
                                                nef_bearer_access_token=self.token,
                                                folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                                capif_host=self.capif_host,
                                                capif_https_port=self.capif_https_port)

        try:
            # Get all subscriptions
            all_subscriptions = connection_subscriber.get_all_subscriptions(self.config.NET_APP_NAME, 0, 100)

            for subscription in all_subscriptions:
                id = subscription.link.split("/")[-1]

                # Check, Loc and Con monitor has same subscriptions list
                if id not in self.monLocSubId.values():
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Connection subscription with ID: " + id)
                    connection_subscriber.delete_subscription(self.config.NET_APP_NAME, id)
                
            self.monConnLossSubId  = {}    
            self.monConnReachSubId = {} 
        except ApiException as e:
            if e.status == 404:
                self.log.debug(Config.LOG_NEF_SDK, "No active Connection subscriptions found")
            else: 
                self.log.error(Config.LOG_ERROR, str(e))
                raise ApiError("readActiveAndDeleteLocSubscriptionsSDK -> " + str(e))
        
    def deleteActiveMonLocSubscriptionSDK(self, external_id):

        location_subscriber = LocationSubscriber(nef_url=self.NET_API_URL, 
                                        nef_bearer_access_token=self.token,
                                        folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                        capif_host=self.capif_host,
                                        capif_https_port=self.capif_https_port)
                    
        try:
            if external_id in self.monLocSubId:
                subscription = self.monLocSubId[external_id]

                if subscription:
                    # Delete subscription
                    location_subscriber.delete_subscription(self.config.NET_APP_NAME, subscription)
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Monitor Location subscription with ID: " + subscription)
                    del self.monLocSubId[external_id]
        except Exception as e:
            None

    def deleteActiveMonConSubscriptionSDK(self, external_id):

        connection_subscriber = ConnectionMonitor(nef_url=self.NET_API_URL, 
                                        nef_bearer_access_token=self.token,
                                        folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                        capif_host=self.capif_host,
                                        capif_https_port=self.capif_https_port)
                    
        try:
            if external_id in self.monConnLossSubId:
                subscription = self.monConnLossSubId[external_id]

                if subscription:
                    # Delete subscription
                    connection_subscriber.delete_subscription(self.config.NET_APP_NAME, subscription)
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Monitor Connection subscription with ID: " + subscription)
                    del self.monConnLossSubId[external_id]
        except Exception as e:
            None

        try:
            if external_id in self.monConnReachSubId:
                subscription = self.monConnReachSubId[external_id]

                if subscription:
                    # Delete subscription
                    connection_subscriber.delete_subscription(self.config.NET_APP_NAME, subscription)
                    self.log.debug(Config.LOG_NEF_SDK, "Deleting Monitor Connection subscription with ID: " + subscription)
                    del self.monConnReachSubId[external_id]
        except Exception as e:
            None

    def deleteActiveQosSubscriptionSDK(self, external_id):

        qos_awereness = QosAwareness(nef_url=self.NET_API_URL, 
                                    nef_bearer_access_token=self.token,
                                    folder_path_for_certificates_and_capif_api_key=self.capif_path_certificates,
                                    capif_host=self.capif_host,
                                    capif_https_port=self.capif_https_port)

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
        self.monitor_subscription(externalId)

    def eventMonitorSubClientConnection(self, externalId):

        # Delete active subscriptions
        self.readActiveAndDeleteConnectionSubscriptionsSDK()

        # Create monitoring event Connection Loss subscription
        self.createMonitorEventSubsConnectionLossSDK(externalId)

        # Create monitoring event Connection Reachability subscription
        self.createMonitorEventSubsConnectionReachabilitySDK(externalId)

    def eventMonitorSubClientQoS(self, externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold, qos_reporting_mode):
        
        # Delete active subscriptions
        self.readActiveAndDeleteQosSubscriptionsSDK()

        # Create monitoring event QoS subscription
        self.sessionqos_subscription(externalId, qos_reference, qos_monitoring_parameter, qos_parameter_threshold, qos_reporting_mode)
