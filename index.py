import jwt
import requests
import json
import socket
import time
import os
import datetime
import sys
from influxdb import InfluxDBClient
from random import randrange

people = ["example1@cisco.com", "example2@cisco.com", "example3@cisco.com"]


def createJsonObj(eventType, event):
    rnd = randrange(5)
    json_body = [{
        "measurement": 'DNASpaces',
        "tags": {
            'eventType': eventType,
            'email': people[rnd],
            'location': event['devicePresence']['location']['name']
        },
        "fields": {
            'email': people[rnd],
            'visitDurationMinutes': int(event['devicePresence']['visitDurationMinutes']),
            'location': event['devicePresence']['location']['name']
        }
    }]
    if event['devicePresence']['device']['email'] != "" and event['devicePresence']['visitDurationMinutes'] != 0:
        return json_body
    else:
        return False


def get_API_Key_and_auth():
    # Gets public key from spaces and places in correct format
    print("-- No API Key Found --")
    pubKey = requests.get(
        'https://partners.dnaspaces.io/client/v1/partner/partnerPublicKey/')
    pubKey = json.loads(pubKey.text)
    pubKey = pubKey['data'][0]['publicKey']
    pubKey = '-----BEGIN PUBLIC KEY-----\n' + pubKey + '\n-----END PUBLIC KEY-----'

    # Gets user to paste in generated token from app
    token = input('Enter token here: ')

    # Decodes JSON Web Token to get JSON out
    decodedJWT = jwt.decode(token, pubKey)
    decodedJWT = json.dumps(decodedJWT, indent=2)
    # print(decodedJWT)

    # picks up required values out of JWT
    decodedJWTJSON = json.loads(decodedJWT)
    appId = decodedJWTJSON['appId']
    activationRefId = decodedJWTJSON['activationRefId']

    # creates payloads and headers ready to activate app
    authKey = 'Bearer ' + token
    payload = {'appId': appId, 'activationRefId': activationRefId}
    header = {'Content-Type': 'application/json', 'Authorization': authKey}

    # Sends request to spaces with all info about JWT to confirm its correct, if it is, the app will show as activated
    activation = requests.post(
        'https://partners.dnaspaces.io/client/v1/partner/activateOnPremiseApp/', headers=header, json=payload)

    # print(activation.text)
    activation = json.loads(activation.text)
    # print(activation['message'])

    apiKey = activation['data']['apiKey']
    f = open("API_KEY.txt", "a")
    f.write(apiKey)
    f.close()
    return apiKey


# work around to get IP address on hosts with non resolvable hostnames
client = InfluxDBClient(host='localhost', port=8086,
                        username='admin', password='admin123')
client.switch_database('telegraf')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
IP_ADRRESS = s.getsockname()[0]
s.close()
url = 'http://' + str(IP_ADRRESS) + '/update/'

try:
    if os.stat("API_KEY.txt").st_size > 0:
        f = open("API_KEY.txt")
        apiKey = f.read()
        f.close()
        # print("-- API Key Found -- ")
        # print("-- If you wanted to renew your API key, just delete the file API_KEY.txt --")
    else:
        apiKey = get_API_Key_and_auth()
except:
    apiKey = get_API_Key_and_auth()

# overwrite previous log file
f = open("log_file.json", 'w')
s = requests.Session()
s.headers = {'X-API-Key': apiKey}
r = s.get(
    'https://partners.dnaspaces.io/api/partners/v1/firehose/events', stream=True)


print("Starting Stream")
for line in r.iter_lines():
    if line:
        f.write(str(json.dumps(json.loads(line), indent=4, sort_keys=True)))
        decoded_line = line.decode('utf-8')
        decoded_line = decoded_line.replace("false", "\"false\"")
        decoded_line = decoded_line.replace(" ", "")
        event = json.loads(decoded_line)
        eventType = event['eventType']
        # print(eventType)
        # print(type(eventType))
        if eventType == 'DEVICE_PRESENCE':
            jsonObj = createJsonObj(eventType, event)
            #jsonObj = json.dumps(jsonObj)
            # print(decoded_line)
            # print(type(jsonObj))
            if jsonObj != False:
                result = client.write_points(
                    jsonObj, database='telegraf', protocol='json')
                print(result)
