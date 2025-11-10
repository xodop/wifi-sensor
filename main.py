#!./venv/bin/python3

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import os
import subprocess
import csv
import json
import time
import re
import shutil
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
                match = re.search('(?:\S{2}:){5}\S{2}', line)
                if match:
                    result['bssid'] = match.group().upper()
            else:
                line = line.split(':')
                if line[0] == 'freq':
                    result[line[0].strip()] = line[1].strip()       #frequancy in MHz
                elif line[0] == 'signal':
                    result[line[0].strip()] = line[1].strip().split()[0]    #signal in dBm 
                elif line[0] == 'rx bitrate' or line[0] == 'tx bitrate':
                    result[line[0].strip()] = line[1].strip().split()[0]    #rate in Mbit/s
    return result

def search_aps_by_ssid(interface, ssid, file_name, timeout=60):
    i = 0
    result = {}
    data_file = file_name + '-01.kismet.csv'
    key_filter = ['NetType', 'BSSID', 'ESSID', 'Channel', 'Beacon', 'Data', 'Total', 'BestQuality', 'BestSignal', 'BestNoise', 'MaxRate', 'MaxSeenRate', 'Encryption', 'FirstTime', 'LastTime', 'Carrier']
    update_wlan_type(interface, 'monitor')

    airodump_ng_proc = subprocess.Popen(
            ['airodump-ng', f'{interface}', '--ignore-negative-one', '--output-format', 'kismet', '-n', '10', '-N', f'{ssid}', '-w', f'{file_name}'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    time.sleep(timeout/2)
    airodump_ng_proc.kill()

    for item in parse_csv(data_file, key_filter, sep=";"):
        result[i] = item
        i += 1
    os.remove(data_file)
    time.sleep(1)

    airodump_ng_proc = subprocess.Popen(
            ['airodump-ng', f'{interface}', '--ignore-negative-one', '--output-format', 'kismet', '-n', '10', '-N', f'{ssid}', '-w', f'{file_name}', '-b', 'a'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            encoding='utf-8'
    )
    time.sleep(timeout/2)
    airodump_ng_proc.kill()

    for item in parse_csv(data_file, key_filter, sep=";"):
        result[i] = item
        i += 1
    os.remove(data_file)

    return result


def test_channel(interface, channel, file_name, timeout=60):
    update_wlan_type(interface, 'monitor')
    airodump_ng_proc = subprocess.Popen(
            ['airodump-ng', f'{interface}', '--ignore-negative-one', '--output-format', 'kismet,csv', '-n', '10', '-c', f'{channel}', '-w', f'{file_name}'], 
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
    return number * multipliers[unit]

def wifi_channel_to_freq(channel):
    #dict of wifi channel numbers and related frequencies in MHz
    wifi_freqs = {
        '1': '2412',
        '2': '2417',
        '3': '2422',
        '4': '2427',
        '5': '2432',
        '6': '2437',
        '7': '2442',
        '8': '2447',
        '9': '2452',
        '10': '2457',
        '11': '2462',
        '12': '2467',
        '13': '2472',
        '14': '2484',
        '36': '5180',
        '40': '5200',
        '44': '5220',
        '48': '5240',
        '52': '5260',
        '56': '5280',
        '60': '5300',
        '64': '5320',
        '100': '5500',
        '104': '5520',
        '108': '5540',
        '112': '5560',
        '116': '5580',
        '120': '5600',
        '124': '5620',
        '128': '5640',
        '132': '5660',
        '136': '5680',
        '140': '5700',
        '144': '5720',
        '149': '5745',
        '153': '5765',
        '157': '5785',
        '161': '5805',
        '165': '5825'
    }
    if type(channel) == int:
        channel = str(channel)
    return wifi_freqs[channel]


def wifi_freq_to_channel(f_mhz):
    #dict of wifi frequencies in MHz and related channel numbers
    wifi_channels = {
        '2412': '1',
        '2417': '2',
        '2422': '3',
        '2427': '4',
        '2432': '5',
        '2437': '6',
        '2442': '7',
        '2447': '8',
        '2452': '9',
        '2457': '10',
        '2462': '11',
        '2467': '12',
        '2472': '13',
        '2484': '14',
        '5180': '36',
        '5200': '40',
        '5220': '44',
        '5240': '48',
        '5260': '52',
        '5280': '56',
        '5300': '60',
        '5320': '64',
        '5500': '100',
        '5520': '104',
        '5540': '108',
        '5560': '112',
        '5580': '116',
        '5600': '120',
        '5620': '124',
        '5640': '128',
        '5660': '132',
        '5680': '136',
        '5700': '140',
        '5720': '144',
        '5745': '149',
        '5765': '153',
        '5785': '157',
        '5805': '161',
        '5825': '165'
    }
    if type(f_mhz) == int:
        channel = str(channel)
    return wifi_channels[f_mhz]



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
    seen_channels = set()
    dict_of_results = {
        'connections': {},
        'seen_aps': {},
        'seen_channels': {}
    }
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

    #delete tmp path with all content if still exist
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    template = env.get_template('wpa_supplicant.j2')
    for i in range(len(config["nets"])):
        net = config["nets"][i]

        # test wifi connection with wpa_suppliciant
        wpa_supplicant_cfg = template.render(net)
        tmp_cfg_file = tmp_dir + 'wpa_supplicant.conf'
        with open(tmp_cfg_file, 'w') as f:
            f.write(wpa_supplicant_cfg)

        #set timeout more than 60 seconds to log connection in wlc
        result = test_connection(mon_if, net['ssid'], tmp_cfg_file, timeout=90)
        
        #retry if connection fails
        retry_count = 0 
        while result['status'] != '0' and retry_count <= retry_limit:
            result = test_connection(mon_if, net['ssid'], tmp_cfg_file, timeout=10)
            retry_count += 1
        result['conn_retries'] = str(retry_count)
        result['rx_bitrate'] = result.pop('rx bitrate')
        result['tx_bitrate'] = result.pop('tx bitrate')

        #append connection result to enumerated dict of connection results    
        dict_of_results['connections'][i] = result
        #print(result)

        #search all active BSSIDs for this net
        data_file_noext = tmp_dir + 'channels_on_' + net['ssid'] 
        seen_aps = search_aps_by_ssid(mon_if, net['ssid'], data_file_noext, timeout=30)
        
        #print(seen_aps)
        
        for k, v in seen_aps.items():
            if v['BSSID'] and v['BSSID'] != 0 and v['BSSID'] != '0':
                dict_of_results['seen_aps'][k] = v
                #fill list of seen channels
                seen_channels.add(v['Channel'])

    seen_channels = list(seen_channels)

    #test wifi channels with airodump-ng
    for i in range(0,len(seen_channels)):
        channel = seen_channels[i]
        result = {}
        result['channel'] = channel
        result['cci_ap_list'] = []

        data_file_noext = tmp_dir + 'capture_' + channel
        test_channel(mon_if, channel, data_file_noext, timeout=30)
    
        #filter kismet output and convert csv to json
        src_data_file = data_file_noext + '-01.kismet.csv'
        key_filter = ['NetType', 'BSSID', 'ESSID', 'Channel', 'Beacon', 'Data', 'Total', 'BestQuality', 'BestSignal', 'BestNoise', 'MaxRate', 'MaxSeenRate', 'Encryption', 'FirstTime', 'LastTime', 'Carrier'] 
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

        counter = 0
        threshold = 70    #module of threshold for signal strength in dBm
        for ap in channel_scan:
            ap_bssid = ap['BSSID']
            ap_bssid_nic = ap_bssid[len(ap_bssid)//2+1:] #last 6 octetc for NIC
            if int(ap['BestQuality']) > -threshold and ap['BestQuality'] != '-1':
                counter += 1
                result['cci_ap_list'].append({ 'bssid': ap['BSSID'], 'ssid': ap['ESSID'], 'signal': ap['BestQuality'], 'channel': ap['Channel'] })
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
        freq = wifi_channel_to_freq(channel)
        result['freq'] = freq
        survey = test_channel_airtime(mon_if, freq)
        survey = survey.split('\n')
        for line in survey:
            line = line.split(':')
            if line[0].strip() != 'frequency':
                if 'time' in line[0].strip():
                    result[line[0].strip()] = str('{:.6f}'.format(round(convert_to_seconds(line[1].strip()), 6)))
                else:
                    result[line[0].strip()] = line[1].strip()
            
        #rename keys which contain whitespaces
        result['active_time'] = result.pop('channel active time')
        result['busy_time'] = result.pop('channel busy time')
        result['transmit_time'] = result.pop('channel transmit time')
        
        #append channel scan result to dict of channel scan results 
        dict_of_results['seen_channels'][i] = result

    #pprint(dict_of_results)    
    #write json to result file and delete tmp dir
    with open(result_file, 'w') as f:
        json.dump(dict_of_results, f)

    os.remove(tmp_cfg_file)
    os.rmdir(tmp_dir)



