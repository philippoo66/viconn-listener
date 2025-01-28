'''
   Copyright 2025 philippoo66
   
   Licensed under the GNU GENERAL PUBLIC LICENSE, Version 3 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       https://www.gnu.org/licenses/gpl-3.0.html

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''

import serial
import time
import threading
#from datetime import datetime

import settings_ini
import mqtt_util
import utils
import requests_util


queue = []


def handle_received():
    global queue
    while(True):
        if(len(queue) > 0):
            val = None
            name = ""
            addrdata = queue.pop(0)
            for pollitem in settings_ini.poll_items:   # (Name, DpAddr, Len, Scale/Type, Signed)
                if(utils.get_int(pollitem[1]) == addrdata[0]):
                    # address match
                    name = pollitem[0]
                    numelms = len(pollitem)
                    if(numelms > 3):
                        if(str(pollitem[3]).startswith('b:')):
                            #print(f"H perform_bytebit_filter, ispollitem {ispollitem}")
                            val = requests_util.perform_bytebit_filter(addrdata[1], pollitem)
                        else:
                            signd = False
                            if(numelms > 4):
                                signd = utils.get_bool(pollitem[4])
                            val = requests_util.get_value(addrdata[1], pollitem[3], signd)
                    else:
                        #return raw
                        val = utils.arr2hexstr(addrdata[1])

            if(val is None) and settings_ini.log_vitoconnect:
                name = f"{addrdata[0]:04x}"
                val = utils.arr2hexstr(addrdata[1])

            if(val is not None):
                # publish MQTT
                mqtt_util.publish_read(name, addrdata[0], val)

        time.sleep(0.005)




# main ++++++++++++++++++++++++++++++++
def main():
    global queue

    # later from ini
    fullraw_eot_time = 0.02

    # Konfiguration der seriellen Schnittstellen ++++++++++++++
    # Vitoconnect  
    serVicon = serial.Serial(settings_ini.port_vitoconnect,
            baudrate=4800,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0,
            exclusive=True)

    # Optolink Kopf
    serOpto = serial.Serial(settings_ini.port_optolink,
            baudrate=4800,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0,
            exclusive=True)
    
    # run threads ++++++++++++++
    mqtt_util.connect_mqtt()

    tcp_thread = threading.Thread(target=handle_received)
    tcp_thread.daemon = True  # Setze den Thread als Hintergrundthread - wichtig für Ctrl-C
    tcp_thread.start()


    # main loop ++++++++++++++

    #last1rec_time = 0
    last2rec_time = 0
    prev_rec = 0

    buff1 = []
    buff2 = []

    try:
        while True:
            # Lesen von Daten von beiden seriellen Schnittstellen
            data1 = serVicon.read()
            data2 = serOpto.read()

            dir_chg = False

            # Überprüfen, ob Daten von ser1 empfangen wurden und dann auf ser2 schreiben
            if data1:
                serOpto.write(data1)
                #last1rec_time = time.time()
                if(prev_rec == 2):
                    bkp1 = buff1
                    buff1 = []
                    dir_chg = True
                prev_rec = 1    
                buff1.append(data1)

            # Überprüfen, ob Daten von ser2 empfangen wurden und dann auf ser1 schreiben
            if data2:
                serVicon.write(data2)
                last2rec_time = time.time()
                prev_rec = 2
                buff2.append(data2)

            if(buff2):
                try_eval = False
                if(dir_chg):
                    dir_chg = False
                    bkp2 = buff2
                    buff2 = []
                    try_eval = True
                elif(time.time() - last2rec_time > fullraw_eot_time):
                    # eot of opto
                    prev_rec = 0
                    bkp1 = buff1
                    buff1 = []
                    bkp2 = buff2
                    buff2 = []
                    try_eval = True
                
                if(try_eval):
                    dlenidx = 0
                    addr = 0

                    if(len(bkp1) == 4 and bkp1[0] == b'\xf7'):
                        dlenidx = 3
                    elif (len(bkp1) == 5 and bkp1[0:1] == [b'\x01', b'\xf7']):
                        dlenidx = 4

                    if(dlenidx > 0):
                        # KW read request
                        if(len(bkp2) == int.from_bytes(bkp1[dlenidx], byteorder='litte')):
                            addr = bkp1[dlenidx-2:dlenidx]
                            addr = int.from_bytes(addr, byteorder='big')
                    else:
                        if(len(bkp1) == 3 and bkp1[0] == b'\xc7'):
                            dlenidx = 2
                        elif (len(bkp1) == 4 and bkp1[0:1] == [b'\x01', b'\xc7']):
                            dlenidx = 3
                        
                        if(dlenidx > 0):
                            # GWG read request
                            if(len(bkp2) == int.from_bytes(bkp1[dlenidx], byteorder='litte')):
                                addr = bkp1[dlenidx-1]
                                addr = int.from_bytes(addr, byteorder='big')

                    if(addr > 0):
                        # apped to queue to process to MQTT
                        queue.append([addr, bkp2])

            # Wartezeit für die Schleife, um die CPU-Last zu reduzieren
            time.sleep(0.001)  # Anpassen der Wartezeit je nach Anforderung

    except KeyboardInterrupt:
        print("Abbruch durch Benutzer.")
    finally:
        # Schließen der seriellen Schnittstellen
        serVicon.close()
        serOpto.close()
        mqtt_util.exit_mqtt()

if __name__ == "__main__":
    main()
