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
    LOG_NET_APP  = 'NET App'
    LOG_RMON_APP = 'rMON App'
    LOG_RMON_COL = 'rMON Collector'
