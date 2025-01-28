import json
import logging
from pathlib import Path

import GPUtil
from ffmpeg import FFmpeg, FFmpegInvalidCommand
from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger("transcoder")

GPU = False

if GPUtil.getAvailable():
    GPU = True


def configure_ffmpeg(
    _download_path: Path,
    _output_file_path: Path,
):
    ffmpeg = (
        FFmpeg()
        .option("y")
        .input(str(_download_path))
        .output(
            _output_file_path,
            {
                "c:v": "libx264",
                "preset": "medium",
                "crf": "23",
                "c:a": "aac",
                "b:a": "192k",
                "c:s": "srt",
                "movflags": "+faststart",
            },
        )
    )
    if GPU:
        ffmpeg = ffmpeg.option("hwaccel", "cuda").output(
            _output_file_path,
            {
                "c:v": "h264_nvenc",
                "c:a": "aac",
                "c:s": "copy",
                "ac": "3",
                "pix_fmt": "yuv420p",
                "map": "0",
                "vsync": "0",
                "threads": "1",
                "rc": "vbr_hq",
                "rc_lookahead": "32",
                "refs:v": "16",
                "bf:v": "3",
                "coder:v": "cabac",
                "b_ref_mode": "middle",
            },
        )
    return ffmpeg


if __name__ == "__main__":
    from config import (
        KAFKA_BROKER,
        MAX_REBALANCE_TIMEOUT,
        MINIO_VIDEO_SPLITTED_BUCKET,
        MINIO_VIDEO_TRANSCODED_BUCKET,
        TEMP_FOLDER,
        VIDEO_CONCAT_TOPIC,
        VIDEO_TRANSCODE_TOPIC,
        minio_client,
    )

    VIDEO_TRANSCODE_TEMP_FOLDER = TEMP_FOLDER / Path("transcoded")
    VIDEO_TRANSCODE_TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
    consumer = KafkaConsumer(
        VIDEO_TRANSCODE_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="transcoder",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        max_poll_records=1,
        max_poll_interval_ms=MAX_REBALANCE_TIMEOUT,
    )
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)

    for message in consumer:
        filename = message.value["filename"]
        file_part = message.value["file_part"]
        base64 = message.value["base64"]
        index = message.value["index"]
        total = message.value["total"]
        # download file from video-split bucket
        download_path = VIDEO_TRANSCODE_TEMP_FOLDER / file_part
        output_file_path = (
            VIDEO_TRANSCODE_TEMP_FOLDER / f"{base64}_transcoded_{index}.mkv"
        )
        minio_client.fget_object(MINIO_VIDEO_SPLITTED_BUCKET, file_part, download_path)
        # transcode video
        logger.info("Transcoding video: " + filename)

        # Convert file
        ffmpeg = configure_ffmpeg(download_path, output_file_path)
        # minio object name
        object_name = f"{base64}/transcoded_{index:010}.mkv"

        @ffmpeg.on("progress")
        def on_progress(progress):
            logger.info(f"Frame: {progress.frame}  - Fps: {progress.fps}")

        @ffmpeg.on("completed")
        def on_completed():
            logger.info("Job Completed !!! 🎉")

        if (
            minio_client.bucket_exists(MINIO_VIDEO_TRANSCODED_BUCKET)
            and len(
                list(
                    minio_client.list_objects(
                        MINIO_VIDEO_TRANSCODED_BUCKET, prefix=object_name
                    )
                )
            )
            == 0
        ):
            try:
                ffmpeg.execute()
            except FFmpegInvalidCommand as e:
                logger.error("An exception has occurred!")
                logger.error(f"- Message from ffmpeg: {e.message}")
                logger.error(f"- Arguments to execute ffmpeg: {e.arguments}")
            except Exception as e:
                logger.error(e)
                raise e
            minio_client.fput_object(
                MINIO_VIDEO_TRANSCODED_BUCKET, object_name, output_file_path
            )
        else:
            logger.info(f"Object {object_name} already exists")
        # send message to kafka if all parts are transcoded
        # check the parts in the minio folder in the bucket
        parts = [
            obj
            for obj in list(
                minio_client.list_objects(
                    MINIO_VIDEO_TRANSCODED_BUCKET, base64, recursive=True
                )
            )
            if obj.is_dir is False
        ]
        if len(parts) == total + 1:
            logger.info(f"All parts transcoded for {filename} sending message to kafka")
            producer.send(
                VIDEO_CONCAT_TOPIC,
                json.dumps(
                    {
                        "filename": filename,
                        "base64": base64,
                        "index": index,
                        "file_part": file_part,
                        "transcoded_part": object_name,
                        "total": total,
                    }
                ).encode("utf-8"),
            )
        # remove downloaded file
        minio_client.remove_object(MINIO_VIDEO_SPLITTED_BUCKET, file_part)
        # remove transcoded file
        output_file_path.unlink(missing_ok=True)
        # remove downloaded file
        download_path.unlink(missing_ok=True)
