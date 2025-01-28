# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/engine/reference/builder/

FROM nvidia/cuda:12.2.0-devel-ubuntu22.04  as base

# install python 3.10
RUN apt-get update && apt-get install -y python3.10 python3-pip

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python3 -m pip install -r requirements.txt

RUN mkdir /data

# give permissions to the appuser
RUN chown -R appuser:appuser /app
RUN chown -R appuser:appuser /data


## install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg
    build-essential yasm cmake libtool libc6 libc6-dev unzip wget libnuma1 libnuma-dev git nasm
RUN apt-get update && apt install nvidia-cuda-toolkit -y
#RUN mkdir ~/nvidia/ && cd ~/nvidia/
#RUN git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git
#RUN cd nv-codec-headers && make install
#RUN cd ~/nvidia/ && git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg/
#RUN apt-get update && apt-get install -y libx264-dev libx265-dev libvpx-dev libfdk-aac-dev libmp3lame-dev libopus-dev libvorbis-dev libaom-dev libass-dev libfreetype6-dev libgnutls28-dev
#RUN cd ~/nvidia/ffmpeg/ && ./configure --enable-nonfree --enable-cuda-nvcc --enable-libnpp --extra-cflags=-I/usr/local/cuda/include --extra-ldflags=-L/usr/local/cuda/lib64 --enable-gpl \
#--enable-gnutls \
#--enable-libaom \
#--enable-libass \
#--enable-libfdk-aac \
#--enable-libfreetype \
#--enable-libmp3lame \
#--enable-libopus \
#--enable-libvorbis \
#--enable-libvpx \
#--enable-libx264 \
#--enable-libx265 \
#--enable-nonfree
#
#RUN cd ~/nvidia/ffmpeg/ && make -j $(nproc)
#RUN cd ~/nvidia/ffmpeg/ && make install
#RUN export PATH=$PATH:/usr/local/bin
# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.
COPY . .

# Run the application.
CMD python3 concater.py
