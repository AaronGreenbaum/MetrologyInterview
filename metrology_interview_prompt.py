"""
2024 Metrology Coop Position 
Coding prompt

This problem is meant to help you demonstrate competency in python, interaction with hardware, and the ability to design tests.
Hardware syncronization can be a challenge with precision movement.  This is a real problem that was resolved by setting up a hardware trigger to a camera, however we could also resolve it with an algorithm.


You must connect to the linear stage, cause it to continuously move back and forth over a range of 2mm.

Develop a method to make the camera object take an image at equal spaced increments as accurately as possible. 

The spacing value should work over a range of 1-100um increments.
You may need to figure out how to adjust the timing of the camera and modify or improve the given classes.
Add in safeguards, show your results over different iterations and write tests for the method.

To connect to the motor go to.
https://software.zaber.com/virtual-device/viewer
you will see the stage after intialization.
select Linear Stages --> LRQ family --> X-LRQ-DE Series -> X-LRQ150AL-DE51

Then copy the cloud link to connect to the device.
c8d2e1c0-3c94-44ec-88f5-0e37e0a4ff16

-Aaron
"""

from zaber_motion import Units, Library, DeviceDbSourceType
from zaber_motion.ascii import Connection, TriggerAction, TriggerCondition
# import numpy as np
import pandas as pd
import time

class ZaberControl(object):
    """
    A wrapper class for zaber motion control
    1. Initialize the object with a connection str and comtype (this will eventually need to be updated to allow for TCP connection)
    Methods
    comtype options : 'serial' used with a comport str like 'COM4', 'iot' used with cloud simulator string.
    connect(): connect to the motor (this is done at init but can be used to reconnect if disconnected)
    home(): home axis
    move_rel(value, velocity:float = 0, accel:float = 0), do a relative move in units, input vel or accel to change params from system default
    move_abs(value, velocity:float = 0, accel:float = 0), same as rel move but absolute position
    pos(): get the position value in degrees units.
    disconnect(): disconnect from the comport.

    """
    def __init__(self, com_port:str, com_type:str = 'serial',
                  db_dir: str = None,scale_factor:int = 1):
        self.com_dat = (com_port, com_type)
        self.is_connected = False
        if db_dir is not None:
            Library.set_device_db_source(DeviceDbSourceType.FILE, db_dir) #"db\devices-public.sqlite"
        self.connect()
        self.scale_factor = scale_factor
    
        self.units = {"unit" :Units.LENGTH_MILLIMETRES,
                       "velocity_unit": Units.VELOCITY_MILLIMETRES_PER_SECOND,
                      "acceleration_unit": Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED}
        
        self.move_settings = {"velocity": 0, "acceleration": 0} # later can be updated to set move/acel values if needed

    def connect(self, alerts:bool = True)-> None:
        # connect to the motor, and initialize axis.
        match self.com_dat[1]:
            case 'serial':
                self.com = Connection.open_serial_port(self.com_dat[0])
            case 'iot':
                self.com = Connection.open_iot(self.com_dat[0])

        if alerts:
            self.com.enable_alerts()
        self.device = self.com.detect_devices()[0] # need to set up a db for indentify devices
        print(f"connected to {self.device}")
        self.axis = self.device.get_axis(1)
        self.triggers = self.device.triggers
        self.triglist = []
        self.triglist.append(self.triggers.get_trigger(1))
        self.is_connected = True
    def disconnect(self):
        self.com.close()
        self.is_connected=False
        print("disconnected from comport")

    def home(self):
        if self.is_connected:
            self.axis.home()
        else:
            print("Not connected to device")
    def pos(self)->float:
        return self.axis.get_position(self.units["unit"])/self.scale_factor
    def move_rel(self, position:float, velocity:float = 0, accel:float = 0, wait_until_idle:bool=False):
        # moves by position value, vel and accel can be modified.
        if self.is_connected:
            self.axis.move_relative(position*self.scale_factor, velocity=velocity*self.scale_factor, acceleration=accel*self.scale_factor, wait_until_idle=wait_until_idle, **self.units)
        else:
            print("not connected to device")
    def move_abs(self, position:float, velocity:float = 0, accel:float = 0,wait_until_idle:bool = False):
        if self.is_connected:
            self.axis.move_absolute(position*self.scale_factor, velocity=velocity*self.scale_factor, acceleration=accel*self.scale_factor,wait_until_idle=wait_until_idle, **self.units)
    def set_cam_trigger_dis(self, distance, trignum:int=1, ioport:int=1):
        # set trig condition for low to hi to low every distance increment
        self.triglist[trignum-1].fire_when_distance_travelled(0,distance*self.scale_factor)
        self.triglist[trignum-1].on_fire(TriggerAction.A,0, "io set do 1 1 schedule 50 0" ) #trigeractionA on axis 0, 50ms LOW-HIGH-LOW pulse on digital output 1
    def enable_trigger(self, trignum:int =1, numbertrigs=None):
        #enable active trigger with optional number of trigs
        if numbertrigs is not None:
            self.triglist[trignum-1].enable(numbertrigs)
        else:
            self.triglist[trignum-1].enable()
    def disable_trigger(self, trignum:int=1):
        # disable trigger condition.
        self.triglist[trignum-1].disable()

class Camera(object):
    """
    connect to your device, trigger image and store positions.

    Method: 
    TakeImage: when triggered, takes an "image" and a position. 
    Return positions: returns Dataframes
    """
    def __init__(self, zaber:ZaberControl):
        self.zaber = zaber
        self.fps = 100
        self.data = []
        self.last_trigger_time = time.time()
        self.frame_number = 0
    def TakeImage(self):
        # trigger to grab an image.

        # check time since last trigger
        time_since_last_image = time.time()-self.last_trigger_time
        if time_since_last_image > 1/self.fps:
            self.last_trigger_time+= time_since_last_image
            self.frame_number +=1
            self.data.append({'frame':self.frame_number, 'pos':self.zaber.pos()})
        else:
            self.data.append({'frame':self.frame_number, 'pos':self.zaber.pos()})
    def GetPositions(self)->pd.DataFrame:
        # return dataframe of positions
        return pd.DataFrame(self.data)
    

if __name__ == "__main__":
    cloud_str = "d25ec0fd-3a9e-4d73-b151-08157feedf6e" # put your cloud str as com_port

    zb = ZaberControl(com_port=cloud_str, com_type='iot')
    cam = Camera(zb)

    zb.home() # need to home the system before use.

    # move from 10-12 mm at 1mm/s
    zb.move_abs(10,1,0,wait_until_idle=True)
    print(zb.pos())
    zb.move_abs(12,1, 0, wait_until_idle=False)
    while zb.axis.is_busy():
        cam.TakeImage()
        time.sleep(.01)
    df = cam.GetPositions()

    print(df)


