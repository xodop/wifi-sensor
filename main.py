from jinja2 import Environment, FileSystemLoader, StrictUndefined
import os
import subprocess
import csv
import json
import time
from pprint import pprint


def parse_csv(csv_file, json_file, key_filter=None, sep=','):
    list_of_dicts = []
    with open(csv_file, newline='') as f:
        csv_reader = csv.DictReader(f, dialect='unix', delimiter=sep)
        for row in csv_reader:
            if key_filter:
                row = {k: v for k, v in row.items() if k in key_filter}
            else:
                row = {k: v for k, v in row.items() if k != ''}
            list_of_dicts.append(row)
    return list_of_dicts


def test_connection(interface, config_file):
    wpa_supplicant_proc = subprocess.Popen(['wpa_supplicant', '-i', f'{interface}', '-c', f'{config_file}', '-f', '/dev/null'])
    time.sleep(5)
    status = subprocess.run(['iw', f'{interface}', 'link'], stdout = subprocess.PIPE, encoding = 'utf-8')
    wpa_supplicant_proc.kill()
    return status.stdout


if __name__ == "__main__":

    self_dir = os.getcwd() + '/'
    template_dir = self_dir + 'templates/'
    config_dir = self_dir
    config_file = config_dir + 'config.json'
    tmp_dir = '/tmp/wifi-sensor/'
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )

    with open(config_file, 'r') as f:
        config = json.load(f)

    mon_if = config['interface']

    # в цикле cоздавать tmp файлы для подключения к wifi и дергать wpa_suppliciant
    template = env.get_template('wpa_supplicant.j2')
    os.makedirs(tmp_dir, exist_ok=True)
    for net in config["nets"]:
        wpa_supplicant_cfg = template.render(net)
        tmp_cfg_file = tmp_dir + 'wpa_supplicant.conf'
        with open(tmp_cfg_file, 'w') as f:
            f.write(wpa_supplicant_cfg)

        result = test_connection(mon_if, tmp_cfg_file)            
        print(result)
        os.remove(tmp_cfg_file)

    os.rmdir(tmp_dir)

'''
    src_file = 'data/capture_ch132.csv'
    dst_file = 'data/capture_ch132.json'
    key_filter = ['Network', 'NetType', 'BSSID', 'ESSID', 'Channel', 'Beacon', 'Data', 'Total', 'BestQuality', 'BestSignal', 'BestNoise', 'MaxRate', 'MaxSeenRate', 'Encryption', 'FirstTime', 'LastTime', 'Carrier'] 

    channel_scan = parse_csv(src_file, dst_file, key_filter, sep=";")
    pprint(channel_scan)
'''
