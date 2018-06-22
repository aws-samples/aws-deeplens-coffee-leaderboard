'''
  Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
  
  Licensed under the Apache License, Version 2.0 (the "License").
  You may not use this file except in compliance with the License.
  A copy of the License is located at
  
      http://www.apache.org/licenses/LICENSE-2.0
  
  or in the "license" file accompanying this file. This file is distributed 
  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either 
  express or implied. See the License for the specific language governing 
  permissions and limitations under the License.
'''

import boto3
from flask import Flask, request, render_template
from datetime import datetime
import time

application = Flask(__name__)

client = boto3.client('dynamodb', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
bucket_name = '<BUCKET_NAME>'

@application.route("/")
def main():    
    table_faces = client.scan(TableName = 'faces')
    lastItem = {}
    items, logs = [], []
    lasttime = 0
    for face in table_faces["Items"]:
        item = {}
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': face['pathToImage']['S'],
            },                                  
            ExpiresIn=5
        )

        utime = int(face["unixtime"]["S"])

        item['time'] = datetime.fromtimestamp(utime).strftime('%Y-%m-%d %H:%M:%S')
        item['counter'] = int(face["score"]["S"])
        item['url'] = str(url)

        items.append(item)

        if utime > lasttime:
            lastItem['lasturl'] = str(url)
            lastItem['action'] = "Register" if str(face["score"]["S"]) == "1" else "Added +1"
            lastItem['lasttime'] = item['time']

    table_logs = client.scan(
        TableName = 'logs',
        Select='ALL_ATTRIBUTES',
        ScanFilter = {
            'unixtime': {
                "AttributeValueList": [ {"S": str(time.time() - 24 * 60 * 60) } ],
                "ComparisonOperator": "GT"
            }
        }
    )

    if len(table_logs["Items"]) > 0:
        for i in table_logs["Items"]:
            log = {}
            log['time'] = datetime.fromtimestamp(float(i["unixtime"]["S"])).strftime('%Y-%m-%d %H:%M:%S')
            log['msg'] = i["mymess"]["S"]

            logs.append(log)

        logs = sorted(logs, key=lambda k: k['time'], reverse= True)


    if len(items) > 0:
        items = sorted(items, key=lambda k: k['counter'], reverse=True)
    
    return render_template('main.html', items = items, logs=logs, lastItem = lastItem)

if __name__ == '__main__':
    application.run()
