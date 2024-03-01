from pathlib import Path

from kafka import KafkaProducer
import os
import time
import json
from minio import Minio
import logging
import os
import kafka.admin

from minio.commonconfig import CopySource

logging.basicConfig(level=logging.INFO)
MINIO_URL = os.getenv("MINIO_URL", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio_user")
MINIO_SECRET = os.getenv("MINIO_SECRET", "minio_password")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

MINIO_BUCKET = os.getenv("MINIO_INPUT_BUCKET", "input")
MINIO_VIDEO_SPLIT_BUCKET = os.getenv("MINIO_VIDEO_SPLIT_BUCKET", "video-split")
MINIO_VIDEO_SPLITTED_BUCKET = os.getenv("MINIO_VIDEO_SPLITTED_BUCKET", "video-splitted")
MINIO_VIDEO_TRANSCODED_BUCKET = os.getenv("MINIO_VIDEO_TRANSCODED_BUCKET", "video-transcoded")
MINIO_VIDEO_CONCATTED_BUCKET = os.getenv("MINIO_VIDEO_CONCATTED_BUCKET", "video-concatted")
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", 'localhost:29092')
VIDEO_SPLIT_TOPIC = os.getenv("VIDEO_SPLIT_TOPIC", 'video-split')
VIDEO_TRANSCODE_TOPIC = os.getenv("VIDEO_TRANSCODE_TOPIC", 'video-transcode')
VIDEO_CONCAT_TOPIC = os.getenv("VIDEO_CONCAT_TOPIC", 'video-concat')
NUMBER_OF_PARTITIONS = os.getenv("NUMBER_OF_PARTITIONS", 4)
MAX_REBALANCE_TIMEOUT = os.getenv("MAX_REBALANCE_TIMEOUT", 600000)


TEMP_FOLDER = Path(os.getenv("TEMP_FOLDER", "../temp"))

SEGMENT_TIME = os.getenv("SEGMENT_TIME", '00:02:00')


minio_client = Minio(MINIO_URL, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET, secure=MINIO_SECURE)
buckets = [MINIO_BUCKET, MINIO_VIDEO_SPLIT_BUCKET, MINIO_VIDEO_SPLITTED_BUCKET, MINIO_VIDEO_TRANSCODED_BUCKET,
           MINIO_VIDEO_CONCATTED_BUCKET]
# create input and video-split buckets
for bucket in buckets:
    if not minio_client.bucket_exists(bucket):
        logger.info('Creating bucket: ' + bucket)
        minio_client.make_bucket(bucket)
    else:
        logger.info('Bucket already exists: ' + bucket)

# create topics

admin_client = kafka.admin.KafkaAdminClient(bootstrap_servers=KAFKA_BROKER, client_id='admin')

topics = [VIDEO_SPLIT_TOPIC, VIDEO_TRANSCODE_TOPIC, VIDEO_CONCAT_TOPIC]

for topic in topics:
    if topic in admin_client.list_topics():
        logger.info(f'Topic {topic} already exists')
        continue
    topic_list = [kafka.admin.NewTopic(name=topic, num_partitions=NUMBER_OF_PARTITIONS, replication_factor=1)]
    admin_client.create_topics(new_topics=topic_list, validate_only=False)
