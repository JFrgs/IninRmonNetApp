import time
import json
import requests
import queue
import threading
import shutil
import os
import pytz
from datetime import datetime
from requests.auth import HTTPBasicAuth
from NetAppApiConfig import Config
from lib.NetAppNotify import Notify

class ApiCollector (threading.Thread):

    def __init__(self, log='', config={}):
        threading.Thread.__init__(self)
        self.log = log
        self.config = config
        self.q = queue.Queue()
        self.log.debug(Config.LOG_RMON_COL, "Init thread")

        # Init MN notify 
        self.notify = Notify(log=self.log, config=self.config)
        self.notify.start()

    def run(self):

        self.log.debug(Config.LOG_RMON_COL, "Processing queue")
        while True:
            item = self.q.get()
            self.log.debug(Config.LOG_RMON_COL, "Item in queue")
            
            #self.log.debug(Config.LOG_RMON_COL, f'{item}')

            event = item[0]
            external_id = item[1]

            qos_reporting_mode = ''
            if len(item) >= 3:
                qos_reporting_mode = item[2]

            self.jsonUploadToCollector(event, external_id, qos_reporting_mode)

            self.q.task_done()

    def moveToArhive(self, file_name):
        
        arhive_directory = Config.ARHIVE_FOLDER

        try:
            if not os.path.exists(arhive_directory):
                os.makedirs(arhive_directory)

            shutil.move(file_name, arhive_directory+'/'+file_name)

            self.log.debug(Config.LOG_RMON_COL, 'File moved to arhive: ' + file_name)
        except:
            self.log.debug(Config.LOG_RMON_COL, 'File can not be moved to arhive: ' + file_name)
        
    def saveToJsonFile(self, json_data, file_name):   
        with open(file_name, 'w') as payload:
            json.dump(json_data, payload)

    def jsonUploadToCollector(self, update_data, externalId, qos_reporting_mode):

        data_json = json.loads(update_data)
        #self.log.debug(Config.LOG_RMON_COL, "Prepare JSON for UPLOAD: " + str(data_json))

        # List of measurements
        data = []

        # MN detailed data JSON
        mn_data = {}

        # Report event type, use in file names
        report_event_type = "unknown"

        # TYPE 1 - LOCATION
        if 'locationInfo' in data_json:
            report_event_type = "location"

            try:
                for parameter in data_json['locationInfo']:

                    timestamp = datetime.now().astimezone(pytz.timezone('CET')).replace().isoformat(timespec='milliseconds')

                    # Fill MN detailed JSON
                    if parameter == 'cellId':
                        mn_data['5G Cell ID'] = data_json['locationInfo'][parameter]
                    elif parameter == 'enodeBId':
                        mn_data['5G gNB'] = data_json['locationInfo'][parameter]

                    tmp_data = {
                        'api_type': 'NEF',
                        'api_version': '1',
                        'report_type': data_json['monitoringType'],
                        'report_mode' : 'EVENT_TRIGGERED',
                        'parameter': parameter,
                        'param_value_type': 'string',
                        'param_value_string': data_json['locationInfo'][parameter],
                        'param_value_float': '',
                        'param_value_unit': '',
                        'timestamp': timestamp,
                        'ue_id_type': 'External ID',
                        'ue_id_value': externalId,
                    }
                    data.append(tmp_data)

                # Put MN detailed JSON into Q
                self.log.debug(Config.LOG_RMON_COL, "MN detailed data: " + json.dumps(mn_data))
                external_id_list = [mn_data, externalId]
                self.notify.q.put(external_id_list)
                self.log.debug(Config.LOG_RMON_COL, "Put in queue")
            except:
                self.log.debug(Config.LOG_RMON_COL, "No location data present.")

        # Type 2 -  CONNECTION REACH
        if 'UE_REACHABILITY' in str(data_json):
            report_event_type = "connection"

            try:
                
                timestamp = datetime.now().astimezone(pytz.timezone('CET')).replace().isoformat(timespec='milliseconds')

                parameter = 'reachabilityType'
                # Fill MN detailed JSON
                if data_json['reachabilityType'] is None:
                    mn_data['5G Conn Reachability Type'] = 'Unknown'
                    data_json['reachabilityType'] = ''
                else:
                    mn_data['5G Conn Reachability Type'] = data_json['reachabilityType']

                tmp_data = {
                    'api_type': 'NEF',
                    'api_version': '1',
                    'report_type': data_json['monitoringType'],
                    'report_mode' : 'EVENT_TRIGGERED',
                    'parameter': parameter,
                    'param_value_type': 'float',
                    'param_value_string': '',
                    'param_value_float': str(data_json['reachabilityType']),
                    'param_value_unit': '',
                    'timestamp': timestamp,
                    'ue_id_type': 'External ID',
                    'ue_id_value': externalId,
                }
                data.append(tmp_data)

                # Put MN detailed JSON into Q
                self.log.debug(Config.LOG_RMON_COL, "MN detailed data: " + json.dumps(mn_data))
                external_id_list = [mn_data, externalId]
                self.notify.q.put(external_id_list)
                self.log.debug(Config.LOG_RMON_COL, "Put in queue")
            except:
                self.log.debug(Config.LOG_RMON_COL, "No connection data present.")

        # Type 3 - CONNECTION LOST
        if 'LOSS_OF_CONNECTIVITY' in str(data_json):
            report_event_type = "connection"

            try:
                
                timestamp = datetime.now().astimezone(pytz.timezone('CET')).replace().isoformat(timespec='milliseconds')

                parameter = 'lossOfConnectReason'
                # Fill MN detailed JSON
                loss_con_reason = data_json['lossOfConnectReason']
                if loss_con_reason == 6:
                    mn_data['5G Conn Lost Reason'] = 'UE is deregistered'
                elif loss_con_reason == 7:
                    mn_data['5G Conn Lost Reason'] = 'UE detection timer expires'
                elif loss_con_reason == 8:
                    mn_data['5G Conn Lost Reason'] = 'UE is purged'
                else:
                    mn_data['5G Conn Lost Reason'] = data_json['lossOfConnectReason']


                tmp_data = {
                    'api_type': 'NEF',
                    'api_version': '1',
                    'report_type': data_json['monitoringType'],
                    'report_mode' : 'EVENT_TRIGGERED',
                    'parameter': parameter,
                    'param_value_type': 'float',
                    'param_value_string': '',
                    'param_value_float': str(data_json['lossOfConnectReason']),
                    'param_value_unit': '',
                    'timestamp': timestamp,
                    'ue_id_type': 'External ID',
                    'ue_id_value': externalId,
                }
                data.append(tmp_data)

                # Put MN detailed JSON into Q
                self.log.debug(Config.LOG_RMON_COL, "MN detailed data: " + json.dumps(mn_data))
                external_id_list = [mn_data, externalId]
                self.notify.q.put(external_id_list)
                self.log.debug(Config.LOG_RMON_COL, "Put in queue")
            except:
                self.log.debug(Config.LOG_RMON_COL, "No connection data present.")

        # Type 4 - QoS
        if 'eventReports' in data_json:
            report_event_type = "qos"

            try:
                timestamp = datetime.now().astimezone(pytz.timezone('CET')).replace().isoformat(timespec='milliseconds')
        
                for parameter in data_json['eventReports']:

                    # Fill MN detailed JSON
                    mn_data['5G QoS Status'] =  parameter["event"]

                    # ipv4Addr
                    tmp_data = {
                        'api_type': 'NEF',
                        'api_version': '1',
                        'report_type': parameter["event"],
                        'report_mode' : qos_reporting_mode,
                        'parameter': "ipv4Addr",
                        'param_value_type': 'string',
                        'param_value_string': data_json["ipv4Addr"],
                        'param_value_float': '',
                        'param_value_unit': '',
                        'timestamp': timestamp,
                        'ue_id_type': 'External ID',
                        'ue_id_value': externalId,
                        }
                    data.append(tmp_data) 

                    # appliedQosRef
                    tmp_data = {
                        'api_type': 'NEF',
                        'api_version': '1',
                        'report_type': parameter["event"],
                        'report_mode' : qos_reporting_mode,
                        'parameter': "appliedQosRef",
                        'param_value_type': 'string',
                        'param_value_string': str(parameter["appliedQosRef"]),
                        'param_value_float': '',
                        'param_value_unit': '',
                        'timestamp': timestamp,
                        'ue_id_type': 'External ID',
                        'ue_id_value': externalId,
                        }
                    data.append(tmp_data) 

                    # ulDelays, dlDelays, rtDelays
                    for report in parameter["qosMonReports"]:
                        for key, value in report.items():
                            tmp_data = {
                                'api_type': 'NEF',
                                'api_version': '1',
                                'report_type': parameter["event"],
                                'report_mode' : qos_reporting_mode,
                                'parameter': key,
                                'param_value_type': 'float',
                                'param_value_string': '',
                                'param_value_float': str(value[0]),
                                'param_value_unit': '',
                                'timestamp': timestamp,
                                'ue_id_type': 'External ID',
                                'ue_id_value': externalId,
                                }
                            data.append(tmp_data)

                    # duration, totalVolume, downlinkVolume, uplinkVolume
                    for key, value in parameter["accumulatedUsage"].items():

                        if value == 'None' or value == 'null':
                            continue

                        if key == 'duration':
                            unit = ''
                        else:
                            unit = 'byte'

                        tmp_data = {
                            'api_type': 'NEF',
                            'api_version': '1',
                            'report_type': parameter["event"],
                            'report_mode' : qos_reporting_mode,
                            'parameter': key,
                            'param_value_type': 'float',
                            'param_value_string': '',
                            'param_value_float': str(value),
                            'param_value_unit': unit,
                            'timestamp': timestamp,
                            'ue_id_type': 'External ID',
                            'ue_id_value': externalId,
                            }
                        data.append(tmp_data)

                # Put MN detailed JSON into Q
                self.log.debug(Config.LOG_RMON_COL, "MN detailed data: " + json.dumps(mn_data))
                external_id_list = [mn_data, externalId]
                self.notify.q.put(external_id_list)
                self.log.debug(Config.LOG_RMON_COL, "Put in queue")
            except:
                self.log.debug(Config.LOG_RMON_COL, "No qos data present.")

        json_data = {'measurements':data}

        # Init file name
        #file_name = '5g_nef_api_' + externalId + '_' +str(datetime.now().strftime("%Y-%m-%d_%H-%M-%S")) + ".json"  
        
        file_name = '5g_nef_api_' + report_event_type + "_" + externalId.replace('@','_').replace('.com','_com') + '_' +str(datetime.now().strftime("%Y-%m-%d_%H-%M-%S")) + ".json"  

        #self.log.debug(Config.LOG_RMON_COL, str(json_data))

        # Save data to JSON file
        self.saveToJsonFile(json_data, file_name)

        # Upload data to server
        self.runUploadFile(file_name)

    def runUploadFile(self, file_name):   

        exception = ""

        self.log.debug(Config.LOG_RMON_COL, 'Upload file to collector')
        try:

            startTransferAt = time.time()

            # Post request using basic http auth
            urlPut = self.config.COLLECTOR_HOST + '/upload.php?filename=' + file_name + '&filetype=resultapi'

            with open(file_name, 'rb') as payload: 
                r = requests.put(urlPut, 
                            data=payload, 
                            auth=HTTPBasicAuth(self.config.COLLECTOR_USER, self.config.COLLECTOR_PASS), timeout=10)

            # Upload duration
            stopTransferAt = time.time()
            duration = stopTransferAt - startTransferAt

            # Calculate hash of payload on the client side
            #file_hash = hash_sha1(file_name)
            self.log.debug(Config.LOG_RMON_COL, 'Response from collector: ' + str(r.status_code))

            # Check for valid resonse            
            if r.status_code == 200:
                
                json = r.json()

                if json['status'] == 'ok':
                    #if json['sha1_hash'] == file_hash:
                    #    result = 'Upload OK, duration: ' + str(duration) + ', free disk: ' + str(json['free_disk'] / 1024 / 1024) + ' MBytes'
                    #else:
                    #    raise Exception('Uploaded file hash not OK, file should be uploaded again')
                    result = 'Upload OK, duration: ' + str(duration) + ', free disk: ' + str(json['free_disk'] / 1024 / 1024) + ' MBytes'

                    self.log.debug(Config.LOG_RMON_COL, result)

                    # Move 5G NEF JSON to arhive
                    self.moveToArhive(file_name)

                elif json['status'] == 'fail':
                    
                    if 'details' in json:
                        if json['details'] == 'unauthorized':
                            raise Exception('Unauthorized user, check user/pass')
                        else:
                            raise Exception(json['details'])
                    
                    if 'free_disk' in json:
                        if int(json['free_disk']) == 0:
                            raise Exception('No free disk space available on upload server!')
                    else:
                        raise Exception(json)
                else:
                    raise Exception('Unknown JSON reply')

            else:
                raise Exception('HTTP Return Code: '+str(r.status_code))


        # Request Timeout 
        except requests.exceptions.Timeout as e:
            exception = 'HTTP Timeout: ' + str(e)

        # Request HTTP Error
        except requests.exceptions.HTTPError as e:
            exception = 'HTTP Error: ' + str(e)
        
        # Request Connection Error 
        except requests.exceptions.ConnectionError as e:
            exception = 'HTTP Connection Error: ' + str(e)

        # Out of Memory Exception
        except MemoryError:
            exception = 'Out of Memory'

        # JSON Exception
        except Exception as e:
            exception = str(e)
        
        # General exception
        except:
            exception = 'HTTP THREADING: Timeout'

        if exception != '':
            self.log.debug(Config.LOG_RMON_COL, 'Upload file to collector: ' + str(exception))
