"""Weekly weather ETL. Only calls functions from src/ - no business logic here."""
from datetime import datetime

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

from src.pipeline import (
    check_counts_step,
    extract_recent,
    load_staging_step,
    merge_mart_step,
    transform,
)

with DAG(
    dag_id="weather_weekly",
    schedule="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,  # DuckDB allows one writer, and runs share the work CSV files
    tags=["weather"],
) as dag:
    extract_task = PythonOperator(
        task_id="extract",
        python_callable=extract_recent,
        # Load the 14 days before the run date (overlap is safe: MERGE is idempotent).
        op_kwargs={"end_date": "{{ dag_run.run_after | ds }}"},
    )
    transform_task = PythonOperator(task_id="transform", python_callable=transform)
    load_staging_task = PythonOperator(task_id="load_staging", python_callable=load_staging_step)
    merge_mart_task = PythonOperator(task_id="merge_mart", python_callable=merge_mart_step)
    check_counts_task = PythonOperator(task_id="check_counts", python_callable=check_counts_step)

    extract_task >> transform_task >> load_staging_task >> merge_mart_task >> check_counts_task
