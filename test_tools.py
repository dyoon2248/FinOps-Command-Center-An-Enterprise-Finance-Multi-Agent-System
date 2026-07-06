"""Unit tests for FinOps agent tools.

Run with:
    python -m pytest tests/test_tools.py -v
"""

from __future__ import annotations

import pytest

from finops_agent.tools.db import get_db, FinanceDB
from finops_agent.tools.expense_tools import (
    add_expense,
    list_expenses,
    get_spending_by_category,
    get_spending_by_department,
)
from finops_agent.tools.budget_tools import (
    set_budget,
    check_budget_status,
    forecast_spending,
    get_budget_alerts,
)
from finops_agent.tools.invoice_tools import (
    list_pending_invoices,
    validate_invoice,
    approve_invoice,
    parse_invoice,
)
from finops_agent.tools.reporting_tools import (
    generate_expense_report,
    generate_budget_report,
    get_financial_summary,
)


# ---------------------------------------------------------------------------
# FinanceDB Tests
# ---------------------------------------------------------------------------

class TestFinanceDB:
    """Tests for the in-memory data store singleton."""

    def test_singleton_returns_same_instance(self):
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2

    def test_instance_is_finance_db(self):
        db = get_db()
        assert isinstance(db, FinanceDB)

    def test_has_expense_data(self):
        db = get_db()
        assert len(db.expenses) > 0

    def test_has_invoice_data(self):
        db = get_db()
        assert len(db.invoices) > 0

    def test_has_budget_data(self):
        db = get_db()
        assert len(db.budgets) > 0

    def test_next_expense_id_increments(self):
        db = get_db()
        id1 = db.next_expense_id()
        id2 = db.next_expense_id()
        assert id1 != id2
        assert id1.startswith("EXP-")
        assert id2.startswith("EXP-")

    def test_next_invoice_id_increments(self):
        db = get_db()
        id1 = db.next_invoice_id()
        id2 = db.next_invoice_id()
        assert id1 != id2
        assert id1.startswith("INV-")

    def test_get_expenses_unfiltered(self):
        db = get_db()
        results = db.get_expenses()
        assert len(results) > 0

    def test_get_expenses_by_category(self):
        db = get_db()
        results = db.get_expenses(category="Travel")
        for exp in results:
            assert exp["category"].lower() == "travel"

    def test_get_expenses_by_status(self):
        db = get_db()
        results = db.get_expenses(status="approved")
        for exp in results:
            assert exp["status"].lower() == "approved"

    def test_get_invoices_unfiltered(self):
        db = get_db()
        results = db.get_invoices()
        assert len(results) > 0

    def test_get_invoices_by_status(self):
        db = get_db()
        results = db.get_invoices(status="pending")
        for inv in results:
            assert inv["status"].lower() == "pending"

    def test_get_budgets_unfiltered(self):
        db = get_db()
        results = db.get_budgets()
        assert len(results) > 0

    def test_add_expense_record(self):
        db = get_db()
        initial_count = len(db.expenses)
        new_exp = db.add_expense({
            "description": "Test expense for unit test",
            "amount": 42.00,
            "category": "Software",
            "date": "2026-07-04",
            "employee": "Test User",
            "department": "Engineering",
        })
        assert new_exp["id"].startswith("EXP-")
        assert new_exp["status"] == "pending"
        assert len(db.expenses) == initial_count + 1


# ---------------------------------------------------------------------------
# Expense Tools Tests
# ---------------------------------------------------------------------------

class TestExpenseTools:
    """Tests for expense tool functions."""

    def test_add_expense_returns_success(self):
        result = add_expense(
            "Pytest item",
            99.99,
            "Software",
            "2026-07-04",
            "Test User",
            "Engineering",
        )
        assert isinstance(result, dict)
        assert result.get("status") == "success"
        assert "expense" in result

    def test_add_expense_creates_record(self):
        result = add_expense(
            "Another test",
            50.00,
            "Travel",
            "2026-07-04",
            "Jane",
            "Sales",
        )
        assert result["expense"]["amount"] == 50.00

    def test_list_expenses_returns_string(self):
        result = list_expenses()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_expenses_with_category_filter(self):
        result = list_expenses(category="Software")
        assert isinstance(result, str)

    def test_list_expenses_with_department_filter(self):
        result = list_expenses(department="Engineering")
        assert isinstance(result, str)

    def test_list_expenses_with_status_filter(self):
        result = list_expenses(status="approved")
        assert isinstance(result, str)

    def test_spending_by_category_returns_string(self):
        result = get_spending_by_category()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_spending_by_category_has_dollar_sign(self):
        result = get_spending_by_category()
        assert "$" in result

    def test_spending_by_department_returns_string(self):
        result = get_spending_by_department()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Budget Tools Tests
# ---------------------------------------------------------------------------

class TestBudgetTools:
    """Tests for budget tool functions."""

    def test_check_budget_status_all(self):
        result = check_budget_status()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_check_budget_status_specific_category(self):
        result = check_budget_status(category="Travel")
        assert isinstance(result, str)

    def test_get_budget_alerts(self):
        result = get_budget_alerts()
        assert isinstance(result, str)

    def test_set_budget(self):
        result = set_budget("Test Category", 10000.0, "Engineering", "Q3 2026")
        assert isinstance(result, str)

    def test_forecast_spending(self):
        result = forecast_spending("Travel", 3)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Invoice Tools Tests
# ---------------------------------------------------------------------------

class TestInvoiceTools:
    """Tests for invoice tool functions."""

    def test_list_pending_invoices(self):
        result = list_pending_invoices()
        assert isinstance(result, str)

    def test_parse_invoice_from_text(self):
        raw = "Vendor: TestCorp, Amount: $500, Date: 2026-07-01"
        result = parse_invoice(raw)
        assert isinstance(result, str)

    def test_validate_invoice_existing(self):
        result = validate_invoice("INV-001")
        assert isinstance(result, str)

    def test_validate_invoice_nonexistent(self):
        result = validate_invoice("INV-999")
        assert isinstance(result, str)
        # Should mention not found or error
        lower = result.lower()
        assert "not found" in lower or "error" in lower or "no invoice" in lower


# ---------------------------------------------------------------------------
# Reporting Tools Tests
# ---------------------------------------------------------------------------

class TestReportingTools:
    """Tests for reporting tool functions."""

    def test_generate_expense_report(self):
        result = generate_expense_report()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_budget_report(self):
        result = generate_budget_report()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_financial_summary(self):
        result = get_financial_summary()
        assert isinstance(result, str)
        assert len(result) > 100  # Should be a substantial report
