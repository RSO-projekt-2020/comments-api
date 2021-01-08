from flask import *
from flask_cors import CORS
import os
import requests
import datetime
import random
from elasticsearch import Elasticsearch


# logging imports
import logging
from logstash_async.handler import AsynchronousLogstashHandler
from logstash_async.handler import LogstashFormatter


route = '/v1'
app = Flask(__name__)
CORS(app, resources={r"/v1/*": {"origins": "*"}})
# DB settings
app.config['USERS_API_URI'] = 'http://users-api:8080/v1' # environ['USERS_API_URI'] 

app.config['ES_CLOUD_ID'] = os.environ['ES_CLOUD_ID'].strip()
app.config['ES_PASSWD'] = os.environ['ES_PASSWD'].strip()

es = Elasticsearch(cloud_id=app.config['ES_CLOUD_ID'], http_auth=('elastic', app.config['ES_PASSWD']))

# -------------------------------------------
# Logging setup
# -------------------------------------------
# Create the logger and set it's logging level
logger = logging.getLogger("logstash")
logger.setLevel(logging.INFO)        

log_endpoint_uri = str(os.environ["LOGS_URI"]).strip()
log_endpoint_port = int(os.environ["LOGS_PORT"].strip())


# Create the handler
handler = AsynchronousLogstashHandler(
    host=log_endpoint_uri,
    port=log_endpoint_port, 
    ssl_enable=True, 
    ssl_verify=False,
    database_path='')

# Here you can specify additional formatting on your log record/message
formatter = LogstashFormatter()
handler.setFormatter(formatter)

# Assign handler to the logger
logger.addHandler(handler)

# functions
def generate_request_id():
    return ''.join(random.choice(string.ascii_letters) for x in range(10))

# views
@app.route(route + '/videos/<int:video_id>/comments', methods=['GET'])
def get_comments(video_id):
    request_id = None
    if 'X-Request-ID' in request.headers:
        request_id = request.headers.get('X-Request-ID')
    logger.info("[comments-api][{}] getting video comments".format(request_id))
    
    res = es.search(index="comments", body={"query": {"match": {'video_id': video_id}}})
    data = []
    for comment in res['hits']['hits']:
        tmp = comment['_source']
        # we need to get user info
        tmp['user_info'] = requests.get(app.config['USERS_API_URI'] + '/user/{}'.format(tmp['user_id']), headers={'X-Request-ID': request_id}).json()
        data.append(tmp)
    return make_response({'msg': 'ok', 'content': data})


@app.route(route + '/videos/<int:video_id>/comments', methods=['POST'])
def post_comment(video_id):
    request_id = generate_request_id()
    token = request.headers.get('Authorization')
    logger.info("[comments-api][{}] we have one new comment".format(request_id))
    user_id = requests.get(app.config['USERS_API_URI'] + '/user/check', headers={'Authorization': token, 'X-Request-ID': request_id}).json()['user_id']
    
    comment_data = {
        'user_id': user_id,
        'video_id': video_id,
        'comment': request.json['comment'],
        'created_on': str(datetime.datetime.utcnow())
    }

    res = es.index(index='comments', body=comment_data)
    return make_response({'msg': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
