import json
import time

import config
from http_server import RestServer

if __name__ == '__main__':
    # Init Db
    with open('data.json', 'r') as f:
        config.g_data['data'] = json.loads(f.read())
    # Init Server
    rest_server = RestServer()
    rest_server.start()
    while True:
        time.sleep(1)
