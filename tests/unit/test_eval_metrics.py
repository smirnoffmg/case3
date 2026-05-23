from case3.eval.metrics import JudgeMetrics, sql_match, update_class_metrics


def test_true_positive_recorded_per_class():
    by_class: dict[str, JudgeMetrics] = {}
    update_class_metrics({"SQL_INJ_UNION", "NO_PAGINATION"}, {"SQL_INJ_UNION"}, by_class)
    assert by_class["SQL_INJ_UNION"].true_positives == 1
    assert by_class["SQL_INJ_UNION"].false_positives == 0
    assert by_class["SQL_INJ_UNION"].false_negatives == 0


def test_false_positive_recorded_per_class():
    by_class: dict[str, JudgeMetrics] = {}
    update_class_metrics({"NO_PAGINATION"}, set(), by_class)
    assert by_class["NO_PAGINATION"].false_positives == 1
    assert by_class["NO_PAGINATION"].true_positives == 0


def test_false_negative_recorded_per_class():
    by_class: dict[str, JudgeMetrics] = {}
    update_class_metrics(set(), {"DML_NO_WHERE"}, by_class)
    assert by_class["DML_NO_WHERE"].false_negatives == 1
    assert by_class["DML_NO_WHERE"].true_positives == 0


def test_accumulates_across_calls():
    by_class: dict[str, JudgeMetrics] = {}
    update_class_metrics({"SQL_INJ_UNION"}, {"SQL_INJ_UNION"}, by_class)
    update_class_metrics({"SQL_INJ_UNION"}, {"SQL_INJ_UNION"}, by_class)
    assert by_class["SQL_INJ_UNION"].true_positives == 2


def test_precision_and_recall_per_class():
    by_class: dict[str, JudgeMetrics] = {}
    update_class_metrics({"SQL_INJ_UNION"}, {"SQL_INJ_UNION"}, by_class)  # TP
    update_class_metrics({"SQL_INJ_UNION"}, set(), by_class)  # FP
    update_class_metrics(set(), {"SQL_INJ_UNION"}, by_class)  # FN
    m = by_class["SQL_INJ_UNION"]
    assert m.precision == 0.5  # 1 TP / (1 TP + 1 FP)
    assert m.recall == 0.5  # 1 TP / (1 TP + 1 FN)


def test_sql_match_exact():
    assert sql_match(
        "SELECT id FROM public.sys_employee WHERE status = 1 LIMIT 10;",
        "SELECT id FROM public.sys_employee WHERE status = 1 LIMIT 10;",
    )


def test_sql_match_whitespace_and_case_insensitive():
    assert sql_match(
        "select  id  from   public.sys_employee   limit 5",
        "SELECT id FROM public.sys_employee LIMIT 5;",
    )


def test_sql_match_ignores_projection_alias():
    # COUNT(*) AS cnt is semantically identical to COUNT(*).
    assert sql_match(
        "SELECT COUNT(*) FROM public.acc_number;",
        "SELECT COUNT(*) AS cnt FROM public.acc_number;",
    )


def test_sql_match_ignores_offset_zero():
    assert sql_match(
        "SELECT id FROM public.sys_employee LIMIT 20 OFFSET 0;",
        "SELECT id FROM public.sys_employee LIMIT 20;",
    )


def test_sql_match_ignores_different_limit():
    # LIMIT is an editorial choice in gold; audited separately by NO_PAGINATION.
    assert sql_match(
        "SELECT id FROM public.sys_employee LIMIT 10;",
        "SELECT id FROM public.sys_employee LIMIT 100;",
    )


def test_sql_match_ignores_limit_vs_no_limit():
    assert sql_match(
        "SELECT id FROM public.sys_employee LIMIT 100;",
        "SELECT id FROM public.sys_employee;",
    )


def test_sql_match_rejects_hallucinated_where():
    # Real generator failure mode: adds invented filters not in the gold.
    assert not sql_match(
        "SELECT id, name FROM public.sys_company WHERE id IN (1, 2) LIMIT 20;",
        "SELECT id, name FROM public.sys_company WHERE status = 1 LIMIT 20;",
    )


def test_sql_match_rejects_extra_column():
    assert not sql_match(
        "SELECT id, name__ru, last_modified_date FROM public.acc_number LIMIT 10;",
        "SELECT id, last_modified_date FROM public.acc_number LIMIT 10;",
    )


def test_sql_match_ignores_order_by():
    assert sql_match(
        "SELECT id, name FROM public.sys_company ORDER BY name;",
        "SELECT id, name FROM public.sys_company;",
    )


def test_sql_match_ignores_different_order_by():
    assert sql_match(
        "SELECT id, create_date FROM public.acc_number ORDER BY last_modified_date DESC;",
        "SELECT id, create_date FROM public.acc_number ORDER BY create_date DESC;",
    )


def test_sql_match_ignores_order_by_with_limit():
    # Both LIMIT and ORDER BY are stripped before comparison.
    assert sql_match(
        "SELECT id FROM public.sys_employee ORDER BY id LIMIT 10;",
        "SELECT id FROM public.sys_employee LIMIT 20;",
    )


def test_sql_match_handles_unparseable_refusal_comment():
    # The pipeline emits SQL comments when the task is non-actionable.
    assert not sql_match(
        "-- Отказ: задача не является запросом к данным.",
        "SELECT id FROM public.sys_employee LIMIT 10;",
    )
