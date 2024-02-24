from pathlib import Path

from kafka import KafkaProducer
import os
import time
import json
from minio import Minio
import logging

from minio.commonconfig import CopySource

logging.basicConfig(level=logging.INFO)
MINIO_URL = '127.0.0.1:9000'
MINIO_ACCESS_KEY = 'minio_user'
MINIO_SECRET = 'minio_password'
MINIO_SECURE = False
MINIO_BUCKET = 'input'

MINIO_VIDEO_SPLIT_BUCKET = 'video-split'
MINIO_VIDEO_SPLITTED_BUCKET = 'video-splitted'
MINIO_VIDEO_TRANSCODED_BUCKET = 'video-transcoded'
MINIO_VIDEO_CONCAT_BUCKET = 'video-concat'
MINIO_VIDEO_CONCATTED_BUCKET = 'video-concatted'
logger = logging.getLogger(__name__)

KAFKA_BROKER = 'localhost:29092'
VIDEO_SPLIT_TOPIC = 'video-split'
VIDEO_TRANSCODE_TOPIC = 'video-transcode'
VIDEO_CONCAT_TOPIC = 'video-concat'

TEMP_FOLDER = Path('../temp')

minio_client = Minio(MINIO_URL, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET, secure=MINIO_SECURE)
buckets = [MINIO_BUCKET, MINIO_VIDEO_SPLIT_BUCKET, MINIO_VIDEO_SPLITTED_BUCKET, MINIO_VIDEO_TRANSCODED_BUCKET,
           MINIO_VIDEO_CONCAT_BUCKET, MINIO_VIDEO_CONCATTED_BUCKET]
# create input and video-split buckets
for bucket in buckets:
    if not minio_client.bucket_exists(bucket):
        logger.info('Creating bucket: ' + bucket)
        minio_client.make_bucket(bucket)
    else:
        logger.info('Bucket already exists: ' + bucket)
