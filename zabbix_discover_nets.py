#!./venv/bin/python3
import os
from sys import argv
import json

result_file = '/tmp/result.json'
zabbix_data = {'data': []}

with open(result_file, 'r') as f:
    result = json.load(f)

if len(argv) == 1 or argv[1] == '--connection':
    for k, v in result['connections'].items():
        i_vars = {'{#SSID}': v['ssid']}
        zabbix_data["data"].append(i_vars)
elif len(argv) > 2:
    raise ValueError('Wrong number of arguments! Available one argument at once')
elif argv[1] == '--ap':
    for k,v in result['seen_aps'].items():
        i_vars = {'{#BSSID}': v['BSSID'], '{#SSID}': v['ESSID'], '{#CH}': v['Channel']}
        zabbix_data["data"].append(i_vars) 
elif argv[1] == '--channel':
    for k,v in result['seen_channels'].items():
        i_vars = {'{#CH}': v['channel']}
        zabbix_data["data"].append(i_vars)
else:
    raise ValueError('Wrong argument! Available agruments: --connection (default), --ap or --channel')

print(json.dumps(zabbix_data))

