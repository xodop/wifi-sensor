#!./venv/bin/python3
import os
import json

self_dir = os.getcwd() + '/'
config_dir = self_dir
config_file = config_dir + 'config.json'
zabbix_data = {"data": []}

with open(config_file, 'r') as f:
    config = json.load(f)

for i in range(len(config["nets"])):
    net = config["nets"][i]
    ssid = net["ssid"]
    net_vars = {"{#NUM}": i, "{#SSID}": ssid}
    zabbix_data["data"].append(net_vars)

print(json.dumps(zabbix_data))
