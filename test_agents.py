"""Integration tests for FinOps agent definitions.

These tests verify that all agents are properly defined, importable, and
correctly configured with the expected tools, sub-agents, and callbacks.

Run with:
    python -m pytest tests/test_agents.py -v
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Agent Definition Tests
# ---------------------------------------------------------------------------

class TestAgentDefinitions:
    """Test that all agents are properly defined and importable."""

    def test_import_expense_tracker(self):
        from finops_agent.agents.expense_tracker import expense_tracker_agent

        assert expense_tracker_agent.name == "ExpenseTracker"
        assert len(expense_tracker_agent.tools) == 4

    def test_expense_tracker_has_correct_tools(self):
        from finops_agent.agents.expense_tracker import expense_tracker_agent

        tool_names = {t.__name__ if callable(t) else str(t) for t in expense_tracker_agent.tools}
        expected = {"add_expense", "list_expenses", "get_spending_by_category", "get_spending_by_department"}
        assert expected == tool_names

    def test_import_budget_analyst(self):
        from finops_agent.agents.budget_analyst import budget_analyst_agent

        assert budget_analyst_agent.name == "BudgetAnalyst"
        assert len(budget_analyst_agent.tools) == 4

    def test_budget_analyst_has_correct_tools(self):
        from finops_agent.agents.budget_analyst import budget_analyst_agent

        tool_names = {t.__name__ if callable(t) else str(t) for t in budget_analyst_agent.tools}
        expected = {"set_budget", "check_budget_status", "forecast_spending", "get_budget_alerts"}
        assert expected == tool_names

    def test_import_invoice_parser(self):
        from finops_agent.agents.invoice_parser import invoice_parser_agent

        assert invoice_parser_agent.name == "InvoiceParser"
        assert len(invoice_parser_agent.tools) == 4

    def test_invoice_parser_has_correct_tools(self):
        from finops_agent.agents.invoice_parser import invoice_parser_agent

        tool_names = {t.__name__ if callable(t) else str(t) for t in invoice_parser_agent.tools}
        expected = {"parse_invoice", "validate_invoice", "list_pending_invoices", "approve_invoice"}
        assert expected == tool_names

    def test_import_reporting_agent(self):
        from finops_agent.agents.reporting_agent import reporting_agent

        assert reporting_agent.name == "ReportingAgent"
        assert len(reporting_agent.tools) == 3

    def test_reporting_agent_has_correct_tools(self):
        from finops_agent.agents.reporting_agent import reporting_agent

        tool_names = {t.__name__ if callable(t) else str(t) for t in reporting_agent.tools}
        expected = {"generate_expense_report", "generate_budget_report", "get_financial_summary"}
        assert expected == tool_names

    def test_import_orchestrator(self):
        from finops_agent.agents.orchestrator import orchestrator_agent

        assert orchestrator_agent.name == "FinOpsOrchestrator"
        assert len(orchestrator_agent.sub_agents) == 4

    def test_orchestrator_has_all_sub_agents(self):
        from finops_agent.agents.orchestrator import orchestrator_agent

        sub_agent_names = {sa.name for sa in orchestrator_agent.sub_agents}
        expected = {"ExpenseTracker", "BudgetAnalyst", "InvoiceParser", "ReportingAgent"}
        assert expected == sub_agent_names

    def test_orchestrator_has_guardrails(self):
        from finops_agent.agents.orchestrator import orchestrator_agent

        assert orchestrator_agent.before_model_callback is not None
        assert orchestrator_agent.before_tool_callback is not None

    def test_root_agent_is_orchestrator(self):
        from finops_agent.agent import root_agent

        assert root_agent.name == "FinOpsOrchestrator"

    def test_all_agents_use_gemini_model(self):
        from finops_agent.agents.expense_tracker import expense_tracker_agent
        from finops_agent.agents.budget_analyst import budget_analyst_agent
        from finops_agent.agents.invoice_parser import invoice_parser_agent
        from finops_agent.agents.reporting_agent import reporting_agent
        from finops_agent.agents.orchestrator import orchestrator_agent

        agents = [
            expense_tracker_agent,
            budget_analyst_agent,
            invoice_parser_agent,
            reporting_agent,
            orchestrator_agent,
        ]
        for agent in agents:
            assert "gemini" in agent.model, f"{agent.name} should use a Gemini model"


# ---------------------------------------------------------------------------
# Guardrail Tests
# ---------------------------------------------------------------------------

class TestGuardrails:
    """Test that guardrails are properly configured."""

    def test_import_input_validator(self):
        from finops_agent.guardrails.input_validator import input_safety_callback

        assert callable(input_safety_callback)

    def test_import_budget_guard(self):
        from finops_agent.guardrails.budget_guard import spending_guard_callback

        assert callable(spending_guard_callback)

    def test_spending_limit_constant(self):
        from finops_agent.guardrails.budget_guard import SPENDING_LIMIT

        assert SPENDING_LIMIT == 10_000.00

    def test_pii_patterns_defined(self):
        from finops_agent.guardrails.input_validator import PII_PATTERNS

        assert "SSN" in PII_PATTERNS
        assert "Credit Card" in PII_PATTERNS

    def test_injection_patterns_defined(self):
        from finops_agent.guardrails.input_validator import INJECTION_PATTERNS

        assert len(INJECTION_PATTERNS) > 0


# ---------------------------------------------------------------------------
# Memory & Session Tests
# ---------------------------------------------------------------------------

class TestMemory:
    """Test memory and session services."""

    def test_import_session_service(self):
        from finops_agent.memory.session_manager import get_session_service

        session_svc = get_session_service()
        assert session_svc is not None

    def test_import_memory_service(self):
        from finops_agent.memory.session_manager import get_memory_service

        memory_svc = get_memory_service()
        assert memory_svc is not None

    def test_app_name_constant(self):
        from finops_agent.memory.session_manager import APP_NAME

        assert APP_NAME == "finops_agent"


# ---------------------------------------------------------------------------
# MCP Server Tests
# ---------------------------------------------------------------------------

class TestMCPServer:
    """Test that the MCP server module is importable and configured."""

    def test_import_mcp_server(self):
        from finops_agent.mcp_server import finance_mcp

        assert hasattr(finance_mcp, "server")

    def test_exchange_rates_defined(self):
        from finops_agent.mcp_server.finance_mcp import EXCHANGE_RATES

        assert len(EXCHANGE_RATES) > 0
        assert "USD_EUR" in EXCHANGE_RATES

    def test_tax_rates_defined(self):
        from finops_agent.mcp_server.finance_mcp import TAX_RATES

        assert len(TAX_RATES) > 0
        assert "CA" in TAX_RATES

    def test_company_policies_defined(self):
        from finops_agent.mcp_server.finance_mcp import COMPANY_POLICIES

        assert len(COMPANY_POLICIES) > 0
        assert "expense_approval" in COMPANY_POLICIES
