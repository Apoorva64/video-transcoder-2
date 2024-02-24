import json
import logging
from ffmpeg import FFmpeg, Progress, FFmpegError
from kafka import KafkaConsumer, KafkaProducer
from pathlib import Path

from config import MINIO_VIDEO_SPLIT_BUCKET, minio_client, KAFKA_BROKER, MINIO_VIDEO_SPLITTED_BUCKET, \
    VIDEO_TRANSCODE_TOPIC, TEMP_FOLDER, MAX_REBALANCE_TIMEOUT

VIDEO_SPLIT_FOLDER = TEMP_FOLDER / Path('video-split')

if not VIDEO_SPLIT_FOLDER.exists():
    VIDEO_SPLIT_FOLDER.mkdir()

logger = logging.getLogger("splitter")
# decode json
consumer = KafkaConsumer('video-split', bootstrap_servers=KAFKA_BROKER,
                         value_deserializer=lambda m: json.loads(m.decode('utf-8')), group_id='splitter',
                         max_poll_interval_ms=MAX_REBALANCE_TIMEOUT)
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
for message in consumer:
    filename = message.value['filename']
    base64 = message.value['base64']
    # download file from video-split bucket
    download_path = VIDEO_SPLIT_FOLDER / base64
    minio_client.fget_object(MINIO_VIDEO_SPLIT_BUCKET, filename, download_path)
    logger.info('Downloaded file: ' + filename)

    # create a folder for the video
    output_folder = VIDEO_SPLIT_FOLDER / ("splitted_" + base64)
    output_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created folder: {output_folder}")
    template = str((output_folder / "%04d").with_suffix(Path(filename).suffix))
    # split video
    logger.info('Splitting video: ' + filename)
    # Split video
    ffmpeg = (
        FFmpeg()
        .option('y')
        .input(str(download_path))
        .output(template, {
            'c': 'copy',
            'map': '0',
            'segment_time': '00:10:00',
            'f': 'segment',
            'reset_timestamps': '1',
        })
    )


    @ffmpeg.on("progress")
    def on_progress(progress: Progress):
        logger.info(
            f"Frame: {progress.frame}  - Fps: {progress.fps}")


    @ffmpeg.on("completed")
    def on_completed():
        logger.info("Job Completed !!! 🎉")


    try:
        logger.info("Starting splitting")
        ffmpeg.execute()

    except FFmpegError as e:
        output_folder.unlink()
        # put message back in kafka
        # producer.send('video-split', json.dumps({'filename': filename,
        #                                          'base64': base64
        #                                          }).encode('utf-8'))
        raise e

    logger.info('Uploading files')
    # upload files
    files = list(output_folder.glob("*"))

    for i, file in enumerate(files):
        object_name = base64 + '/' + file.name
        logger.info(f"Uploading file: {file.name} to {object_name}")

        minio_client.fput_object(MINIO_VIDEO_SPLITTED_BUCKET, object_name, file)
        # send message to kafka
        logger.info(f"Sending message to kafka: {file.name}")
        producer.send(VIDEO_TRANSCODE_TOPIC, json.dumps(
            {'filename': filename,
             'base64': base64,
             'file_part': object_name,
             'index': i,
             'total': len(files) - 1
             }).encode('utf-8'),
                      key=object_name.encode('utf-8')
                      )

    # delete folder
    logger.info(f"Deleting folder: {output_folder}")
    for file in files:
        file.unlink()
    output_folder.rmdir()
    # local file
    download_path.unlink()
    logger.info(f"Deleted file: {download_path}")
    # delete file from video-split bucket
    logger.info(f"Deleting file: {filename} from video-split bucket")
    minio_client.remove_object(MINIO_VIDEO_SPLIT_BUCKET, filename)
    logger.info(f"Deleted file: {filename} from video-split bucket")
