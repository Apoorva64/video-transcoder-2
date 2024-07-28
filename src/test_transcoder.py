from unittest import TestCase

from transcoder import configure_ffmpeg
import pathlib

class Test(TestCase):
    def test_configure_ffmpeg(self):
        ffmpeg = configure_ffmpeg(pathlib.Path('../test-video/The Office (US) - S05E26 - Company Picnic.mkv'),
                                pathlib.Path('../test-video/The Office (US) - S05E26 - Company Picnic2.mkv'))

        @ffmpeg.on("progress")
        def on_progress(progress):
            print(
                f"Frame: {progress.frame}  - Fps: {progress.fps}")

        @ffmpeg.on("completed")
        def on_completed():
            print("Job Completed !!! 🎉")

        ffmpeg.execute()
