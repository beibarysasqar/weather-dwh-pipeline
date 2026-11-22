from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

from src.config import PROJECT_ROOT
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
    # a failing test stops the run before any data is loaded
    run_tests = BashOperator(
        task_id="run_tests",
        bash_command="python -m pytest -q",
        cwd=str(PROJECT_ROOT),
        # Airflow 3 blocks the metadata DB in tasks with a fake URL; test_dag.py imports airflow
        env={"AIRFLOW__DATABASE__SQL_ALCHEMY_CONN": "sqlite:////tmp/run_tests_airflow.db"},
        append_env=True,
    )
    extract_task = PythonOperator(
        task_id="extract",
        python_callable=extract_recent,
        # 14 days back from the run date; the overlap with last week is safe because of MERGE
        op_kwargs={"end_date": "{{ dag_run.run_after | ds }}"},
    )
    transform_task = PythonOperator(task_id="transform", python_callable=transform)
    load_staging_task = PythonOperator(task_id="load_staging", python_callable=load_staging_step)
    merge_mart_task = PythonOperator(task_id="merge_mart", python_callable=merge_mart_step)
    check_counts_task = PythonOperator(task_id="check_counts", python_callable=check_counts_step)

    (
        run_tests
        >> extract_task
        >> transform_task
        >> load_staging_task
        >> merge_mart_task
        >> check_counts_task
    )
