# author: oskar.blom@gmail.com
#
# Make sure your gevent version is >= 1.0
import gevent
from gevent.wsgi import WSGIServer
from gevent.queue import Queue

from flask import Flask, Response, request

import flask

import json


# SSE "protocol" is described here: http://mzl.la/UPFyxY
class ServerSentEvent(object):

    def __init__(self, data):
        self.data = data
        self.event = None
        self.id = None
        self.desc_map = {
            self.data: "data",
            self.event: "event",
            self.id: "id"
        }

    def encode(self):
        if not self.data:
            return ""
        lines = ["%s: %s" % (v, k)
                 for k, v in self.desc_map.items() if k]

        return "%s\n\n" % "\n".join(lines)


app = Flask(__name__)
subscriptions = []


datadict = {}

# Client code consumes like this.


@app.route("/")
def index():
    return(flask.render_template("index.html",
                                 value_ids=datadict))


@app.route("/debug")
def debug():

    substring = "Currently %d subscriptions" % len(subscriptions)

    html = """
    <html>
    <body>
    {}</br>
    {}
    </body>
    </html>
    """.format(substring, str(datadict))

    return html


@app.route('/update', methods=['POST'])
def update(*args, **kwargs):
    j = json.loads(request.data)
    for i in j:
        datadict[i['id']] = i
    print(datadict)

    def notify():
        msg = json.dumps(j)
        for sub in subscriptions[:]:
            sub.put(msg)
    gevent.spawn(notify)
    return json.dumps(dict(result="ok"))


@app.route("/subscribe")
def subscribe():
    def gen():
        q = Queue()
        subscriptions.append(q)
        try:
            while True:
                result = q.get()
                ev = ServerSentEvent(str(result))
                yield ev.encode()
        except GeneratorExit:  # Or maybe use flask signals
            subscriptions.remove(q)

    return Response(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.debug = True
    server = WSGIServer(("", 5000), app)
    server.serve_forever()
    # Then visit http://localhost:5000 to subscribe
    # and send messages by visiting http://localhost:5000/publish
