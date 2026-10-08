# The two small data servers (Tennessee Eastman replay and the mapped demo points), packaged so the Docker demo
# needs no Python on the host. Built by docker-compose.yml; see docker/README.md.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir asyncua==2.1.0
COPY data/te_process_model.json data/te_process_model.json
COPY data/io_lists data/io_lists
COPY scripts/fetch_te_data.py scripts/fetch_te_data.py
COPY scripts/ignition/te_sim_server.py scripts/ignition/te_sim_server.py
COPY scripts/ignition/demo_points_server.py scripts/ignition/demo_points_server.py
# The open TE runs, downloaded and checked against their recorded checksums when the image is built.
RUN python scripts/fetch_te_data.py
