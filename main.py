#!./venv/bin/python3

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import os
import subprocess
import csv
import json
import time
import re
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
    update_wlan_type(interface)
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
       result['status'] = '1'
    else:
        status = status.replace('\t','').splitlines()
        for line in status:
            if line.startswith('Connected'):
                result['status'] = '0'
            else:
                line = line.split(':')
                if line[0] == 'freq':
                    result[line[0].strip()] = line[1].strip()       #frequancy in MHz
                elif line[0] == 'signal':
                    result[line[0].strip()] = line[1].strip().split()[0]    #signal in dBm 
                elif line[0] == 'rx bitrate' or line[0] == 'tx bitrate':
                    result[line[0].strip()] = line[1].strip().split()[0]    #rate in Mbit/s
    return result


def test_channel(interface, freq, file_name, timeout=60):
    update_wlan_type(interface, 'monitor')
    airodump_ng_proc = subprocess.Popen(
            ['airodump-ng', f'{interface}', '--ignore-negative-one', '--output-format', 'kismet,csv', '-n', '10', '-C', f'{freq}', '-w', f'{file_name}'], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    time.sleep(timeout)
    airodump_ng_proc.kill()


def update_wlan_type(interface, wlan_type='managed'):
    subprocess.run(
        ['ip', 'link', 'set', f'{interface}', 'down'],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL,
        encoding='utf-8' 
    )
    subprocess.run(
        ['iw', 'dev', f'{interface}', 'set', 'type', f'{wlan_type}'],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL,
        encoding='utf-8' 
    )
    subprocess.run(
        ['ip', 'link', 'set', f'{interface}', 'up'],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL,
        encoding='utf-8' 
    )


def test_channel_airtime(interface, freq):
    update_wlan_type(interface, 'monitor')
    iw_survey_proc = subprocess.run(
        ['iw', 'dev', f'{interface}', 'survey', 'dump'],
        stdout=subprocess.PIPE, 
        stderr=subprocess.DEVNULL,
        encoding='utf-8' 
    )
    match = re.search(r'(^\s*frequency:\s+5180.*?)\sSurvey', iw_survey_proc.stdout, flags=re.DOTALL|re.MULTILINE)
    if match:
        return match.group(1)


def convert_to_seconds(time_str):
    parts = time_str.split(' ')
    if len(parts) < 2:
        raise ValueError('Bad string format')
    number = float(parts[0])
    unit = parts[1].lower()
    multipliers = {
        'ms': 0.001,
        'milliseconds': 0.001,
        's': 1,
        'sec': 1,
        'seconds': 1,
        'm': 60,
        'min': 60,
        'minutes': 60,
        'h': 3600,
        'hours': 3600,
        'd': 86400,
        'days': 86400
    }
    if unit not in multipliers:
        raise ValueError(f'Unknown unit: {unit}')
    return str(number * multipliers[unit])



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
    dict_of_results = {}
    result_file = '/tmp/result.json'
    retry_limit = 2
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
    for i in range(len(config["nets"])):
        net = config["nets"][i]

        # test wifi connection with wpa_suppliciant
        wpa_supplicant_cfg = template.render(net)
        tmp_cfg_file = tmp_dir + 'wpa_supplicant.conf'
        with open(tmp_cfg_file, 'w') as f:
            f.write(wpa_supplicant_cfg)

        #set timeout to 120 seconds to log connection in wlc
        result = test_connection(mon_if, net['ssid'], tmp_cfg_file, timeout=10)
        retry_count = 0 
        #test wifi channel with airodump-ng
        if result['status'] == '0':

            #result['cci_ap_list'] = []

            data_file_noext = tmp_dir + 'capture_' + result['freq'] + 'MHz' 
            test_channel(mon_if, result['freq'], data_file_noext, timeout=90)
    
            #filter kismet output and convert csv to json
            src_data_file = data_file_noext + '-01.kismet.csv'
            key_filter = ['Network', 'NetType', 'BSSID', 'ESSID', 'Channel', 'Beacon', 'Data', 'Total', 'BestQuality', 'BestSignal', 'BestNoise', 'MaxRate', 'MaxSeenRate', 'Encryption', 'FirstTime', 'LastTime', 'Carrier'] 

            channel_scan = parse_csv(src_data_file, sep=";")
            os.remove(src_data_file)
            
            #get stations on channel from csv
            src_data_file = data_file_noext +  '-01.csv'
            with open(src_data_file, 'r+') as f:
                channel_stations = f.read().split('\n\n')[1]
                f.seek(0)
                f.write(channel_stations)
            channel_stations = parse_csv(src_data_file, sep=",")
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
                    result['noise'] = ap['BestNoise']
            counter = 0
            threshold = 70    #module of threshold for signal strength in dBm
            conn_bssid = result['bssid']
            conn_bssid_nic = conn_bssid[len(conn_bssid)//2+1:] # last 6 octets for NIC
            for ap in channel_scan:
                ap_bssid = ap['BSSID']
                ap_bssid_nic = ap_bssid[len(ap_bssid)//2+1:] #last 6 octetc for NIC
                if ap_bssid_nic != conn_bssid_nic and int(ap['BestQuality']) > -threshold:
                    counter += 1
                    #result['cci_ap_list'].append({ 'bssid': ap['BSSID'], 'ssid': ap['ESSID'], 'signal': ap['BestQuality'] })
            result['cci_aps'] = str(counter)

            #pprint(channel_stations)
            counter = 0
            counter_threshold = 0 
            for station in channel_stations:
                counter += 1
                try:
                    if int(station[' Power']) > -threshold:
                        counter_threshold += 1
                except:
                    pass
            result['stations'] = str(counter)
            result[f'stations_{threshold}dbm'] = str(counter_threshold)

            #get channel airtime data
            survey = test_channel_airtime(mon_if, result['freq'])
            survey = survey.split('\n')
            for line in survey:
                line = line.split(':')
                if line[0].strip() != 'frequency':
                    if 'time' in line[0].strip():
                        result[line[0].strip()] = convert_to_seconds(line[1].strip())
                    else:
                        result[line[0].strip()] = line[1].strip()
            
            #rename keys which contain whitespaces
            result['rx_bitrate'] = result.pop('rx bitrate') 
            result['tx_bitrate'] = result.pop('tx bitrate')
            result['active_time'] = result.pop('channel active time')
            result['busy_time'] = result.pop('channel busy time')
            result['transmit_time'] = result.pop('channel transmit time')
        
        else:
            while result['status'] != '0' and retry_count <= retry_limit:
                result = test_connection(mon_if, net['ssid'], tmp_cfg_file, timeout=10)
                retry_count += 1
        result['conn_retries'] = str(retry_count)
        
        #append result to enumerated dict of results    
        dict_of_results[i] = result
        
    #write json to result file and delete tmp dir
    with open(result_file, 'w') as f:
        json.dump(dict_of_results, f)

    os.remove(tmp_cfg_file)
    os.rmdir(tmp_dir)



