import requests
import json
import time
from influxdb import InfluxDBClient

# This file is run every 30 seconds by Telegraf
# No data is collected by Telegraf, its used as a scheduler and data is fired straight at InfluxDB

# List of users we want to grab data from
Org = ["example1@cisco.com", "example2@cisco.com", "example3@cisco.com"]

# API key in another file called API_KEY.txt - to improve move this to keychain
f = open("API_KEY.txt")
apiKey = f.read()
f.close()

# Creating the Bearer token from key
Auth = 'Bearer ' + apiKey
responses = []

# Influx Setup
client = InfluxDBClient(host='localhost', port=8086,
                        username='admin', password='admin123')
client.switch_database('telegraf')

# Get details about each user in org
for l in Org:
    url = "https://webexapis.com/v1/people?email=" + l
    payload = {}
    headers = {
        'Authorization': Auth
    }

    response = requests.request(
        "GET", url, headers=headers, data=payload).json()

    item = response["items"][0]["id"]
    responses.append(item)

i = 0
runningTime = 30
# For each user
for r in responses:
    # set all variables to 0
    totCall = totActive = totInactive = active = call = DND = inactive = meeting = OOO = pending = presenting = unknown = 0
    url = "https://webexapis.com/v1/people/" + r + "?callingData=true"
    payload = {}
    headers = {
        'Authorization': Auth
    }
    response = requests.request(
        "GET", url, headers=headers, data=payload).json()
    # Get the status
    status = response["status"]
    # Then set variables based upon status
    # I.E. if a user in on a call, they should be given the status of active and on a call and in a meeting
    if status == "active":
        active += runningTime
        totActive = runningTime
    elif status == "call":
        call += runningTime
        totActive = runningTime
        totCall = runningTime
    elif status == "DoNotDisturb":
        DND += runningTime
        totInactive = runningTime
    elif status == "inactive":
        inactive += runningTime
        totInactive = runningTime
    elif status == "meeting":
        meeting += runningTime
        totActive = runningTime
        totCall = runningTime
    elif status == "OutOfOffice":
        OOO += runningTime
        totInactive = runningTime
    elif status == "pending":
        pending += runningTime
        totInactive = runningTime
    elif status == "presenting":
        presenting += runningTime
        totActive = runningTime
        totCall = runningTime
    else:
        unknown += runningTime
        totInactive = runningTime

    # We provide Influx with a series of data that firstly includes their Status
    # We then have a field for each individual status, and if they have that status we set that to 30 as thats the running time
    # When this data gets to Grafana, we can sum the data over a day.
    # This will then give us a cumulative time in seconds someone has been acitve/away over a time period
    jsonObj = [{
        "measurement": "Webex",
        "tags": {
            "userID": r,
            "email": Org[i],
            "status": status
        },
        "fields": {
            "active": active,
            "call": call,
            "DND": DND,
            "inactive": inactive,
            "meeting": meeting,
            "OOO": OOO,
            "pending": pending,
            "presenting": presenting,
            "unknown": unknown,
            "totalActive": totActive,
            "totalInactive": totInactive,
            "totalCall": totCall
        }
    }]
    # This writes to Influx directly
    result = client.write_points(jsonObj, database='telegraf', protocol='json')
    i += 1
