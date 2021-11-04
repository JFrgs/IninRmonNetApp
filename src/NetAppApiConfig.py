class Config:

    # 5G NEF API endpoint settings
    NET_APP_NAME   = 'qmonTest'
    NET_API_PROT   = 'http'
    NET_API_HOST   = '192.168.202.39'
    NET_API_PORT   = '8888'

    NET_API_USER   = 'admin@my-email.com'
    NET_API_PASS   = 'pass'

    # Change if using separate host
    CALLBACK_HOST  = NET_API_HOST
    CALLBACK_PORT  = '80'

    # Set rMON Collector host
    COLLECTOR_HOST   = 'https://evolved5g-collector.qmon.eu'
    COLLECTOR_USER   = 'test'
    COLLECTOR_PASS   = 'test'

    # JSON File name
    JSON_FILE_NAME   = 'nef_test_data.json'
    ARHIVE_FOLDER    = 'arhive_nef_5g'

    # Log modules
    LOG_5G_NEF   = '5G NEF API'
    LOG_NET_APP  = 'NET App'
    LOG_RMON_APP = 'rMON App'
    LOG_RMON_COL = 'rMON Collector'
