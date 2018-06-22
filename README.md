# coffee-leaderboard

This repository is part of a [blog post]() that guides users through creating a coffee leaderboard that uses face detection to track the number of coffee people drink using the [AWS DeepLens](https://aws.amazon.com/deeplens/)

Following the steps described in the [blog post](), the final architecture is this: 

![diagram](../master/diagram.png)

### *face_function.py*

Using Amazon Rekognition, this lambda function responsible for recognising/registering a face and mug, storing the results in DynamoDB


### *deeplens_inference_function.py*

This lambda function runs on the AWS DeepLens and perform inferences and the necessary logic. It uploads frames to Amazon S3 when a face is detected, as well as adds features such as a cooldown period between uploads along with a countdown before taking a picture.


### *app/*

This folder contains a Python Flask application that presents the information collected. Using AWS Elastic Beanstalk, it is easy to deploy this application and visualise the result collected from the AWS DeepLens
