#!/usr/bin/python

import os
import io
import sys
import fcntl
import time
import datetime
import copy
import string
from AtlasI2C import (
	 AtlasI2C
)



def main():

    device_list = get_devices()

    device = device_list[0]

    print_help_text()

    print_devices(device_list, device)

    real_raw_input = vars(__builtins__).get('raw_input', input)

    while True:
    
        user_cmd = real_raw_input(">> Enter command: ")
        
        # show all the available devices
        if user_cmd.upper().strip().startswith("LIST"):
            print_devices(device_list, device)
            
        # print the help text 
        elif user_cmd.upper().startswith("HELP"):
            print_help_text()


        ###  sample a single measurement from the probe
        elif user_cmd.upper().strip().startswith('SAMPLE'):
            cmd_list = user_cmd.split(',')

            ###  setting parameters if provided
            N = 1
            delay = 2
            if len(cmd_list) > 1:
                N = int(cmd_list[1])
            if len(cmd_list) > 2:
                delay = float(cmd_list[2])

            print('Sampling measurements from %s sensor' % device_list[0]._module)
            measurements = sample(device_list[0], N=N, delay=delay, verbose=True)


        ###  continuously record measurements to the given file name
        ###  Example >>> RECORD,filename.txt,delay
        elif user_cmd.upper().strip().startswith('RECORD'):
            cmd_list = user_cmd.split(',')

            if len(cmd_list) != 2:
                raise IOError('Invalid input(s)')

            ###  parsing number of samples
            N = None
            if len(cmd_list) > 2:
                N = int(cmd_list[2])

            ###  parsing sampling delay
            delay = 2
            if len(cmd_list) > 3:
                delay = float(cmd_list[3])

            record(device_list[0], cmd_list[1], N=N, delay=delay)


        # continuous polling command automatically polls the board
        elif user_cmd.upper().strip().startswith("POLL"):
            cmd_list = user_cmd.split(',')
            if len(cmd_list) > 1:
                delaytime = float(cmd_list[1])
            else:
                delaytime = device.long_timeout

            # check for polling time being too short, change it to the minimum timeout if too short
            if delaytime < device.long_timeout:
                print("Polling time is shorter than timeout, setting polling time to %0.2f" % device.long_timeout)
                delaytime = device.long_timeout
            try:
                while True:
                    print("-------press ctrl-c to stop the polling")
                    for dev in device_list:
                        dev.write("R")
                    time.sleep(delaytime)
                    for dev in device_list:
                        print(dev.read())
                
            except KeyboardInterrupt:       # catches the ctrl-c command, which breaks the loop above
                print("Continuous polling stopped")
                print_devices(device_list, device)
                
        # send a command to all the available devices
        elif user_cmd.upper().strip().startswith("ALL:"):
            cmd_list = user_cmd.split(":")
            for dev in device_list:
                dev.write(cmd_list[1])
            
            # figure out how long to wait before reading the response
            timeout = device_list[0].get_command_timeout(cmd_list[1].strip())
            # if we dont have a timeout, dont try to read, since it means we issued a sleep command
            if(timeout):
                time.sleep(timeout)
                for dev in device_list:
                    print(dev.read())
                
        # if not a special keyword, see if we change the address, and communicate with that device
        else:
            try:
                cmd_list = user_cmd.split(":")
                if(len(cmd_list) > 1):
                    addr = cmd_list[0]
                    
                    # go through the devices to figure out if its available
                    # and swith to it if it is
                    switched = False
                    for i in device_list:
                        if(i.address == int(addr)):
                            device = i
                            switched = True
                    if(switched):
                        print(device.query(cmd_list[1]))
                    else:
                        print("No device found at address " + addr)
                else:
                    # if no address change, just send the command to the device
                    print(device.query(user_cmd))
            except IOError:
                print("Query failed \n - Address may be invalid, use list command to see available addresses")




def print_devices(device_list, device):
    for i in device_list:
        if(i == device):
            print("--> " + i.get_device_info())
        else:
            print(" - " + i.get_device_info())
    #print("")
    

def get_devices():
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    device_list = []
    
    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("I")
        moduletype = response.split(",")[1] 
        response = device.query("name,?").split(",")[1]
        device_list.append(AtlasI2C(address = i, moduletype = moduletype, name = response))
    return device_list 


def print_help_text():
    print('''
    Description
    -----------
        Atlas Scientific I2C sample code
        Any commands entered are passed to the default target device via I2C except:

    Commands
    --------
        Help
            Brings up this menu

        List 
            Lists the available I2C circuits.
            The --> indicates the target device that will receive individual commands
        
        Sample,N,delay
            Sample measurements from all devices
            N ------- Number of measurements to sample (default=1)
            delay --- Delay time between samplings (seconds, default=2)

        Poll,delay
          Continuously polls all devices
          delay ----- Delay time between samplings (seconds, default=2)
        
        xxx:[command]
          Sends the command to the device at I2C address xxx 
          and sets future communications to that address
          Ex: "102:status" will send the command status to address 102
        
        all:[command]
          Sends the command to all devices

    Exit
    ----
        Press Ctrl-c to stop
    ''')
    return None


def sample(device, N=1, delay=2, verbose=True):
    '''
    Description
    -----------
        Sample `N` measurements from all devices every `delay` seconds

    Parameters
    ----------
        device : AtlasI2C.AtlasI2C
            Atlas Scientific device

        N : int
            Number of measurements to sample

        delay : float
            Delay time (in seconds) between samplings

        verbose : bool
            Print individual samplings to screen
    '''

    ###  sampling measurements
    measurements = []
    for i_sample in range(N):
        device.write("R")
        time.sleep(delay)
        #print(device.read())
        measurement = device.read_value(num_of_bytes=31)
        measurements.append(measurement['value'])
        if verbose == True:
            print('%s,%s,%.3f' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), measurement['module'], measurement['value']))

    return measurements


def record(device, filename, N=None, delay=2):
    '''
    Description
    -----------
        Continuously samples device and saves readings to output file

    Parameters
    ----------
        device : AtlasI2C.AtlasI2C
            Atlas Scientific device

        filename : str
            File name or path to save output to

        N : int
            Number of readings to make. If `None` will sample indefinitely

        delay : float
            Delay time (in seconds) between samplings
    '''

    ###  parsing output file path, if no path was specified 
    ###  (i.e. onlay a filename), then save to ../data/
    if os.path.sep not in filename:
        filepath = os.path.join('..', 'data', filename)
    elif filename.endswith(os.path.sep):
        raise IOError('Provided path must include a valid file name')
    else:
        filepath = filename

    ###  NOTE: THIS CODE WAS WRITTEN TO HANDLE ONLY READINGS FROM ONE
    ###        SENSOR. IT MAY NOT WORK WITH MULTIPLE SENSORS ATTACHED
    ###  initializing output file
    print('Reading %s sensor' % device._module)
    print('Saving readings to %s' % filepath)
    with open(filepath, 'w') as fopen:
        fopen.write('timestamp,device,measurement\n')

    ###  continuously sampling sensor
    counter = 0
    while True:
        counter += 1
        if (N is not None) and (counter > N):
            break
        time.sleep(delay)
        measurement = device.read_value(num_of_bytes=31)
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(filepath, 'w') as fopen:
            fopen.write('%s,%s,%.3f\n' % (now, measurement['module'], measurement['value']))


def exit():
    ###  define exit function
    pass


if __name__ == '__main__':
    main()







