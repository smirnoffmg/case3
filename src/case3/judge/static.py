"""Deterministic SQL vulnerability detectors (sqlglot + regex)."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from case3.judge.sql_validity import analyze_sql_validity
from case3.models import Vulnerability
from case3.schema_index.loader import sensitive_column_set_from_index
from case3.schema_index.parser import SchemaIndex

_DEFAULT_RISKS: dict[str, float] = {
    "SQL_INJ_CLASSIC": 10.0,
    "SQL_INJ_UNION": 9.0,
    "DML_NO_WHERE": 9.0,
    "SELECT_STAR": 5.0,
    "DIRECT_SENSITIVE": 6.0,
    "NO_PAGINATION": 4.0,
    "SQL_INJ_TIME": 8.0,
    "PRIV_ESCALATE": 8.0,
    "PLPGSQL_UNSAFE": 9.0,
}


class StaticAnalyzer:
    def __init__(self, schema_index: SchemaIndex | None = None) -> None:
        self._sensitive: set[str] = (
            sensitive_column_set_from_index(schema_index) if schema_index else set()
        )

    def analyze(self, sql_query: str) -> list[Vulnerability]:
        findings: list[Vulnerability] = []
        sql = sql_query.strip()
        if not sql:
            return findings

        sensitive = self._sensitive
        upper = sql.upper()

        findings.extend(self._check_injection_patterns(sql, upper))
        findings.extend(self._check_dml_no_where(sql))
        findings.extend(self._check_select_star(sql))
        findings.extend(self._check_no_pagination(sql))
        findings.extend(self._check_sensitive(sql, sensitive))
        findings.extend(self._check_execute(sql, upper))
        findings.extend(self._check_priv_escalate(sql, upper))
        findings.extend(analyze_sql_validity(sql))

        return findings

    def _check_injection_patterns(self, sql: str, upper: str) -> list[Vulnerability]:
        out: list[Vulnerability] = []
        if re.search(r"'\s*\|\||\|\|\s*'", sql) or re.search(r"\+\s*'\s*|\s*'\s*\+", sql):
            out.append(
                Vulnerability(
                    vuln_class="SQL_INJ_CLASSIC",
                    risk_score=_DEFAULT_RISKS["SQL_INJ_CLASSIC"],
                    description="Обнаружена конкатенация строк с литералами (риск SQL injection).",
                    recommendation="Используйте параметризованные запросы ($1, $2) вместо конкатенации.",
                )
            )
        if re.search(r"\bUNION\b", upper):
            out.append(
                Vulnerability(
                    vuln_class="SQL_INJ_UNION",
                    risk_score=_DEFAULT_RISKS["SQL_INJ_UNION"],
                    description="Обнаружен UNION, возможна атака типа UNION-based SQL injection.",
                    recommendation="Избегайте UNION в динамически собираемых запросах; используйте параметризованные запросы.",
                )
            )
        if re.search(r"\bPG_SLEEP\s*\(", upper) or re.search(r"\bWAITFOR\s+DELAY\b", upper):
            out.append(
                Vulnerability(
                    vuln_class="SQL_INJ_TIME",
                    risk_score=_DEFAULT_RISKS["SQL_INJ_TIME"],
                    description="Time-based функция (pg_sleep / WAITFOR), blind injection vector.",
                    recommendation="Удалите вызовы задержки из запроса.",
                )
            )
        return out

    def _check_dml_no_where(self, sql: str) -> list[Vulnerability]:
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except sqlglot.errors.ParseError:
            return []
        out: list[Vulnerability] = []
        for node in parsed.walk():
            if isinstance(node, (exp.Update, exp.Delete)) and node.args.get("where") is None:
                out.append(
                    Vulnerability(
                        vuln_class="DML_NO_WHERE",
                        risk_score=_DEFAULT_RISKS["DML_NO_WHERE"],
                        description=f"{node.key.upper()} без WHERE, затронет все строки.",
                        recommendation="Добавьте WHERE с конкретным условием.",
                    )
                )
        return out

    def _check_select_star(self, sql: str) -> list[Vulnerability]:
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except sqlglot.errors.ParseError:
            if re.search(r"SELECT\s+\*", sql, re.I):
                return [
                    Vulnerability(
                        vuln_class="SELECT_STAR",
                        risk_score=_DEFAULT_RISKS["SELECT_STAR"],
                        description="SELECT * избыточен и может раскрыть лишние поля.",
                        recommendation="Перечислите нужные колонки явно.",
                    )
                ]
            return []
        out: list[Vulnerability] = []
        for select in parsed.find_all(exp.Select):
            for proj in select.expressions:
                if isinstance(proj, exp.Star) or (
                    isinstance(proj, exp.Column) and proj.name == "*"
                ):
                    out.append(
                        Vulnerability(
                            vuln_class="SELECT_STAR",
                            risk_score=_DEFAULT_RISKS["SELECT_STAR"],
                            description="SELECT * избыточен и может раскрыть лишние поля.",
                            recommendation="Перечислите нужные колонки явно.",
                        )
                    )
                    break
        return out

    def _check_no_pagination(self, sql: str) -> list[Vulnerability]:
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except sqlglot.errors.ParseError:
            return []
        if not isinstance(parsed, exp.Select) and not parsed.find(exp.Select):
            return []
        if parsed.find(exp.Limit):
            return []
        # allow COUNT-only queries
        if parsed.find(exp.AggFunc):
            return []
        # scalar SELECT (no FROM) — no result set to paginate
        if not parsed.find(exp.From):
            return []
        return [
            Vulnerability(
                vuln_class="NO_PAGINATION",
                risk_score=_DEFAULT_RISKS["NO_PAGINATION"],
                description="SELECT без LIMIT, неограниченный результат.",
                recommendation="Добавьте LIMIT (например LIMIT 100).",
            )
        ]

    def _check_sensitive(self, sql: str, sensitive: set[str]) -> list[Vulnerability]:
        if not sensitive:
            return []
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except sqlglot.errors.ParseError:
            return []
        out: list[Vulnerability] = []
        seen: set[str] = set()
        for col in parsed.find_all(exp.Column):
            col_name = col.name.lower()
            table_name = (col.table or "").lower() if col.table else ""
            for s in sensitive:
                s_low = s.lower()
                if "." not in s_low:
                    continue
                s_table, s_col = s_low.rsplit(".", 1)
                if col_name != s_col:
                    continue
                if table_name and table_name != s_table:
                    continue
                if s_low in seen:
                    break
                seen.add(s_low)
                out.append(
                    Vulnerability(
                        vuln_class="DIRECT_SENSITIVE",
                        risk_score=_DEFAULT_RISKS["DIRECT_SENSITIVE"],
                        description=f"Запрос обращается к чувствительному полю: {s}.",
                        recommendation="Замените чувствительное поле фиксированной маской: '***' AS column_name. Не используйте current_setting() или условную логику по ролям.",
                    )
                )
                break
        return out

    def _check_execute(self, sql: str, upper: str) -> list[Vulnerability]:
        out: list[Vulnerability] = []
        if not re.search(r"\bEXECUTE\b", upper):
            return out
        is_format = re.search(r"EXECUTE\s+format\s*\(", upper, re.I) and "USING" not in upper
        # EXECUTE 'literal' || var  — concatenation inside dynamic SQL
        is_concat = re.search(r"EXECUTE\b[^;]*\|\|", upper, re.I)
        if is_format or is_concat:
            out.append(
                Vulnerability(
                    vuln_class="PLPGSQL_UNSAFE",
                    risk_score=_DEFAULT_RISKS["PLPGSQL_UNSAFE"],
                    description="Динамический SQL в PL/pgSQL без USING-параметров (format/конкатенация).",
                    recommendation="Используйте EXECUTE ... USING $1 или format(%L, val) с %L/%I.",
                )
            )
        else:
            out.append(
                Vulnerability(
                    vuln_class="PRIV_ESCALATE",
                    risk_score=_DEFAULT_RISKS["PRIV_ESCALATE"],
                    description="Динамический EXECUTE, риск privilege escalation.",
                    recommendation="Избегайте динамического EXECUTE или ограничьте права.",
                )
            )
        return out

    def _check_priv_escalate(self, sql: str, upper: str) -> list[Vulnerability]:
        if not re.search(
            r"\b(GRANT|REVOKE|ALTER\s+ROLE|ALTER\s+USER|SET\s+ROLE|CREATE\s+ROLE)\b", upper
        ):
            return []
        return [
            Vulnerability(
                vuln_class="PRIV_ESCALATE",
                risk_score=_DEFAULT_RISKS["PRIV_ESCALATE"],
                description="DDL по правам (GRANT/REVOKE/ALTER ROLE) — попытка изменить привилегии.",
                recommendation="Управление правами должно быть вне рантайма приложения.",
            )
        ]
