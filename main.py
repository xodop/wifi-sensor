from jinja2 import Environment, FileSystemLoader, StrictUndefined
import os
import subprocess
import csv
import json
import time
from pprint import pprint


def parse_csv(csv_file, key_filter=None, sep=','):
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


def test_connection(interface, ssid, config_file, timeout=5):
    result = {
        'ssid': ssid,       #pass ssid as paramter
        'status': None,     #status 0 - Connected, 1 - Not Connected, None - Failed to write
    }
    wpa_supplicant_proc = subprocess.Popen(
            ['wpa_supplicant', '-i', f'{interface}', '-c', f'{config_file}'],
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    time.sleep(timeout)
    status = subprocess.run(
            ['iw', f'{interface}', 'link'], 
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    wpa_supplicant_proc.kill()
    status = status.stdout.strip()
    if status == "Not connected.":
       result['status'] = 1 
    else:
        status = status.replace('\t','').splitlines()
        for line in status:
            if line.startswith('Connected'):
                result['status'] = 0
            else:
                line = line.split(':')
                if line[0] == 'freq': 
                    result[line[0].strip()] = line[1].strip()       #frequancy in MHz
                elif line[0] == 'signal':
                    result[line[0].strip()] = line[1].strip().split()[0]    #signal in dBm 
                elif line[0] == 'rx bitrate' or line[0] == 'tx bitrate':
                    result[line[0].strip()] = line[1].strip().split()[0]    #rate in Mbit/s
    return result


def test_channel(interface, freq, file_name):
    airodump_ng_proc = subprocess.Popen(
            ['airodump-ng', f'{interface}', '--ignore-negative-one', '--output-format', 'kismet', '-n', '10', '-C', f'{freq}', '-w', f'{file_name}'], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    time.sleep(30)
    airodump_ng_proc.kill()


if __name__ == "__main__":

    '''
    config.json format:
    {
        "interface": "NAME",
        "nets": [
            { wpa_supplicant params in JSON format },
            ...
        ]
    }
    '''

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

    template = env.get_template('wpa_supplicant.j2')
    os.makedirs(tmp_dir, exist_ok=True)
    for net in config["nets"]:

        # test wifi connection with wpa_suppliciant
        wpa_supplicant_cfg = template.render(net)
        tmp_cfg_file = tmp_dir + 'wpa_supplicant.conf'
        with open(tmp_cfg_file, 'w') as f:
            f.write(wpa_supplicant_cfg)

        result = test_connection(mon_if, net['ssid'], tmp_cfg_file)
        os.remove(tmp_cfg_file)
    
        #test wifi channel with airodump-ng
        if result['status'] == 0:

            result['cci_ap_list'] = []

            data_file_noext = tmp_dir + 'capture_' + result['freq'] + 'MHz' 
            test_channel(mon_if, result['freq'], data_file_noext)
    
            #filter output and convert csv to json
            src_data_file = data_file_noext + '-01.kismet.csv'
            key_filter = ['Network', 'NetType', 'BSSID', 'ESSID', 'Channel', 'Beacon', 'Data', 'Total', 'BestQuality', 'BestSignal', 'BestNoise', 'MaxRate', 'MaxSeenRate', 'Encryption', 'FirstTime', 'LastTime', 'Carrier'] 

            channel_scan = parse_csv(src_data_file, key_filter, sep=";")
            os.remove(src_data_file)
            #pprint(channel_scan)
            for ap in channel_scan:
                if ap['ESSID'] == net['ssid']:
                    result['bssid'] = ap['BSSID']
                    result['beacon'] = ap['Beacon']
                    result['channel'] = ap['Channel']
                    result['data'] = ap['Data']
                    result['encryption'] = ap['Encryption']
                    result['rate'] = ap['MaxSeenRate']
            counter = 0
            threashold = -70    #dBm
            conn_bssid = result['bssid']
            conn_bssid_nic = conn_bssid[len(conn_bssid)//2+1:] # last 6 octets for NIC
            for ap in channel_scan:
                ap_bssid = ap['BSSID']
                ap_bssid_nic = ap_bssid[len(ap_bssid)//2+1:] #last 6 octetc for NIC
                if ap_bssid_nic != conn_bssid_nic and int(ap['BestQuality']) > threashold:
                    counter += 1
                    result['cci_ap_list'].append({ 'bssid': ap['BSSID'], 'ssid': ap['ESSID'], 'signal': ap['BestQuality'] })

            result['cci_ap'] = counter

        pprint(result)

        os.rmdir(tmp_dir)
         


