FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/portbug
RUN groupadd --gid 10001 portbug && useradd --uid 10001 --gid portbug --no-create-home portbug \
    && mkdir /data && chown portbug:portbug /data
COPY --chown=portbug:portbug portbug ./portbug
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "portbug", "--host", "0.0.0.0", "--data-dir", "/data"]
