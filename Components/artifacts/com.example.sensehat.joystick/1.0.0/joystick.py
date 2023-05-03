import sys
import time
import traceback
import json

import awsiot.greengrasscoreipc
import awsiot.greengrasscoreipc.client as client
from awsiot.greengrasscoreipc.model import (
    #for local ipc msg
    PublishToTopicRequest,
    PublishMessage,
    BinaryMessage
)

from sense_hat import SenseHat
sense = SenseHat()

ipc_publishtopic = str(sys.argv[1])

TIMEOUT = 10

def publishJoystickEvents(ipc_client, ipc_publishtopic):
    try:
        for event in sense.stick.get_events():
            
            message =  {
                "timemillis": round(time.time() * 1000),
                "direction": event.direction,
                "action": event.action
            }

            msgstring = json.dumps(message)

            # ipc local msg publishing
            ipc_request = PublishToTopicRequest()
            ipc_request.topic = ipc_publishtopic
            ipc_publish_message = PublishMessage()
            ipc_publish_message.binary_message = BinaryMessage()
            ipc_publish_message.binary_message.message = bytes(msgstring, "utf-8")

            ipc_request.publish_message = ipc_publish_message
            ipc_operation = ipc_client.new_publish_to_topic()
            ipc_operation.activate(ipc_request)
            ipc_future = ipc_operation.get_response()
            ipc_future.result(TIMEOUT)

    except Exception as e:
        print("Error publishJoystickEvents:", type(e), e)

# have to reuse this client, do not create a new client in every loop
# in case of error: (AWS_ERROR_PRIORITY_QUEUE_EMPTY): Attempt to pop an item from an empty queue..,
# the whole component will be restarted by greengrass
ipc_client = awsiot.greengrasscoreipc.connect()

while True:
    publishJoystickEvents(ipc_client, ipc_publishtopic)

print("Joystick event detect finished")