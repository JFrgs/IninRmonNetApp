import json
from aiohttp import web
from NetAppApiConfig import Config
from lib.NetAppApiClient import ApiClient
from lib.NetAppApiCollector import ApiCollector

class ApiServer:

    def __init__(self, log='', config={}):
        self.log = log
        self.config = config
        self.app = web.Application()
        self.active_supi = []
        self.supi_detailed = None
        self.mn_api_version = "v1"

        # Init Client object and token
        self.apiClient = ApiClient(log=self.log, config=self.config)

        # Init Collector object
        self.apiCollector = ApiCollector(log=self.log, config=self.config)
        self.apiCollector.start()

    async def handleLocMonitor(self, request):
    
        self.log.debug(Config.LOG_5G_NEF, 'Location monitor event received.')
        if request.body_exists:
            response = await request.read()
            self.log.debug(response)

            supi = request.match_info['supi']
            text = 'Location monitoring update for SUPI: {}'.format(supi)

            if supi in self.active_supi:
                # Get UE for additional info
                # apiClient = ApiClient(supi=supi, log=self.log, token=self.token, type=self.type, config=self.config)
                self.supi_detailed = self.apiClient.getUeSupi(supi)
                
                self.log.debug(Config.LOG_5G_NEF, 'UE details: ' + str(self.supi_detailed))
                self.log.debug(Config.LOG_5G_NEF, text)
                self.log.debug(Config.LOG_5G_NEF, response.decode('utf-8'))

                # Create JSON file and push to collector queue
                event = response.decode('utf-8')
                supi_list = [event, supi, self.supi_detailed]
                self.apiCollector.q.put(supi_list)
                self.log.debug(Config.LOG_5G_NEF, "Put in queue")

                # self.apiCollector.jsonUploadToCollector(response.decode('utf-8'), supi, self.supi_detailed)

                return web.Response(text='ok', status=web.HTTPOk.status_code)
            else:
                self.log.debug(Config.LOG_RMON_APP, 'SUPI not registered in 5G network ' + supi)
                return web.Response(text='SUPI not registered in 5G network', status=web.HTTPBadRequest.status_code) 

    async def handleRegisterApiMn(self, request):
    
        if request.body_exists:
            response = await request.read()

            supi = json.loads(response.decode('utf-8'))['supi']

            # temp workaround
            if not supi in self.active_supi:

                self.log.debug(Config.LOG_RMON_APP, 'Register received from ' + supi)

                # if supi exists use it otherwise return error
                if self.apiClient.initClientSupi(supi):

                    # add to active supi list
                    self.active_supi.append(supi)

                    # subscribe to location monitor reporting api
                    self.apiClient.eventMonitorSubClient(supi)

                    return web.Response(text='ok', status=web.HTTPOk.status_code)
                else:
                    self.log.debug(Config.LOG_RMON_APP, 'SUPI not registered in 5G network ' + supi)
                    return web.Response(text='SUPI not registered in 5G network', status=web.HTTPNotAcceptable.status_code)
    

    async def handleDeregisterApiMn(self, request):

        self.log.debug(Config.LOG_RMON_APP, 'Deregister request received.')
        if request.body_exists:
            response = await request.read()

            supi = json.loads(response.decode('utf-8'))['supi']

            if supi in self.active_supi:
                self.active_supi.remove(supi)
                self.log.debug(Config.LOG_RMON_APP, 'Deregister received from ' + supi)

                # Check all active NetApp subscriptions
                active_subs = self.apiClient.readActiveSubscriptions()
                # Delete all active NetApp subscriptions
                for i in active_subs:
                    self.apiClient.deleteActiveSubscriptions(i)

                return web.Response(text='ok', status=web.HTTPOk.status_code)
            else:
                self.log.debug(Config.LOG_RMON_APP, 'SUPI not registered in 5G network ' + supi)
                return web.Response(text='SUPI not registered in 5G network', status=web.HTTPNotAcceptable.status_code)



    async def handleSliceApiMn(self, request):

        # self.log.debug(Config.LOG_RMON_APP, 'Set slice request received.')
        if request.body_exists:
            response = await request.read()
            # self.log.debug(response)

            supi = request.match_info['supi']
            net_slice = json.loads(response.decode('utf-8'))['slice']

            if supi in self.active_supi:
                self.log.debug(Config.LOG_RMON_APP, 'Set slice ' + net_slice +  ' request received from ' + supi)

                self.apiClient.setSliceSupi(net_slice, supi)

                return web.Response(text='ok', status=web.HTTPOk.status_code)
            else:
                return web.Response(text='SUPI not registered in 5G network', status=web.HTTPBadRequest.status_code)

            return web.Response(text='ok', status=web.HTTPOk.status_code)

    async def handleApiVersion(self, request):

        return web.Response(text=self.mn_api_version)

    def runServer(self):

        self.log.debug('NetApp API Server starting ...')

        # Validate API Client
        if self.apiClient.validateToken():
            self.app.add_routes([web.get('/api/mn/version', self.handleApiVersion),
                    web.post('/api/mn/register', self.handleRegisterApiMn),
                    web.post('/api/mn/deregister', self.handleDeregisterApiMn),
                    web.post('/api/mn/set-slice/{supi}', self.handleSliceApiMn),
                    web.post('/api/v1/utils/monitoring/callback/{supi}', self.handleLocMonitor)])

            web.run_app(self.app, port=80)
        else:
            self.log.debug(Config.LOG_5G_NEF, 'API Client can not be validated. Exiting...')


        
