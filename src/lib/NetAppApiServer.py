import json
from aiohttp import web
from NetAppApiConfig import Config
from lib.NetAppApiClient import ApiClient,MonSubError,ApiError,QoSSubError
from lib.NetAppApiCollector import ApiCollector


class ApiServer:

    def __init__(self, log='', config={}):
        self.log = log
        self.config = config
        self.app = web.Application()
        self.active_ext_id = []
        self.mn_api_version = "v2"

        # Init Client object and token
        self.apiClient = ApiClient(log=self.log, config=self.config)

        # Init Collector object
        self.apiCollector = ApiCollector(log=self.log, config=self.config)
        self.apiCollector.start()

    async def handleEventMonitor(self, request):
        
        self.log.debug(Config.LOG_5G_NEF, 'Location monitor event received.')
        if request.body_exists:
            response = await request.read()
            self.log.debug(response)

            externalId = request.match_info['external_id']
            # externalId = json.loads(response.decode('utf-8'))['externalId']
            text = 'Location monitoring update for External ID: {}'.format(externalId)

            if externalId in self.active_ext_id:

                self.log.debug(Config.LOG_5G_NEF, text)
                self.log.debug(Config.LOG_5G_NEF, response.decode('utf-8'))

                # Create JSON file and push to collector queue
                event = response.decode('utf-8')
                external_id_list = [event, externalId]
                self.apiCollector.q.put(external_id_list)
                self.log.debug(Config.LOG_5G_NEF, "Put in queue")

                return web.json_response({"result" : "ok"}, status=web.HTTPOk.status_code)
            else:
                self.log.debug(Config.LOG_RMON_APP, 'External ID not registered in 5G network ' + externalId)
                return web.Response(text='External ID not registered in 5G network', status=web.HTTPBadRequest.status_code) 

    async def handleQoSMonitor(self, request):
            
        self.log.debug(Config.LOG_5G_NEF, 'QoS monitor event received.')
        if request.body_exists:
            response = await request.read()
            self.log.debug(response)

            externalId = request.match_info['external_id']
            text = 'QoS monitoring update for External ID: {}'.format(externalId)

            if externalId in self.active_ext_id:

                self.log.debug(Config.LOG_5G_NEF, text)
                self.log.debug(Config.LOG_5G_NEF, response.decode('utf-8'))

                # Create JSON file and push to collector queue
                event = response.decode('utf-8')
                external_id_list = [event, externalId]
                self.apiCollector.q.put(external_id_list)
                self.log.debug(Config.LOG_5G_NEF, "Put in queue")

            return web.json_response({"result" : "ok"}, status=web.HTTPOk.status_code)
        else:
            self.log.debug(Config.LOG_RMON_APP, 'External ID not registered in 5G network ' + externalId)
            return web.Response(text='External ID not registered in 5G network', status=web.HTTPBadRequest.status_code) 

    async def handleRegisterApiMn(self, request):

        registered_now = False
    
        if request.body_exists:
            response = await request.read()

            # External ID
            external_id = json.loads(response.decode('utf-8'))['external_id']

            # set default values for qos
            qos_reference=2
            qos_monitoring_parameter="UPLINK"
            qos_parameter_threshold=0

            # get values for qos
            if 'qos_reference' in json.loads(response.decode('utf-8')).keys():
                qos_reference = int(json.loads(response.decode('utf-8'))['qos_reference'])

            if 'qos_monitoring_parameter' in json.loads(response.decode('utf-8')).keys():
                qos_monitoring_parameter = json.loads(response.decode('utf-8'))['qos_monitoring_parameter']

            if 'qos_parameter_threshold' in json.loads(response.decode('utf-8')).keys():
                qos_parameter_threshold = int(json.loads(response.decode('utf-8'))['qos_parameter_threshold'])

            # temp workaround
            if not external_id in self.active_ext_id:

                self.log.debug(Config.LOG_RMON_APP, 'Register received from: ' + external_id)

                # Check if Client token exists
                if self.apiClient.token:

                    try:
                        # subscribe to location monitor reporting api
                        self.log.debug(Config.LOG_RMON_APP, 'Trying to subscribe to event monitor api or ' + external_id)
                        self.apiClient.eventMonitorSubClientLocation(external_id)
                        registered_now = True
                    except MonSubError as e:
                        self.log.error(Config.LOG_RMON_APP, 'Monitoring Subscription error for ' + external_id + ': ' + str(e))
                        return web.json_response({"reason" : str(e)}, status=web.HTTPNotFound.status_code)
                    except Exception as e:
                        self.log.error(Config.LOG_RMON_APP, 'Unknown Monitoring Subscription error for ' + external_id + ': ' + str(e))
                        return web.json_response({"reason" : str(e)}, status=web.HTTPInternalServerError.status_code)

                    # add to active external_id list
                    self.active_ext_id.append(external_id)

                else:
                    self.log.error(Config.LOG_RMON_APP, 'api comm error - ' + external_id)
                    return web.json_response({"reason" : "api comm error"}, status=web.HTTPInternalServerError.status_code)

            try:
                # subscribe to QoS profile and reporting api
                # check if already exists and change if necessary
                self.log.debug(Config.LOG_RMON_APP, 'Trying to subscribe to session with qos api or ' + external_id)
                self.apiClient.eventMonitorSubClientQoS(external_id, qos_reference, qos_monitoring_parameter, qos_parameter_threshold)
            except QoSSubError as e:
                self.log.error(Config.LOG_RMON_APP, 'QoS Subscription error for ' + external_id + ': ' + str(e))
                
                # Delete Monitoring Location external ID
                if registered_now is True:
                    self.apiClient.deleteActiveMonSubscriptionSDK(external_id)

                return web.json_response({"reason" : str(e)}, status=web.HTTPNotAcceptable.status_code)
            except Exception as e:
                self.log.error(Config.LOG_RMON_APP, 'Unknown QoS Subscription error for ' + external_id + ': ' + str(e))

                # Delete Monitoring Location external ID
                if registered_now is True:
                    self.apiClient.deleteActiveMonSubscriptionSDK(external_id)

                return web.json_response({"reason" : str(e)}, status=web.HTTPInternalServerError.status_code)

            return web.json_response({"status" : "ok"}, status=web.HTTPCreated.status_code)


    async def handleDeregisterApiMn(self, request):

        self.log.debug(Config.LOG_RMON_APP, 'Deregister request received.')
        if request.body_exists:
            response = await request.read()

            # External ID
            external_id = json.loads(response.decode('utf-8'))['external_id']

            if external_id in self.active_ext_id:
                self.active_ext_id.remove(external_id)
                self.log.debug(Config.LOG_RMON_APP, 'Deregister received from ' + external_id)

                # Delete all active NetApp Monitor Location subscriptions
                self.apiClient.deleteActiveMonSubscriptionSDK(external_id)

                # Delete all active NetApp QoS subscriptions 
                self.apiClient.deleteActiveQosSubscriptionSDK(external_id)

                return web.Response(text='ok', status=web.HTTPOk.status_code)
            else:
                self.log.debug(Config.LOG_RMON_APP, 'External ID not registered in 5G network ' + external_id)
                return web.Response(text='External ID not registered in 5G network', status=web.HTTPNotAcceptable.status_code)


    async def handleSetQoSProfileMn(self, request):

        # self.log.debug(Config.LOG_RMON_APP, 'Set slice request received.')
        if request.body_exists:
            response = await request.read()
            self.log.debug(response)

            externalId = request.match_info['external_id']

            return web.Response(text='', status=web.HTTPNotImplemented.status_code)

    async def handleGetQoSProfileMn(self, request):

        # self.log.debug(Config.LOG_RMON_APP, 'Set slice request received.')
        if request.body_exists:
            response = await request.read()
            self.log.debug(response)

            externalId = request.match_info['external_id']

            return web.Response(text='', status=web.HTTPNotImplemented.status_code)

    async def handleApiVersion(self, request):

        return web.json_response({"mn_version_api" : self.mn_api_version}, status=web.HTTPOk.status_code)

    def runServer(self):

        self.log.debug('NetApp API Server starting ...')

        # Validate API Client
        if self.apiClient.validateTokenSDK():
            self.app.add_routes([web.get('/api/mn/version', self.handleApiVersion),
                    web.post('/api/mn/register', self.handleRegisterApiMn),
                    web.post('/api/mn/deregister', self.handleDeregisterApiMn),
                    web.post('/api/mn/set-qos-profile/{external_id}', self.handleSetQoSProfileMn),
                    web.post('/api/mn/get-qos-profile/{external_id}', self.handleGetQoSProfileMn),
                    web.post(self.apiClient.CALLBACK_MON+'{external_id}', self.handleEventMonitor),
                    web.post(self.apiClient.CALLBACK_QOS+'{external_id}', self.handleQoSMonitor)
                    ])

            web.run_app(self.app, port=80)
        else:
            self.log.debug(Config.LOG_5G_NEF, 'API Client can not be validated. Exiting...')


        
