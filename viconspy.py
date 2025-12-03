import serial
import time
from datetime import datetime
import atexit


PORT_VICON = '/dev/ttyS0'
PORT_OPTO = '/dev/ttyUSB0'
EOT_TIME = 0.01  # ~2.3ms pro byte



def main():
    print("Version 000")
    print("open serial ports")
    # Konfiguration der seriellen Schnittstellen ++++++++++++++
    # Optolink Kopf
    serOpto = serial.Serial(PORT_OPTO,
            baudrate=4800,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0,
            exclusive=True)
    # Vitoconnect  
    serVicon = serial.Serial(PORT_VICON,
            baudrate=4800,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0,
            exclusive=True)

    
    ts = datetime.now().strftime("%y%m%d%H%M%S")
    logf = 'spylog_' + ts + '.csv'
    # Öffnen der Ausgabedatei im Schreibmodus
    vlog = open(logf, 'a')

    buff1 = bytearray()
    buff2 = bytearray()

    def at_exit():
        serOpto.close()
        serVicon.close()
        vlog.write(f"{time.time():.3f};{bbbstr(buff1)};{bbbstr(buff2)}\n")
        vlog.close()

    atexit.register(at_exit)

    last1 = time.time() + 1000
    last2 = time.time() + 1000

    while(True):
        # Lesen von Daten von beiden seriellen Schnittstellen
        data1 = serOpto.read_all()
        data2 = serVicon.read_all()
        now = time.time()

        if(data1):
            serVicon.write(data1)
            buff1 += data1
            last1 = now
            print(f"O {data1}")

            if(buff2):
                vlog.write(f"{time.time():.3f};;{bbbstr(buff2)}\n")
                buff2 = bytearray()
                
        if(data2):
            serOpto.write(data2)
            buff2 += data2
            last2 = now
            print(f"V {data2}")

            if(buff1):
                vlog.write(f"{time.time():.3f};{bbbstr(buff1)};\n")
                buff1 = bytearray()
        
        if (buff1) and (now - last1 > EOT_TIME):
            vlog.write(f"{time.time():.3f};{bbbstr(buff1)};\n")
            buff1 = bytearray()
            
        if (buff2) and (now - last2 > EOT_TIME):
            vlog.write(f"{time.time():.3f};;{bbbstr(buff2)}\n")
            buff2 = bytearray()

        time.sleep(0.001)  # Anpassen der Wartezeit je nach Anforderung


def bbbstr(data) -> str:
    if not data: return ''
    return ' '.join([format(byte, '02x') for byte in data])


if __name__ == "__main__":
    main()    