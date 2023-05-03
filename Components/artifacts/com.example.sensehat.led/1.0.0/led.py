import sys
import time
import json
import traceback
import concurrent.futures
import random
from enum import Enum
from sense_hat import SenseHat
import awsiot.greengrasscoreipc
from awsiot.greengrasscoreipc.clientv2 import GreengrassCoreIPCClientV2
from awsiot.greengrasscoreipc.model import (
    SubscribeToTopicRequest,
    SubscriptionResponseMessage,
    UnauthorizedError,
    GetThingShadowRequest,
    UpdateThingShadowRequest
)

class Device_Update_Source(Enum):
    STARTUP = "device is initialized with default value"
    UPDATED_BY_CLOUD_SHADOW = "device is updated by shadow"
    UPDATED_BY_LOCAL = "device is updated by local"

def on_joystick_stream_event(event: SubscriptionResponseMessage) -> None:
    try:
        raw_payload = str(event.binary_message.message, "utf-8")
        payload = json.loads(raw_payload)

        joystick_direction = payload["direction"]
        joystick_action = payload["action"]

        if joystick_action != "pressed":
            #ignore action that is NOT pressed
            return

        new_number = CURRENT_NUMBER

        if joystick_direction == "up":
            #increase number until 9
            new_number = min(CURRENT_NUMBER + 1, 9)
        
        if joystick_direction == "down":
            #decrease number until 0
            new_number = max(CURRENT_NUMBER - 1, 0)
        
        update_device_and_cloud_shadow(new_number, Device_Update_Source.UPDATED_BY_LOCAL)

    except:
        traceback.print_exc()

def on_stream_error(error: Exception) -> bool:
    print('Received a stream error.', file=sys.stderr)
    traceback.print_exc()
    return False  # Return True to close stream, False to keep stream open.

def on_stream_closed() -> None:
    print('Subscribe to topic stream closed.')


def check_cloud_shadow_and_update_device(thingName, shadowName):
    print("getting cloud shadow document to check if we need to update device...")
    
    try:
        get_shadow_result = ipc_client.get_thing_shadow(thing_name=thingName, shadow_name=shadowName)

        #convert string to json object
        shadow_json = json.loads(get_shadow_result.payload)

        # if cloud shadow has a new desired number, update the device with the new number
        if 'desired' in shadow_json['state'] and 'number' in shadow_json['state']['desired']:
            number_from_shadow = int(shadow_json['state']['desired']['number'])
            if CURRENT_NUMBER != number_from_shadow:
                update_device_and_cloud_shadow(number_from_shadow, Device_Update_Source.UPDATED_BY_CLOUD_SHADOW)
                print("Device updated to match the newly fetched shadow:" + json.dumps(shadow_json))
                
    except Exception as e:
        print("Error get shadow", type(e), e)
        traceback.print_exc()

# Update device state (number) and report the new state back to cloud shadow
def update_device_and_cloud_shadow(new_number, new_status):
    global CURRENT_NUMBER
    global CURRENT_SOURCE_OF_CHANGE

    # update device state 
    CURRENT_NUMBER = new_number
    CURRENT_SOURCE_OF_CHANGE = new_status
    
    # refresh LED display
    sense.show_letter(str(CURRENT_NUMBER))

    #report device update back to shadow
    current_state =  {
        "state":{
            "reported":{
                "status": CURRENT_SOURCE_OF_CHANGE.value,
                "number": CURRENT_NUMBER
            }
        }
    }

    # if the latest update was done by local joystick, we want to keep the value
    # we will have to set the value to remote shadow desired value
    # otherwise the remote shadow will keep overwriting the local new values.
    if CURRENT_SOURCE_OF_CHANGE == Device_Update_Source.UPDATED_BY_LOCAL:
        current_state['state']["desired"] = {
            "number": CURRENT_NUMBER
        }

    print("New shadow to be reported:" + json.dumps(current_state))
    payload = bytes(json.dumps(current_state), "utf-8")
    
    try:
        result = ipc_client.update_thing_shadow(thing_name=THING_NAME, shadow_name=SHADOW_NAME, payload=payload)
        jsonmsg = json.loads(result.payload)
        print("Cloud shadow updated successfully.")
        return result.payload
        
    except Exception as e:
        print("Error update shadow", type(e), e)
        traceback.print_exc()


# ------ The code exeuction begins here ------

# ------ 1. Initialize parameters and common objects  ------
sense = SenseHat()
ipc_client = GreengrassCoreIPCClientV2()

THING_NAME = "PiWithSenseHat" # Consider to move this to a variable in recipe
SHADOW_NAME = "NumberLEDNamedShadow" # Consider to move this to a variable in recipe
JOYSTICK_TOPIC = "ipc/joystick" # Consider to move this to a variable in recipe

CURRENT_NUMBER = 0 # Default value of the number is 0. Consider to move this to a variable in recipe 
CURRENT_SOURCE_OF_CHANGE = Device_Update_Source.STARTUP

# ------ 2. Once the component is initialized, report the initial state to cloud shadow ------
update_device_and_cloud_shadow(CURRENT_NUMBER, CURRENT_SOURCE_OF_CHANGE)

# ------ 3. Subscribe to local IPC joystick events ------
# SubscribeToTopic returns a tuple with the response and the operation.
_, operation = ipc_client.subscribe_to_topic(topic=JOYSTICK_TOPIC, on_stream_event=on_joystick_stream_event,
                                                on_stream_error=on_stream_error, on_stream_closed=on_stream_closed)

# ------ 4. Loop: Check cloud shadow periodically and update device state to match the cloud shadow if needed ------
while True:
    check_cloud_shadow_and_update_device(THING_NAME, SHADOW_NAME)
    time.sleep(10) #cloud to device shadow sync: every 10 seconds




