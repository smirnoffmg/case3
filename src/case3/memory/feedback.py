"""Accumulate audit findings across iterations."""

from __future__ import annotations

from case3.models import AuditResult, Vulnerability


class FeedbackMemory:
    def __init__(self) -> None:
        self._by_class: dict[str, Vulnerability] = {}
        self._resolved: set[str] = set()
        self._iteration_classes: list[set[str]] = []

    def update(self, audit: AuditResult, iteration: int) -> None:
        current = {v.vuln_class for v in audit.vulnerabilities}
        self._iteration_classes.append(current)
        for v in audit.vulnerabilities:
            self._by_class[v.vuln_class] = v
        # classes not in current iteration are considered resolved for regression tracking
        for cls in list(self._by_class):
            if cls not in current and cls not in self._resolved:
                self._resolved.add(cls)

    def lessons(self) -> list[str]:
        result = []
        for v in self._by_class.values():
            if v.vuln_class in self._resolved:
                result.append(
                    f"⚠️ THIS IS A REPEAT MISTAKE [{v.vuln_class}] "
                    f"You fixed this before but it came back. {v.description}. {v.recommendation}"
                )
            else:
                result.append(f"[{v.vuln_class}] {v.description}. {v.recommendation}")
        return result

    def all_vulnerabilities(self) -> list[Vulnerability]:
        return list(self._by_class.values())

    def detect_regression(self, audit: AuditResult) -> bool:
        """True if a previously resolved vuln class reappears."""
        current = {v.vuln_class for v in audit.vulnerabilities}
        return bool(current & self._resolved)

    def is_stuck(self, min_iterations: int = 2) -> bool:
        """True when the last min_iterations rounds share identical vuln classes."""
        if len(self._iteration_classes) < min_iterations:
            return False
        last = self._iteration_classes[-1]
        return all(c == last for c in self._iteration_classes[-min_iterations:])

    def revision_note(self, audit: AuditResult, iteration: int) -> str:
        if iteration == 1:
            return "Первая генерация."
        n = len(audit.vulnerabilities)
        reg = self.detect_regression(audit)
        base = f"Итерация {iteration}: найдено замечаний: {n}."
        if reg:
            base += " РЕГРЕССИЯ: повтор ранее устранённой ошибки."
        return base
