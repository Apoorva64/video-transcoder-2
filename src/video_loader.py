from kafka import KafkaProducer
import os
import time
import json
from minio import Minio
import logging
import base64

from minio.commonconfig import CopySource

from config import KAFKA_BROKER, MINIO_BUCKET, minio_client, MINIO_VIDEO_SPLIT_BUCKET, VIDEO_SPLIT_TOPIC

logger = logging.getLogger("video-loader")

producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)

# watch input folder for new files
while True:
    objects = minio_client.list_objects(MINIO_BUCKET, recursive=True)
    for obj in objects:
        logger.info('Found file: ' + obj.object_name)
        # move file to video-split bucket
        logger.info('Moving file to video-split bucket: ' + obj.object_name)
        minio_client.copy_object(MINIO_VIDEO_SPLIT_BUCKET, obj.object_name, CopySource(MINIO_BUCKET, obj.object_name))
        logger.info('Deleting file from input bucket: ' + obj.object_name)
        minio_client.remove_object(MINIO_BUCKET, obj.object_name)
        # send message to kafka
        logger.info('Sending message to kafka: ' + obj.object_name)
        producer.send(VIDEO_SPLIT_TOPIC, json.dumps({'filename': obj.object_name,
                                                     'base64': base64.b64encode(
                                                         obj.object_name.encode('utf-8')).decode("utf-8")
                                                     }).encode('utf-8'))
    time.sleep(5)
