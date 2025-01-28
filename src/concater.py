import json
import logging

import ffmpeg
from ffmpeg import FFmpeg
from kafka import KafkaConsumer

from config import (
    KAFKA_BROKER,
    MAX_REBALANCE_TIMEOUT,
    MINIO_VIDEO_CONCATTED_BUCKET,
    MINIO_VIDEO_TRANSCODED_BUCKET,
    TEMP_FOLDER,
    VIDEO_CONCAT_TOPIC,
    minio_client,
)

consumer = KafkaConsumer(
    VIDEO_CONCAT_TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    group_id="concater",
    max_poll_interval_ms=MAX_REBALANCE_TIMEOUT,
)

logger = logging.getLogger("concater")

CONCAT_TEMP_FOLDER = TEMP_FOLDER / "concat"
CONCAT_TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

for message in consumer:
    filename = message.value["filename"]
    file_part = message.value["file_part"]
    base64 = message.value["base64"]
    index = message.value["index"]
    total = message.value["total"]
    logger.info(f"Received file part: {file_part}")
    logger.info(f"Index: {index}")
    logger.info(f"Total: {total}")
    logger.info(f"Base64: {base64}")
    logger.info(f"Filename: {filename}")

    # Concatenate video
    logger.info("Concatenating video")

    # Concatenate video
    concat_list_file = CONCAT_TEMP_FOLDER / f"concat_list{base64}.txt"
    with open(concat_list_file, "w") as f:
        # get all files from minio transcode bucket
        for file in list(
            minio_client.list_objects(
                MINIO_VIDEO_TRANSCODED_BUCKET, prefix=base64, recursive=True
            )
        ):
            if not file.is_dir:
                logger.info(f"Downloading file: {file.object_name}")
                minio_client.fget_object(
                    MINIO_VIDEO_TRANSCODED_BUCKET,
                    file.object_name,
                    CONCAT_TEMP_FOLDER / file.object_name,
                )
                logger.info(f"Downloaded file: {file.object_name}")
                f.write(
                    f"file '{(CONCAT_TEMP_FOLDER / file.object_name).absolute()}'\n"
                )

    # Concat files
    output_file = CONCAT_TEMP_FOLDER / f"{base64}_concat.mkv"
    ffmpeg = (
        FFmpeg()
        .option("y")
        .option("f", "concat")
        .option("safe", "0")
        .input(concat_list_file)
        .output(
            output_file,
            {
                "c": "copy",
            },
        )
    )

    @ffmpeg.on("progress")
    def on_progress(progress):
        logger.info(f"Frame: {progress.frame}  - Fps: {progress.fps}")

    @ffmpeg.on("completed")
    def on_completed():
        logger.info("Job Completed !!! 🎉")

    # minio object name
    object_name = f"{filename}"
    if (
        len(
            list(
                minio_client.list_objects(
                    MINIO_VIDEO_CONCATTED_BUCKET, prefix=object_name
                )
            )
        )
        == 0
    ):
        try:
            logger.info("Starting concatenation")
            ffmpeg.execute()
        except Exception as e:
            logger.error(e)

            raise e

        minio_client.fput_object(MINIO_VIDEO_CONCATTED_BUCKET, object_name, output_file)
        logger.info(f"Uploaded file: {object_name}")

    # delete "base64" folder
    for file in minio_client.list_objects(
        MINIO_VIDEO_TRANSCODED_BUCKET, prefix=base64, recursive=True
    ):
        if not file.is_dir:
            minio_client.remove_object(MINIO_VIDEO_TRANSCODED_BUCKET, file.object_name)
    logger.info(f"Deleted folder: {base64}")
    # delete concat_list file
    concat_list_file.unlink(missing_ok=True)
    # delete output file
    output_file.unlink(missing_ok=True)
    logger.info(f"Deleted file: {output_file}")
    # delete "base64" folder in temp folder
    for file in (CONCAT_TEMP_FOLDER / base64).glob("*"):
        file.unlink(missing_ok=True)

    if (CONCAT_TEMP_FOLDER / base64).is_dir():
        (CONCAT_TEMP_FOLDER / base64).rmdir()
