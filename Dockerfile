FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /mlang
COPY . .
ENTRYPOINT ["python3", "mlang/cli.py"]
CMD ["version"]
