from case3.eval.metrics import JudgeMetrics, update_class_metrics


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
