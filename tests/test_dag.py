"""DAG structure test. Needs Airflow, so it runs inside Docker and is skipped elsewhere."""
import pytest

pytest.importorskip("airflow")


def test_dag_loads_with_tasks_in_order():
    from dags.weather_dag import dag

    order = ["extract", "transform", "load_staging", "merge_mart", "check_counts"]
    assert dag.dag_id == "weather_weekly"
    assert sorted(dag.task_ids) == sorted(order)
    for task_id, next_task_id in zip(order, order[1:]):
        assert dag.get_task(task_id).downstream_task_ids == {next_task_id}
