'''
	Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
	SPDX-License-Identifier: MIT-0
'''

import datetime
import os
import greengrasssdk
from threading import Timer
import time
import awscam
import cv2
import random, string
from botocore.session import Session
from threading import Thread

client = greengrasssdk.client('iot-data')

iotTopic = '$aws/things/{}/infer'.format(os.environ['AWS_IOT_THING_NAME'])
bucket_name = '<BUCKET_NAME>'

ret, frame = awscam.getLastFrame()
ret,jpeg = cv2.imencode('.jpg', frame) 
Write_To_FIFO = True
class FIFO_Thread(Thread):
	def __init__(self):
		''' Constructor. '''
		Thread.__init__(self)
 
	def run(self):
		fifo_path = "/tmp/results.mjpeg"
		if not os.path.exists(fifo_path):
			os.mkfifo(fifo_path)
		f = open(fifo_path,'w')
		client.publish(topic=iotTopic, payload="Opened Pipe")
		while Write_To_FIFO:
			try:
				f.write(jpeg.tobytes())
			except IOError as e:
				continue  

def greengrass_infinite_infer_run():
	try:
		modelPath = "/opt/awscam/artifacts/mxnet_deploy_ssd_FP16_FUSED.xml"
		modelType = "ssd"
		input_width = 300
		input_height = 300
		prob_thresh = 0.1
		results_thread = FIFO_Thread()
		results_thread.start()

		# Send a starting message to IoT console
		client.publish(topic=iotTopic, payload="Face detection starts now")

		# Load model to GPU (use {"GPU": 0} for CPU)
		mcfg = {"GPU": 1}
		model = awscam.Model(modelPath, mcfg)
		client.publish(topic=iotTopic, payload="Model loaded")
		ret, frame = awscam.getLastFrame()
		if ret == False:
			raise Exception("Failed to get frame from the stream")
			
		yscale = float(frame.shape[0]/input_height)
		xscale = float(frame.shape[1]/input_width)
		font = cv2.FONT_HERSHEY_SIMPLEX
		rgb_color = (255, 165, 20)
		#Timers for cooldown and countdown
		cooldown = datetime.datetime.now()
		countdown = datetime.datetime.now()
		doInfer = True
		onCountdown = False

		while doInfer:
			# Get a frame from the video stream
			ret, frame = awscam.getLastFrame()
			# Raise an exception if failing to get a frame
			if ret == False:
				raise Exception("Failed to get frame from the stream")

			# Resize frame to fit model input requirement
			frameResize = cv2.resize(frame, (input_width, input_height))
			# Run model inference on the resized frame
			inferOutput = model.doInference(frameResize)
			# Output inference result to the fifo file so it can be viewed with mplayer
			parsed_results = model.parseResult(modelType, inferOutput)['ssd']
			
			label = '{'
			msg = 'false'

			time_now = datetime.datetime.now()

			for obj in parsed_results:
				if (obj['prob'] < prob_thresh):
					break
				xmin = int( xscale * obj['xmin'] ) + int((obj['xmin'] - input_width/2) + input_width/2)
				ymin = int( yscale * obj['ymin'] )
				xmax = int( xscale * obj['xmax'] ) + int((obj['xmax'] - input_width/2) + input_width/2)
				ymax = int( yscale * obj['ymax'] )
				cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), rgb_color, 4)
				label += '"{}": {:.2f},'.format("prob", obj['prob'] )
				label_show = '{}: {:.2f}'.format(str(obj['label']), obj['prob'] )
				cv2.putText(frame, label_show, (xmin, ymin-15), font, 0.5, rgb_color, 4)
				msg = "true" 

				if (time_now >= cooldown) and obj['prob'] >= 0.60:
					# Uploading to Amazon S3 if cooldown and countdown allow it 
					if onCountdown and time_now >= countdown:
						message = "uploading to s3..."
						client.publish(topic=iotTopic, payload = message)

						key = 'images/frame-' + time.strftime("%Y%m%d-%H%M%S") + '.jpg'
						session = Session()
						s3 = session.create_client('s3')

						_, jpg_data = cv2.imencode('.jpg', frame)
						result = s3.put_object(Body=jpg_data.tostring(), Bucket=bucket_name, Key=key)

						message = "uploaded to s3: " + key
						client.publish(topic=iotTopic, payload = message)
						cooldown = time_now + datetime.timedelta(seconds = 10)
						onCountdown = False
					# Starting countdown
					elif not onCountdown:
						onCountdown = True
						countdown = time_now + datetime.timedelta(seconds = 4)

			if not onCountdown:
				cv2.putText(frame, "Wait for picture: " + str(max(0, int((cooldown - time_now).total_seconds()))) + " seconds", (950, 100), font , 2, rgb_color, 4)
				if int((cooldown - time_now).total_seconds()) >= 5 :
					cv2.putText(frame, "Image Uploaded! " , (1150, 200), font, 2, rgb_color, 4)
					cv2.putText(frame, "Please check the leaderboard" , (900, 300), font , 2, rgb_color, 4)
			else:
				if int((countdown - time_now).total_seconds()) >= -5:
					cv2.putText(frame, "Say Cheese!", (1000,1000), font, 3, rgb_color, 4)
					cv2.putText(frame, str(max(0, int((countdown - time_now).total_seconds()))) + "...", (1200,1100), font , 3, rgb_color, 4)
				else:
					onCountdown = False

			label += '"face": "' + msg + '"'
			label += '}'  
			client.publish(topic=iotTopic, payload = label)
			global jpeg
			ret,jpeg = cv2.imencode('.jpg', frame)
			
	except Exception as e:
		msg = "Test failed: " + str(e)
		client.publish(topic=iotTopic, payload=msg)

	# Asynchronously schedule this function to be run again in 15 seconds
	Timer(15, greengrass_infinite_infer_run).start()


# Execute the function above
greengrass_infinite_infer_run()

def function_handler(event, context):
	return
