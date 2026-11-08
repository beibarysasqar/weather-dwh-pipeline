FROM apache/airflow:3.3.2-python3.11

# Keep Airflow at its version and install our pinned dependencies next to it.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==3.3.2" -r /requirements.txt

COPY --chown=airflow:root . /opt/airflow/project
ENV PYTHONPATH=/opt/airflow/project
