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

class ApiCollector (threading.Thread):

    def __init__(self, log='', config={}):
        threading.Thread.__init__(self)
        self.log = log
        self.config = config
        self.q = queue.Queue()
        self.log.debug(Config.LOG_RMON_COL, "Init thread")

    def run(self):

        self.log.debug(Config.LOG_RMON_COL, "Processing queue")
        while True:
            item = self.q.get()
            self.log.debug(Config.LOG_RMON_COL, "Item in queue")
            self.log.debug(Config.LOG_RMON_COL, f'{item}')

            event = item[0]
            supi = item[1]
            supi_detailed = item[2]

            self.jsonUploadToCollector(event, supi, supi_detailed)

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
        

    def saveToJsonFile(self, json_data, file_name=Config.JSON_FILE_NAME):   
        self.log.debug(json_data) 
        with open(file_name, 'w') as payload:
            json.dump(json_data, payload)

    def jsonUploadToCollector(self, loc_update_data, supi, supi_details_json):
        #self.log.debug(Config.LOG_RMON_COL, loc_update_data)
        loc_json = json.loads(loc_update_data)
        #supi_details_json = supi_details
        self.log.debug(Config.LOG_RMON_COL, str(loc_json))
        #self.log.debug(Config.LOG_RMON_COL, supi)
        self.log.debug(Config.LOG_RMON_COL, str(supi_details_json))


        data = []

        try:
            for parameter in loc_json['locationInfo']:
                #self.log.debug(Config.LOG_RMON_COL, i)
                #self.log.debug(Config.LOG_RMON_COL, loc_json['locationInfo'][i])

                timestamp = datetime.now().astimezone(pytz.timezone('CET')).replace().isoformat(timespec='milliseconds')

                tmp_data = {
                    'api_type': 'NEF',
                    'api_version': '1',
                    'report_type': loc_json['monitoringType'],
                    'parameter': parameter,
                    'param_value_type': 'string',
                    'param_value_string': loc_json['locationInfo'][parameter],
                    'param_value_float': '',
                    'param_value_unit': '',
                    'timestamp': timestamp,
                    'ue_id_type': 'SUPI',
                    'ue_id_value': supi,
                    'ue_name': supi_details_json['name'],
                    'ue_ip_address_v4': supi_details_json['ip_address_v4'],
                    'ue_ip_address_v6': supi_details_json['ip_address_v6'],
                    'ue_mac_address': supi_details_json['mac_address'],
                    'operator_name': supi_details_json['dnn'],
                    'plmn': str(supi_details_json['mcc']).zfill(3)+str(supi_details_json['mnc']).zfill(2),
                    'ue_latitude': supi_details_json['latitude'],
                    'ue_longitude': supi_details_json['longitude'],
                    'ue_speed': supi_details_json['speed'],
                }
                data.append(tmp_data)
        except:
            self.log.debug(Config.LOG_RMON_COL, "No location data present.")

        json_data = {'measurements':data}

        # Init file name
        file_name = '5g_nef_api_' + supi + '_' +str(datetime.now().strftime("%Y-%m-%d_%H-%M-%S")) + ".json"  

        # Save data to JSON file
        self.saveToJsonFile(json_data, file_name)

        # Upload data to server
        self.runUploadFile(file_name)

    def runUploadFile(self, file_name=Config.JSON_FILE_NAME):   

        exception = ""

        self.log.debug(Config.LOG_RMON_COL, 'Upload file to collector')
        try:

            startTransferAt = time.time()

            # Post request using basic http auth
            urlPut = Config.COLLECTOR_HOST + '/upload.php?filename=' + file_name + '&filetype=resultapi'

            with open(file_name, 'rb') as payload: 
                r = requests.put(urlPut, 
                            data=payload, 
                            auth=HTTPBasicAuth(Config.COLLECTOR_USER, Config.COLLECTOR_PASS), timeout=10)

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
