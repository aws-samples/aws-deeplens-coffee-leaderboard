'''
        Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
        SPDX-License-Identifier: MIT-0
'''

import boto3
import time

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
rekognition = boto3.client('rekognition')


face_collection = "Faces" # Name of the face collection that the AWS Rekognition uses
face_match_threshold = 70 # Match Threshold for the faces to be concidered the same person
logging_table = 'logs' # DynamoDB table name for the log files



def lambda_handler(event, context):

    utime = str(int(time.time())) #Current Unix Time   
    coffee_cup_detected = False  
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']  
    image = {
        'S3Object': {
            'Bucket': bucket,
            'Name': key,
            }
        }
    response = rekognition.detect_labels(Image=image, MaxLabels=123, MinConfidence=50)    
    for object in response["Labels"]:
        if object["Name"] == "Coffee Cup" or object["Name"] == "Cup":
            coffee_cup_detected = True
            break        
    if coffee_cup_detected:
        dynamodb.put_item(
            TableName=logging_table,
            Item={
                'unixtime':{'S':utime},
                'mymess':{'S': "Coffee Cup Detected"}
            })
        message = detect_faces(image, bucket, key)
    else:
        dynamodb.put_item(
            TableName=logging_table,
            Item={
                'unixtime':{'S':utime},
                'mymess':{'S': "Coffee Cup Not Found in the image"}
                })
        return 'Coffee Cup Not Found in the image'        
    return message

def detect_faces(image, bucket, key):

    # Checks if user face is already registered in rekongtion collection
    faces = rekognition.search_faces_by_image(CollectionId=face_collection, Image=image,
                                              FaceMatchThreshold=face_match_threshold, MaxFaces=1)
    utime = int(time.time()) # Current Unix Time
    time_5_minutes_ago = int(utime) - 300

    if len(faces['FaceMatches']) == 1:  # User is already registered in the collection
        # Authenticate
        faceid = faces['FaceMatches'][0]['Face']['FaceId']
        item = dynamodb.get_item(TableName='faces', Key={'faceID': {'S': str(faceid)}})

        # Gets the item
        item = item['Item']
        face_id = item['faceID']['S']
        score = int(item['score']['S'])
        unixtime = int(item['unixtime']['S'])
        new_score = str(score + 1)
        
        #Checks if 5 minutes passed since the last upload
        if unixtime < time_5_minutes_ago:
            dynamodb.update_item(TableName='faces', Key={'faceID': {'S': str(face_id)}},
                                 UpdateExpression="set score = :val, unixtime =:val2, s3Bucket = :val3, pathToImage = :val4",
                                 ExpressionAttributeValues={
                                     ':val': {'S': new_score},
                                     ':val2': {'S': str(utime)},
                                     ':val3': {'S': bucket},
                                     ':val4': {'S': key}
                                 })
            dynamodb.put_item(
                TableName=logging_table,
                Item={
                    'unixtime': {'S': str(utime)},
                    'mymess': {'S': 'User Score increased to ' + new_score}
                })
            return 'User Score increased to ' + new_score
        else:
            dynamodb.put_item(
                TableName=logging_table,
                Item={
                    'unixtime': {'S': str(utime)},
                    'mymess': {'S': 'Sorry, you can only participate every 5 minutes.'}
                })
            return 'You can only participate every 5 minutes'
    else:
        # Face not found in the Rekognition database
        faces = rekognition.index_faces(Image=image, CollectionId=face_collection)

        # Check if there are no faces in the image:
        if len(faces['FaceRecords']) == 0:
            dynamodb.put_item( 
                TableName=logging_table,
                Item={
                    'unixtime': {'S': str(utime)},
                    'mymess': {'S': "No faces were found in the picture"}
                })
            return 'No faces found in the image'

        # More than one face in the image:
        elif len(faces['FaceRecords']) > 1:
            rekognition.delete_faces(CollectionId=face_collection,
                                     FaceIds=[f['Face']['FaceId'] for f in faces['FaceRecords']])

            dynamodb.put_item(
                TableName=logging_table,
                Item={
                    'unixtime': {'S': str(utime)},
                    'mymess': {'S': "Error: More than one face detected in the image"}
                })

            return 'More than one face in the image'

        # One new face in the image, register it:
        else:
            face_id = faces['FaceRecords'][0]['Face']['FaceId']
            dynamodb.put_item(
                TableName='faces',
                Item={
                    'faceID': {'S': face_id},
                    'score': {'S': '1'},
                    'unixtime': {'S': str(utime)},
                    's3Bucket': {'S': bucket},
                    'pathToImage': {'S': key}
                })

            dynamodb.put_item(
                TableName=logging_table,
                Item={
                    'unixtime': {'S': str(utime)},
                    'mymess': {'S': "Congratulations! You're now registered for the coffee leaderboard."}
                })

            return "Congratulations! You're now registered for the coffee leaderboard."
