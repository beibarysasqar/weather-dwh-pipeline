import pytest

pytest.importorskip("airflow")


def test_dag_tasks_run_in_order():
    from dags.weather_dag import dag

    order = ["run_tests", "extract", "transform", "load_staging", "merge_mart", "check_counts"]
    assert sorted(dag.task_ids) == sorted(order)
    for task_id, next_task_id in zip(order, order[1:]):
        assert dag.get_task(task_id).downstream_task_ids == {next_task_id}
