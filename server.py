# author: oskar.blom@gmail.com
#
# Make sure your gevent version is >= 1.0
import gevent
from gevent.wsgi import WSGIServer
from gevent.queue import Queue

from flask import Flask, Response, request

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
    debug_template = """
     <html>
       <head>
       <link rel="stylesheet" href="static/style.css">
       </head>
       <body>
         <h1>Server sent events</h1>
         <div id="event"></div>
         <script type="text/javascript">
         var data = {};
         var eventOutputContainer = document.getElementById("event");
         var evtSrc = new EventSource("/subscribe");

         evtSrc.onmessage = function(e) {
             console.log(e.data);
             data = JSON.parse(e.data);
             for (i = 0; i < data.length; i++) {
                var update = data[i];
                var field = document.getElementById(update.id);
                if (field != null) {
                    console.log(update.id);
                    field.getElementsByClassName("value")[0].innerHTML = update.value;
                };
             };

             //eventOutputContainer.innerHTML = e.data;
         };

         </script>

         <table>
         <tr class="value_display id="time">
             <td><span class="description">Time </span></td>
             <td><span class="value">-</span></td>
         </tr>
         <tr class="value_display id="random number">
             <td><span class="description">Random number </span></td>
             <td><span class="value">-</span></td>
         </tr>
         <tr class="value_display id="iteration">
             <td><span class="description">Iteration </span></td>
             <td><span class="value">-</span></td>
         </tr>
         </table>


       </body>
     </html>
    """
    return(debug_template)


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
        msg = json.dumps(list(datadict.values()))
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
