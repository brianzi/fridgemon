import time
import numpy as np
import datetime
import requests
import json


i = 0

while(1):
    i += 1
    all_updates = {
        "time": str(datetime.datetime.now()),
        "field1": "test",
        "iteration": i,
        "random number": np.random.random(),
        "sine": np.cos(2*np.pi*i/2)
    }
    if (i % 2 == 0):
        del all_updates["field1"]

    request = []

    now = datetime.datetime.now()
    for k, v in all_updates.items():
        request.append({
            "id": k,
            "value": v,
            "timestamp": now.timestamp(),
        })

    try:
        print(request)
        r = requests.post(
            "http://localhost:5000/update",
            data=json.dumps(request, default=str))
        print(r.status_code)
        print(r.json())
    except BaseException:
        print("no server")
    time.sleep(4*np.random.random())
