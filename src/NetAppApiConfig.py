class Config:

    # 5G NEF API endpoint settings
    NET_APP_NAME   = 'qmonTest'
    NET_API_PROT   = 'http'
    NET_API_ADDRESS   = '192.168.202.35' + ':' + '8888'

    NET_API_USER   = 'admin@my-email.com'
    NET_API_PASS   = 'pass'

    # Change if using separate host
    CALLBACK_ADDRESS  = '192.168.202.35' + ':' + '80'

    # Set rMON Collector host
    COLLECTOR_HOST   = 'https://evolved5g-collector.qmon.eu'
    COLLECTOR_USER   = 'test'
    COLLECTOR_PASS   = 'test'

    # Set MN API host
    MN_HOST = 'http://evolved5g-mn.qmon.eu'
    MN_TOKEN = 'd074feb62430a78e49b5a6da58cb81827e4229b9e3a4ecb28d2a3e47469871247e15ab95a9f34ac713682cebee1031c4da3a'

    # JSON File name
    JSON_FILE_NAME   = 'nef_test_data.json'
    ARHIVE_FOLDER    = 'arhive_nef_5g'

    # Log modules
    LOG_5G_NEF   = '5G NEF API'
    LOG_NEF_SDK  = '5G NEF SDK'
    LOG_NET_APP  = 'NET App'
    LOG_RMON_APP = 'rMON App'
    LOG_RMON_COL = 'rMON Collector'
    LOG_ERROR    = 'NET App Error'
    LOG_NOTIFY   = 'MN Notify'

    # CAPIF JSON path 
    CAPIF_PATH = '/home/ubuntu/test_capif/'
    CAPIF_HOSTNAME = 'capifcore'
    CAPIF_PORT_HTTP = 8080
    CAPIF_PORT_HTTPS = 443

"""
class Config:

    # 5G NEF API endpoint settings
    NET_APP_NAME   = 'test'
    NET_API_PROT   = 'http'
    NET_API_HOST   = '0.0.0.0'
    NET_API_PORT   = '8888'

    NET_API_USER   = 'test'
    NET_API_PASS   = 'test'

    # Change if using separate host
    CALLBACK_HOST  = '0.0.0.0'
    CALLBACK_PORT  = '80'

    # Set rMON Collector host
    COLLECTOR_HOST   = 'https://test.com'
    COLLECTOR_USER   = 'test'
    COLLECTOR_PASS   = 'test'

    # JSON File name
    JSON_FILE_NAME   = 'nef_test_data.json'
    ARHIVE_FOLDER    = 'arhive_nef_5g'

    # Log modules
    LOG_5G_NEF   = '5G NEF API'
    LOG_NEF_SDK  = '5G NEF SDK'
    LOG_NET_APP  = 'NET App'
    LOG_RMON_APP = 'rMON App'
    LOG_RMON_COL = 'rMON Collector'
    LOG_ERROR    = 'NET App Error'
    LOG_NOTIFY   = 'MN Notify'

    # CAPIF JSON path 
    CAPIF_JSON_PATH = 'capif_register.json'

"""