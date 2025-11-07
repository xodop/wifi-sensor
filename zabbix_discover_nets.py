#!./venv/bin/python3
import os
from sys import argv
import json

result_file = '/tmp/result.json'
zabbix_data = {'data': []}

with open(result_file, 'r') as f:
    result = json.load(f)

if len(argv) == 1 or argv[1] == '--connection':
    for i in list(result['connections'].keys()):
        i_vars = {'{#NUM}': i, '{#SSID}': result['connections'][i]['ssid']}
        zabbix_data["data"].append(i_vars)
elif len(argv) > 2:
    raise ValueError('Wrong number of arguments! Available one argument at once')
elif argv[1] == '--ap':
    for i in list(result['seen_aps'].keys()):
        i_vars = {"{#BSSID}": i}
        zabbix_data["data"].append(i_vars) 
elif argv[1] == '--channel':
    for i in list(result['seen_channels'].keys()):
        i_vars = {"{#CHANNEL}": i}
        zabbix_data["data"].append(i_vars)
else:
    raise ValueError('Wrong argument! Available agruments: --connection (default), --ap or --channel')

print(json.dumps(zabbix_data))

