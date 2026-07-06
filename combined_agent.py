"""Combined FinOps Command Center Agent.

Consolidates all tools, guardrails, specialist agents, and orchestrator
into a single, self-contained Python file for easy deployment or upload.
"""

from __future__ import annotations

import json
import re
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types
from google.adk.tools import BaseTool

logger = logging.getLogger(__name__)

# ===========================================================================
# 1. DATA STORE (FinanceDB Singleton & Mock Data)
# ===========================================================================

# Locate the data directory (lives at <workspace_root>/data/)
_PROJECT_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _PROJECT_ROOT / "data"

_DEFAULT_EXPENSES: list[dict] = [
    {
        "id": "EXP-001",
        "description": "Flight to NYC for client meeting",
        "amount": 450.00,
        "category": "Travel",
        "date": "2026-07-01",
        "employee": "Alice Chen",
        "department": "Sales",
        "status": "approved",
    },
    {
        "id": "EXP-002",
        "description": "GitHub Copilot annual license",
        "amount": 1200.00,
        "category": "Software",
        "date": "2026-06-28",
        "employee": "Bob Martinez",
        "department": "Engineering",
        "status": "approved",
    },
    {
        "id": "EXP-003",
        "description": "Google Ads campaign - July",
        "amount": 5000.00,
        "category": "Marketing",
        "date": "2026-07-02",
        "employee": "Carol Davis",
        "department": "Marketing",
        "status": "pending",
    },
    {
        "id": "EXP-004",
        "description": "Office chair ergonomic upgrade",
        "amount": 350.00,
        "category": "Office Supplies",
        "date": "2026-06-30",
        "employee": "David Kim",
        "department": "Operations",
        "status": "approved",
    },
    {
        "id": "EXP-005",
        "description": "Team dinner - Q2 celebration",
        "amount": 780.00,
        "category": "Meals & Entertainment",
        "date": "2026-06-27",
        "employee": "Eva Johnson",
        "department": "Engineering",
        "status": "pending",
    },
    {
        "id": "EXP-006",
        "description": "Legal consultation fee",
        "amount": 2500.00,
        "category": "Professional Services",
        "date": "2026-07-01",
        "employee": "Frank Lee",
        "department": "Finance",
        "status": "approved",
    },
    {
        "id": "EXP-007",
        "description": "AWS infrastructure - June",
        "amount": 8200.00,
        "category": "Software",
        "date": "2026-06-30",
        "employee": "Grace Park",
        "department": "Engineering",
        "status": "approved",
    },
    {
        "id": "EXP-008",
        "description": "Sales conference registration",
        "amount": 1500.00,
        "category": "Travel",
        "date": "2026-07-03",
        "employee": "Henry Wong",
        "department": "Sales",
        "status": "pending",
    },
]

_DEFAULT_INVOICES: list[dict] = [
    {
        "id": "INV-001",
        "vendor": "CloudHost Inc.",
        "amount": 12500.00,
        "date": "2026-07-01",
        "due_date": "2026-07-31",
        "status": "pending",
        "line_items": [
            {"description": "Compute instances (x10)", "amount": 8000.00},
            {"description": "Storage (5 TB)", "amount": 2500.00},
            {"description": "Network egress", "amount": 2000.00},
        ],
    },
    {
        "id": "INV-002",
        "vendor": "Office Depot",
        "amount": 2340.00,
        "date": "2026-06-28",
        "due_date": "2026-07-28",
        "status": "approved",
        "line_items": [
            {"description": "Standing desks (x3)", "amount": 1800.00},
            {"description": "Monitor arms (x3)", "amount": 540.00},
        ],
    },
    {
        "id": "INV-003",
        "vendor": "TechRecruiters LLC",
        "amount": 15000.00,
        "date": "2026-06-25",
        "due_date": "2026-07-25",
        "status": "pending",
        "line_items": [
            {"description": "Senior Engineer placement fee", "amount": 15000.00},
        ],
    },
    {
        "id": "INV-004",
        "vendor": "Marketing Pro Agency",
        "amount": 7800.00,
        "date": "2026-07-02",
        "due_date": "2026-08-01",
        "status": "pending",
        "line_items": [
            {"description": "Brand strategy consulting", "amount": 5000.00},
            {"description": "Social media management - July", "amount": 2800.00},
        ],
    },
    {
        "id": "INV-005",
        "vendor": "SecureIT Solutions",
        "amount": 4500.00,
        "date": "2026-06-30",
        "due_date": "2026-07-30",
        "status": "approved",
        "line_items": [
            {"description": "Penetration testing", "amount": 3000.00},
            {"description": "Security audit report", "amount": 1500.00},
        ],
    },
]

_DEFAULT_BUDGETS: list[dict] = [
    {"category": "Travel", "department": "all", "allocated": 25000.00, "spent": 1950.00, "period": "Q3 2026"},
    {"category": "Software", "department": "all", "allocated": 50000.00, "spent": 9400.00, "period": "Q3 2026"},
    {"category": "Marketing", "department": "all", "allocated": 30000.00, "spent": 5000.00, "period": "Q3 2026"},
    {"category": "Office Supplies", "department": "all", "allocated": 10000.00, "spent": 350.00, "period": "Q3 2026"},
    {"category": "Meals & Entertainment", "department": "all", "allocated": 8000.00, "spent": 780.00, "period": "Q3 2026"},
    {"category": "Professional Services", "department": "all", "allocated": 20000.00, "spent": 2500.00, "period": "Q3 2026"},
]

def _load_json(filename: str, fallback: list[dict]) -> list[dict]:
    path = _DATA_DIR / filename
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
            return fallback
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return [dict(item) for item in fallback]

class FinanceDB:
    _instance: Optional["FinanceDB"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "FinanceDB":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._init_data()
                cls._instance = instance
            return cls._instance

    def _init_data(self) -> None:
        self.expenses: list[dict] = _load_json("sample_expenses.json", _DEFAULT_EXPENSES)
        self.invoices: list[dict] = _load_json("sample_invoices.json", _DEFAULT_INVOICES)
        self.budgets: list[dict] = _load_json("sample_budgets.json", _DEFAULT_BUDGETS)
        self._expense_counter: int = self._max_id(self.expenses, "EXP")
        self._invoice_counter: int = self._max_id(self.invoices, "INV")

    @staticmethod
    def _max_id(records: list[dict], prefix: str) -> int:
        max_val = 0
        for rec in records:
            rid = rec.get("id", "")
            if rid.startswith(prefix + "-"):
                try:
                    num = int(rid.split("-", 1)[1])
                    max_val = max(max_val, num)
                except ValueError:
                    pass
        return max_val

    def next_expense_id(self) -> str:
        self._expense_counter += 1
        return f"EXP-{self._expense_counter:03d}"

    def next_invoice_id(self) -> str:
        self._invoice_counter += 1
        return f"INV-{self._invoice_counter:03d}"

    def add_expense(self, expense: dict) -> dict:
        expense.setdefault("id", self.next_expense_id())
        expense.setdefault("status", "pending")
        self.expenses.append(expense)
        return expense

    def get_expenses(
        self,
        category: Optional[str] = None,
        department: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        results = self.expenses
        if category:
            results = [e for e in results if e.get("category", "").lower() == category.lower()]
        if department:
            results = [e for e in results if e.get("department", "").lower() == department.lower()]
        if status:
            results = [e for e in results if e.get("status", "").lower() == status.lower()]
        return results

    def add_invoice(self, invoice: dict) -> dict:
        invoice.setdefault("id", self.next_invoice_id())
        invoice.setdefault("status", "pending")
        self.invoices.append(invoice)
        return invoice

    def get_invoices(
        self,
        status: Optional[str] = None,
        vendor: Optional[str] = None,
    ) -> list[dict]:
        results = self.invoices
        if status:
            results = [i for i in results if i.get("status", "").lower() == status.lower()]
        if vendor:
            vendor_lower = vendor.lower()
            results = [i for i in results if vendor_lower in i.get("vendor", "").lower()]
        return results

    def get_budgets(
        self,
        category: Optional[str] = None,
        department: Optional[str] = None,
    ) -> list[dict]:
        results = self.budgets
        if category:
            results = [b for b in results if b.get("category", "").lower() == category.lower()]
        if department:
            results = [b for b in results if b.get("department", "").lower() == department.lower()]
        return results

    def update_budget_spent(self, category: str, amount: float) -> dict:
        for budget in self.budgets:
            if budget.get("category", "").lower() == category.lower():
                budget["spent"] = budget.get("spent", 0.0) + amount
                return budget
        return {"error": f"No budget found for category '{category}'"}

def get_db() -> FinanceDB:
    return FinanceDB()


# ===========================================================================
# 2. AGENT TOOLS IMPLEMENTATION
# ===========================================================================

# ---- Expense Tools --------------------------------------------------------

def add_expense(
    description: str,
    amount: float,
    category: str,
    date: str,
    employee: str,
    department: str,
) -> dict:
    """Add a new expense record to the system."""
    try:
        db = get_db()
        expense = {
            "description": description,
            "amount": round(float(amount), 2),
            "category": category,
            "date": date,
            "employee": employee,
            "department": department,
        }
        created = db.add_expense(expense)
        db.update_budget_spent(category, created["amount"])
        return {
            "status": "success",
            "message": f"Expense '{description}' recorded successfully.",
            "expense": created,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Failed to add expense: {exc}"}

def list_expenses(
    category: str = "",
    department: str = "",
    status: str = "",
) -> str:
    """List expenses with optional filtering."""
    try:
        db = get_db()
        expenses = db.get_expenses(
            category=category or None,
            department=department or None,
            status=status or None,
        )

        if not expenses:
            return "No expenses found matching filters."

        lines = [
            "=" * 72,
            "  Expenses Report",
            "=" * 72,
            "",
            f"  {'ID':<10} {'Date':<12} {'Description':<28} {'Amount':>10} {'Status':<10}",
            f"  {'-' * 10} {'-' * 12} {'-' * 28} {'-' * 10} {'-' * 10}"
        ]

        total = 0.0
        for exp in expenses:
            desc = exp.get("description", "")
            if len(desc) > 26:
                desc = desc[:24] + ".."
            lines.append(
                f"  {exp.get('id', 'N/A'):<10} "
                f"{exp.get('date', 'N/A'):<12} "
                f"{desc:<28} "
                f"${exp.get('amount', 0):>9,.2f} "
                f"{exp.get('status', 'N/A'):<10}"
            )
            total += exp.get("amount", 0)

        lines.append(f"  {'-' * 72}")
        lines.append(f"  {'Total':<52} ${total:>9,.2f}")
        lines.append(f"  {'Count':<52} {len(expenses):>10}")
        lines.append("=" * 72)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error listing expenses: {exc}"

def get_spending_by_category() -> str:
    """Get total spending broken down by category."""
    try:
        db = get_db()
        expenses = db.get_expenses()
        if not expenses:
            return "No expenses recorded yet."

        by_category: dict[str, float] = {}
        for exp in expenses:
            cat = exp.get("category", "Uncategorized")
            by_category[cat] = by_category.get(cat, 0.0) + exp.get("amount", 0.0)

        grand_total = sum(by_category.values())
        sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

        lines = [
            "=" * 60,
            "  Spending by Category",
            "=" * 60,
            "",
            f"  {'Category':<28} {'Amount':>12} {'Share':>8}",
            f"  {'-' * 28} {'-' * 12} {'-' * 8}"
        ]

        for cat, amount in sorted_cats:
            pct = (amount / grand_total * 100) if grand_total > 0 else 0
            bar = "█" * int(pct / 5)
            lines.append(f"  {cat:<28} ${amount:>11,.2f} {pct:>6.1f}%  {bar}")

        lines.append(f"  {'-' * 50}")
        lines.append(f"  {'TOTAL':<28} ${grand_total:>11,.2f}")
        lines.append("=" * 60)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating category spending report: {exc}"

def get_spending_by_department() -> str:
    """Get total spending broken down by department."""
    try:
        db = get_db()
        expenses = db.get_expenses()
        if not expenses:
            return "No expenses recorded yet."

        by_dept: dict[str, float] = {}
        for exp in expenses:
            dept = exp.get("department", "Unknown")
            by_dept[dept] = by_dept.get(dept, 0.0) + exp.get("amount", 0.0)

        grand_total = sum(by_dept.values())
        sorted_depts = sorted(by_dept.items(), key=lambda x: x[1], reverse=True)

        lines = [
            "=" * 60,
            "  Spending by Department",
            "=" * 60,
            "",
            f"  {'Department':<28} {'Amount':>12} {'Share':>8}",
            f"  {'-' * 28} {'-' * 12} {'-' * 8}"
        ]

        for dept, amount in sorted_depts:
            pct = (amount / grand_total * 100) if grand_total > 0 else 0
            bar = "█" * int(pct / 5)
            lines.append(f"  {dept:<28} ${amount:>11,.2f} {pct:>6.1f}%  {bar}")

        lines.append(f"  {'-' * 50}")
        lines.append(f"  {'TOTAL':<28} ${grand_total:>11,.2f}")
        lines.append("=" * 60)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating department spending report: {exc}"


# ---- Budget Tools ---------------------------------------------------------

def set_budget(
    category: str,
    allocated_amount: float,
    department: str,
    period: str = "Q3 2026",
) -> str:
    """Set or update a budget allocation for a category."""
    try:
        db = get_db()
        allocated_amount = round(float(allocated_amount), 2)

        for budget in db.budgets:
            if (
                budget.get("category", "").lower() == category.lower()
                and budget.get("department", "").lower() == department.lower()
                and budget.get("period", "") == period
            ):
                old_amount = budget["allocated"]
                budget["allocated"] = allocated_amount
                return (
                    f"✅ Budget updated for '{category}' ({department}, {period}).\n"
                    f"   Previous allocation: ${old_amount:,.2f}\n"
                    f"   New allocation:      ${allocated_amount:,.2f}\n"
                    f"   Current spending:    ${budget.get('spent', 0):,.2f}\n"
                    f"   Remaining:           ${allocated_amount - budget.get('spent', 0):,.2f}"
                )

        new_budget = {
            "category": category,
            "department": department,
            "allocated": allocated_amount,
            "spent": 0.0,
            "period": period,
        }
        db.budgets.append(new_budget)
        return (
            f"✅ New budget created for '{category}' ({department}, {period}).\n"
            f"   Allocated: ${allocated_amount:,.2f}\n"
            f"   Spent:     $0.00\n"
            f"   Remaining: ${allocated_amount:,.2f}"
        )
    except Exception as exc:
        return f"Error setting budget: {exc}"

def check_budget_status(category: str = "") -> str:
    """Check budget status showing allocated vs spent amounts."""
    try:
        db = get_db()
        budgets = db.get_budgets(category=category or None)
        if not budgets:
            return "No budgets configured."

        lines = [
            "=" * 72,
            "  Budget Status Report",
            "=" * 72,
            "",
            f"  {'Category':<22} {'Allocated':>12} {'Spent':>12} {'Remaining':>12} {'Used':>7}",
            f"  {'-' * 22} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 7}"
        ]

        total_allocated = 0.0
        total_spent = 0.0

        for b in budgets:
            allocated = b.get("allocated", 0.0)
            spent = b.get("spent", 0.0)
            remaining = allocated - spent
            pct = (spent / allocated * 100) if allocated > 0 else 0
            indicator = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
            bar = "█" * min(int(pct / 5), 20) + "░" * (20 - min(int(pct / 5), 20))

            lines.append(
                f"  {b.get('category', 'N/A'):<22} "
                f"${allocated:>11,.2f} "
                f"${spent:>11,.2f} "
                f"${remaining:>11,.2f} "
                f"{pct:>5.1f}% {indicator}"
            )
            lines.append(f"  {'':>22} [{bar}]")
            total_allocated += allocated
            total_spent += spent

        total_remaining = total_allocated - total_spent
        total_pct = (total_spent / total_allocated * 100) if total_allocated > 0 else 0

        lines.append(f"  {'-' * 68}")
        lines.append(
            f"  {'TOTAL':<22} "
            f"${total_allocated:>11,.2f} "
            f"${total_spent:>11,.2f} "
            f"${total_remaining:>11,.2f} "
            f"{total_pct:>5.1f}%"
        )
        lines.append("=" * 72)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error checking budget status: {exc}"

def forecast_spending(category: str, months_ahead: int = 3) -> str:
    """Forecast future spending based on current trends."""
    try:
        db = get_db()
        budgets = db.get_budgets(category=category)
        if not budgets:
            return f"No budget found for category '{category}'."

        budget = budgets[0]
        allocated = budget.get("allocated", 0.0)
        spent = budget.get("spent", 0.0)
        monthly_rate = spent

        lines = [
            "=" * 56,
            f"  Spending Forecast: {category}",
            "=" * 56,
            f"  Current budget:   ${allocated:>12,.2f}",
            f"  Current spent:    ${spent:>12,.2f}",
            f"  Monthly run-rate: ${monthly_rate:>12,.2f}",
            "",
            f"  {'Month':<18} {'Projected Spend':>16} {'Cumulative':>14} {'Status':>8}",
            f"  {'-' * 18} {'-' * 16} {'-' * 14} {'-' * 8}"
        ]

        cumulative = spent
        for month in range(1, months_ahead + 1):
            cumulative += monthly_rate
            status = "⚠️ OVER" if cumulative > allocated else "✅ OK"
            lines.append(f"  Month +{month:<10} ${monthly_rate:>15,.2f} ${cumulative:>13,.2f} {status}")

        lines.append("")
        projected_end = spent + (monthly_rate * months_ahead)
        variance = allocated - projected_end

        if variance >= 0:
            lines.append(f"  📊 Projected end-of-period total: ${projected_end:>12,.2f}")
            lines.append(f"     Expected to be ${variance:,.2f} UNDER budget.")
        else:
            lines.append(f"  📊 Projected end-of-period total: ${projected_end:>12,.2f}")
            lines.append(f"     ⚠️  Expected to be ${abs(variance):,.2f} OVER budget!")

        lines.append("=" * 56)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error forecasting spending: {exc}"

def get_budget_alerts() -> str:
    """Get alerts for budgets that are over 80% utilized or exceeded."""
    try:
        db = get_db()
        budgets = db.get_budgets()
        if not budgets:
            return "No budgets configured."

        alerts = []
        for b in budgets:
            allocated = b.get("allocated", 0.0)
            spent = b.get("spent", 0.0)
            if allocated <= 0:
                continue
            pct = spent / allocated * 100

            if pct >= 100:
                alerts.append({
                    "severity": "CRITICAL", "icon": "🔴", "category": b.get("category", "Unknown"),
                    "message": f"Budget EXCEEDED — spent ${spent:,.2f} of ${allocated:,.2f} ({pct:.1f}%)",
                    "overage": spent - allocated
                })
            elif pct >= 80:
                alerts.append({
                    "severity": "WARNING", "icon": "🟡", "category": b.get("category", "Unknown"),
                    "message": f"Budget approaching limit — spent ${spent:,.2f} of ${allocated:,.2f} ({pct:.1f}%)",
                    "remaining": allocated - spent
                })

        if not alerts:
            return "✅ All budgets are within healthy limits (under 80% utilization). No alerts."

        lines = [
            "=" * 64,
            f"  ⚠️  Budget Alerts ({len(alerts)} active)",
            "=" * 64,
            ""
        ]

        for alert in sorted(alerts, key=lambda a: 0 if a["severity"] == "CRITICAL" else 1):
            lines.append(f"  {alert['icon']} [{alert['severity']}] {alert['category']}")
            lines.append(f"     {alert['message']}")
            if "overage" in alert:
                lines.append(f"     Overage: ${alert['overage']:,.2f}")
            elif "remaining" in alert:
                lines.append(f"     Remaining: ${alert['remaining']:,.2f}")
            lines.append("")

        lines.append("=" * 64)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving budget alerts: {exc}"


# ---- Invoice Tools --------------------------------------------------------

def parse_invoice(raw_text: str) -> str:
    """Parse structured data from raw invoice text."""
    try:
        db = get_db()
        vendor = "Unknown Vendor"
        vendor_match = re.search(r"(?:from|vendor|company|billed\s+by)[:\s]+([A-Z][\w\s&.,']+)", raw_text, re.IGNORECASE)
        if vendor_match:
            vendor = vendor_match.group(1).strip().rstrip(".,")

        amounts = re.findall(r"\$\s?([\d,]+(?:\.\d{2})?)", raw_text)
        total_amount = max([float(a.replace(",", "")) for a in amounts]) if amounts else 0.0

        invoice_date = datetime.now().strftime("%Y-%m-%d")
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", raw_text)
        if date_match:
            invoice_date = date_match.group(1)

        line_items = []
        for line in raw_text.split("\n"):
            line = line.strip()
            item_match = re.search(r"(.+?)\s+\$\s?([\d,]+(?:\.\d{2})?)", line)
            if item_match:
                item_desc = item_match.group(1).strip().rstrip("-–—:•")
                item_amount = float(item_match.group(2).replace(",", ""))
                if item_amount != total_amount:
                    line_items.append({"description": item_desc, "amount": item_amount})

        if not line_items and total_amount > 0:
            line_items.append({"description": "Invoice total", "amount": total_amount})

        invoice = {
            "vendor": vendor,
            "amount": total_amount,
            "date": invoice_date,
            "due_date": "",
            "status": "pending",
            "line_items": line_items,
        }
        created = db.add_invoice(invoice)

        lines = [
            "=" * 56,
            "  📄 Parsed Invoice",
            "=" * 56,
            f"  ID:       {created['id']}",
            f"  Vendor:   {vendor}",
            f"  Amount:   ${total_amount:,.2f}",
            f"  Date:     {invoice_date}",
            f"  Status:   pending",
            ""
        ]
        if line_items:
            lines.append("  Line Items:")
            for item in line_items:
                lines.append(f"    • {item['description']:<36} ${item['amount']:>10,.2f}")
        lines.append("=" * 56)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error parsing invoice: {exc}"

def validate_invoice(invoice_id: str) -> str:
    """Validate an invoice record checking for completeness and anomalies."""
    try:
        db = get_db()
        invoice = next((inv for inv in db.invoices if inv.get("id", "").upper() == invoice_id.upper()), None)
        if not invoice:
            return f"Invoice '{invoice_id}' not found."

        issues = []
        passes = []

        for field in ["vendor", "amount", "date", "status"]:
            if not invoice.get(field):
                issues.append(f"Missing field: '{field}'")
            else:
                passes.append(f"Field '{field}' present")

        amount = invoice.get("amount", 0)
        if amount <= 0:
            issues.append(f"Invalid amount: ${amount:,.2f}")
        else:
            passes.append(f"Amount ${amount:,.2f} is valid")

        line_items = invoice.get("line_items", [])
        if line_items:
            items_total = sum(item.get("amount", 0) for item in line_items)
            if abs(items_total - amount) > 0.01:
                issues.append(f"Line items total (${items_total:,.2f}) mismatch invoice amount")
            else:
                passes.append("Line items total matches invoice amount")
        else:
            issues.append("No line items found")

        duplicates = [inv for inv in db.invoices if inv.get("id") != invoice.get("id") and inv.get("vendor", "").lower() == invoice.get("vendor", "").lower() and inv.get("amount") == invoice.get("amount")]
        if duplicates:
            issues.append(f"Potential duplicate(s): {', '.join(d.get('id', '?') for d in duplicates)}")
        else:
            passes.append("No duplicates detected")

        status = "❌ FAILED" if issues else "✅ PASSED"
        lines = [
            "=" * 56,
            f"  Invoice Validation Report — {invoice_id}",
            f"  Overall: {status}",
            "=" * 56,
            ""
        ]
        if passes:
            lines.append("  ✅ Passed Checks:")
            for p in passes: lines.append(f"     ✓ {p}")
        if issues:
            lines.append("\n  ❌ Issues Found:")
            for issue in issues: lines.append(f"     ✗ {issue}")
        lines.append(f"\n  Summary: {len(passes)} passed, {len(issues)} issue(s)")
        lines.append("=" * 56)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error validating invoice: {exc}"

def list_pending_invoices() -> str:
    """List all invoices with pending status awaiting approval."""
    try:
        db = get_db()
        pending = db.get_invoices(status="pending")
        if not pending:
            return "✅ No pending invoices."

        lines = [
            "=" * 68,
            f"  Pending Invoices ({len(pending)} awaiting approval)",
            "=" * 68,
            "",
            f"  {'ID':<10} {'Vendor':<24} {'Amount':>12} {'Date':<12} {'Due Date':<12}",
            f"  {'-' * 10} {'-' * 24} {'-' * 12} {'-' * 12} {'-' * 12}"
        ]

        total = 0.0
        for inv in pending:
            vendor = inv.get("vendor", "Unknown")
            if len(vendor) > 22:
                vendor = vendor[:20] + ".."
            lines.append(
                f"  {inv.get('id', 'N/A'):<10} "
                f"{vendor:<24} "
                f"${inv.get('amount', 0):>11,.2f} "
                f"{inv.get('date', 'N/A'):<12} "
                f"{inv.get('due_date', 'N/A'):<12}"
            )
            total += inv.get("amount", 0)

        lines.append(f"  {'-' * 68}")
        lines.append(f"  {'Total pending':<36} ${total:>11,.2f}")
        lines.append("=" * 68)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error listing pending invoices: {exc}"

def approve_invoice(invoice_id: str) -> str:
    """Approve a pending invoice and update its status."""
    try:
        db = get_db()
        invoice = next((inv for inv in db.invoices if inv.get("id", "").upper() == invoice_id.upper()), None)
        if not invoice:
            return f"❌ Invoice '{invoice_id}' not found."

        current_status = invoice.get("status", "").lower()
        if current_status == "approved":
            return f"ℹ️ Invoice '{invoice_id}' is already approved."
        if current_status != "pending":
            return f"❌ Cannot approve invoice '{invoice_id}' — current status is '{current_status}'."

        invoice["status"] = "approved"
        invoice["approved_date"] = datetime.now().strftime("%Y-%m-%d")

        return (
            f"✅ Invoice {invoice_id} approved successfully!\n\n"
            f"   Vendor:   {invoice.get('vendor', 'Unknown')}\n"
            f"   Amount:   ${invoice.get('amount', 0):,.2f}\n"
            f"   Status:   approved"
        )
    except Exception as exc:
        return f"Error approving invoice: {exc}"


# ---- Reporting Tools ------------------------------------------------------

def generate_expense_report(period: str = "Q3 2026") -> str:
    """Generate a comprehensive expense report for the specified period."""
    try:
        db = get_db()
        expenses = db.get_expenses()
        if not expenses:
            return "No expenses recorded."

        total = sum(e.get("amount", 0) for e in expenses)
        count = len(expenses)

        by_category: dict[str, float] = {}
        by_department: dict[str, float] = {}
        by_status: dict[str, int] = {}
        for e in expenses:
            cat = e.get("category", "Uncategorized")
            dept = e.get("department", "Unknown")
            status = e.get("status", "unknown")
            by_category[cat] = by_category.get(cat, 0.0) + e.get("amount", 0.0)
            by_department[dept] = by_department.get(dept, 0.0) + e.get("amount", 0.0)
            by_status[status] = by_status.get(status, 0) + 1

        top5 = sorted(expenses, key=lambda x: x.get("amount", 0), reverse=True)[:5]

        lines = [
            "═" * 72,
            f"  💰 EXPENSE REPORT — {period}",
            "═" * 72,
            "",
            "  📊 Summary",
            f"  {'─' * 40}",
            f"  Total Expenses:    ${total:>12,.2f}",
            f"  Number of Records: {count:>13}",
            "",
            "  📋 By Status",
            f"  {'─' * 40}"
        ]
        for s, cnt in sorted(by_status.items()):
            icon = "✅" if s == "approved" else ("⏳" if s == "pending" else "❌")
            lines.append(f"  {icon} {s.capitalize():<16} {cnt:>5} records")

        lines.extend(["", "  📂 By Category", f"  {'─' * 56}"])
        for cat, amt in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100) if total > 0 else 0
            lines.append(f"  {cat:<28} ${amt:>11,.2f} {pct:>6.1f}%")

        lines.extend(["", "  🏢 By Department", f"  {'─' * 56}"])
        for dept, amt in sorted(by_department.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100) if total > 0 else 0
            lines.append(f"  {dept:<28} ${amt:>11,.2f} {pct:>6.1f}%")

        lines.extend(["", "  🔝 Top 5 Expenses", f"  {'─' * 66}"])
        for i, exp in enumerate(top5, 1):
            lines.append(f"  {i:<3} {exp.get('description', '')[:30]:<32} {exp.get('employee', '')[:14]:<16} ${exp.get('amount', 0):>11,.2f}")

        lines.append("═" * 72)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating expense report: {exc}"

def generate_budget_report() -> str:
    """Generate a budget vs actual comparison report."""
    try:
        db = get_db()
        budgets = db.get_budgets()
        if not budgets:
            return "No budgets configured."

        lines = [
            "═" * 72,
            "  📊 BUDGET VS ACTUAL REPORT",
            "═" * 72,
            ""
        ]

        total_allocated = 0.0
        total_spent = 0.0
        alerts = []

        for b in budgets:
            cat = b.get("category", "Unknown")
            allocated = b.get("allocated", 0.0)
            spent = b.get("spent", 0.0)
            remaining = allocated - spent
            pct = (spent / allocated * 100) if allocated > 0 else 0

            total_allocated += allocated
            total_spent += spent

            icon = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
            status_text = "OVER BUDGET" if pct >= 100 else ("CAUTION" if pct >= 80 else "ON TRACK")
            if pct >= 100:
                alerts.append(f"🔴 {cat}: ${abs(remaining):,.2f} over budget")
            elif pct >= 80:
                alerts.append(f"🟡 {cat}: approaching limit ({pct:.0f}% used)")

            bar = "█" * min(int(pct / 4), 25) + "░" * (25 - min(int(pct / 4), 25))
            lines.append(f"  {icon} {cat}")
            lines.append(f"    Allocated: ${allocated:>11,.2f}  |  Spent: ${spent:>11,.2f}  |  Remaining: ${remaining:>11,.2f}")
            lines.append(f"    [{bar}] {pct:.1f}% — {status_text}\n")

        total_remaining = total_allocated - total_spent
        total_pct = (total_spent / total_allocated * 100) if total_allocated > 0 else 0

        lines.extend([
            "  " + "─" * 66,
            "  📈 Overall Totals",
            f"    Total Allocated: ${total_allocated:>12,.2f}",
            f"    Total Spent:     ${total_spent:>12,.2f}",
            f"    Total Remaining: ${total_remaining:>12,.2f}",
            f"    Utilization:     {total_pct:>12.1f}%\n"
        ])

        if alerts:
            lines.append("  ⚠️  Alerts:")
            for a in alerts: lines.append(f"    {a}")
        else:
            lines.append("  ✅ All budgets are on track.")

        lines.append("═" * 72)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating budget report: {exc}"

def get_financial_summary() -> str:
    """Generate a high-level financial dashboard summary."""
    try:
        db = get_db()
        expenses = db.get_expenses()
        total_expenses = sum(e.get("amount", 0) for e in expenses)
        approved_exp = [e for e in expenses if e.get("status") == "approved"]
        pending_exp = [e for e in expenses if e.get("status") == "pending"]

        budgets = db.get_budgets()
        total_allocated = sum(b.get("allocated", 0) for b in budgets)
        total_spent = sum(b.get("spent", 0) for b in budgets)
        budget_pct = (total_spent / total_allocated * 100) if total_allocated > 0 else 0

        invoices = db.get_invoices()
        pending_inv = db.get_invoices(status="pending")

        lines = [
            "═" * 72,
            "  🏦 FINANCIAL DASHBOARD SUMMARY",
            "═" * 72,
            "",
            "  💳 EXPENSES",
            f"  {'─' * 44}",
            f"  Total Expenses:          ${total_expenses:>12,.2f}",
            f"    Approved ({len(approved_exp)}):          ${sum(e.get('amount',0) for e in approved_exp):>12,.2f}",
            f"    Pending  ({len(pending_exp)}):          ${sum(e.get('amount',0) for e in pending_exp):>12,.2f}",
            "",
            "  📊 BUDGET UTILIZATION",
            f"  {'─' * 44}",
            f"  Total Allocated:         ${total_allocated:>12,.2f}",
            f"  Total Spent:             ${total_spent:>12,.2f}",
            f"  Remaining:               ${total_allocated - total_spent:>12,.2f}"
        ]
        bar = "█" * min(int(budget_pct / 4), 25) + "░" * (25 - min(int(budget_pct / 4), 25))
        lines.append(f"  Utilization: [{bar}] {budget_pct:.1f}%\n")

        lines.extend([
            "  📄 INVOICES",
            f"  {'─' * 44}",
            f"  Total Invoices:          {len(invoices)}",
            f"    Pending ({len(pending_inv)}):            ${sum(i.get('amount',0) for i in pending_inv):>12,.2f}\n"
        ])

        alerts = []
        if len(pending_inv) > 0:
            alerts.append(f"📄 {len(pending_inv)} invoice(s) pending approval")
        if len(pending_exp) > 0:
            alerts.append(f"⏳ {len(pending_exp)} expense(s) pending review")

        if alerts:
            lines.append("  ⚠️  KEY ALERTS")
            f"  {'─' * 44}"
            for a in alerts: lines.append(f"  {a}")
        else:
            lines.append("  ✅ All systems healthy.")

        lines.append("═" * 72)
        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating financial summary: {exc}"


# ===========================================================================
# 3. SECURITY GUARDRAILS (Callbacks)
# ===========================================================================

# PII Patterns
PII_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Credit Card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
}
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

# Prompt Injection Patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"act\s+as\s+(if\s+you\s+are|a)",
    r"disregard\s+(all\s+)?(prior|previous|above)",
    r"override\s+(your\s+)?(safety|security|instructions)",
]

_compiled_pii = {name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()}
_compiled_email = re.compile(EMAIL_PATTERN)
_compiled_injection = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

def _extract_user_text(llm_request: LlmRequest) -> Optional[str]:
    if not llm_request.contents:
        return None
    for content in reversed(llm_request.contents):
        if content.role == "user" and content.parts:
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
    return None

def _redact_pii(text: str) -> tuple[str, list[str]]:
    findings = []
    redacted = text
    for pii_name, pattern in _compiled_pii.items():
        matches = pattern.findall(redacted)
        if matches:
            findings.append(f"{pii_name} ({len(matches)})")
            redacted = pattern.sub(f"[REDACTED-{pii_name.upper().replace(' ', '-')}]", redacted)
    return redacted, findings

def _check_injection(text: str) -> Optional[str]:
    for pattern in _compiled_injection:
        match = pattern.search(text)
        if match:
            return match.group()
    return None

def _mutate_user_message(llm_request: LlmRequest, original: str, replacement: str) -> None:
    if not llm_request.contents:
        return
    for content in reversed(llm_request.contents):
        if content.role == "user" and content.parts:
            for i, part in enumerate(content.parts):
                if hasattr(part, "text") and part.text == original:
                    content.parts[i] = types.Part(text=replacement)
                    return

def input_safety_callback(
    callback_context: Context,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Before-model callback enforcing PII and injection checks."""
    user_text = _extract_user_text(llm_request)
    if not user_text:
        return None

    if _check_injection(user_text):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="I'm sorry, but I'm unable to process that request. It appears to conflict with my operating guidelines.")]
            )
        )

    redacted_text, findings = _redact_pii(user_text)
    if findings:
        _mutate_user_message(llm_request, user_text, redacted_text)

    return None

# Spending Policy Guardrail
SPENDING_LIMIT = 10_000.00

def spending_guard_callback(
    tool: BaseTool,
    args: dict,
    tool_context: Context,
) -> Optional[dict]:
    """Before-tool callback enforcing a spending limit on add_expense."""
    tool_name = tool.name if hasattr(tool, "name") else str(tool)

    if tool_name == "add_expense":
        amount = args.get("amount", 0)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"error": "Invalid expense amount provided."}

        if amount > SPENDING_LIMIT:
            return {
                "error": f"This expense of ${amount:,.2f} exceeds the single-transaction limit of ${SPENDING_LIMIT:,.2f}. Manager approval is required."
            }

    return None


# ===========================================================================
# 4. SPECIALIST & ORCHESTRATOR AGENTS DEFINITIONS
# ===========================================================================

expense_tracker_agent = LlmAgent(
    name="ExpenseTracker",
    model="gemini-2.5-flash",
    instruction="""You are an Expense Tracking specialist for the FinOps Command Center.
    - Add expenses with proper categories (Travel, Software, Marketing, Office Supplies, Meals & Entertainment, Professional Services).
    - List and filter expenses.
    - Present spending breakdowns.
    Always confirm details and format monetary values with $ and 2 decimal places.""",
    tools=[add_expense, list_expenses, get_spending_by_category, get_spending_by_department],
)

budget_analyst_agent = LlmAgent(
    name="BudgetAnalyst",
    model="gemini-2.5-flash",
    instruction="""You are a Budget Analysis specialist.
    - Manage budget allocations and check status.
    - Forecast spending and generate overrun alerts.
    Flag status over 80% with warning icon, over 100% with critical icon.""",
    tools=[set_budget, check_budget_status, forecast_spending, get_budget_alerts],
)

invoice_parser_agent = LlmAgent(
    name="InvoiceParser",
    model="gemini-2.5-flash",
    instruction="""You are an Invoice Processing specialist.
    - Parse structured data from raw invoice text.
    - Validate invoices and approve them.
    Always validate invoices before approving. Confirm details before approval.""",
    tools=[parse_invoice, validate_invoice, list_pending_invoices, approve_invoice],
)

reporting_agent = LlmAgent(
    name="ReportingAgent",
    model="gemini-2.5-flash",
    instruction="""You are a Financial Reporting specialist.
    - Generate expense reports, budget vs actual comparisons, and dashboards.
    Provide rich formatting with totals and clear takeaways.""",
    tools=[generate_expense_report, generate_budget_report, get_financial_summary],
)

# Main Orchestrator Agent
orchestrator_agent = LlmAgent(
    name="FinOpsOrchestrator",
    model="gemini-2.5-flash",
    instruction="""You are the FinOps Command Center orchestrator.
    Coordinate specialists to handle financial queries:
    1. ExpenseTracker — Add/list expenses, department/category breakdowns.
    2. BudgetAnalyst — Set budgets, status checks, forecasts, alerts.
    3. InvoiceParser — Parse raw invoice text, validate/approve invoices.
    4. ReportingAgent — Dashboards, reports.
    Always route to the correct sub-agent. Maintain a helpful and professional tone.""",
    sub_agents=[expense_tracker_agent, budget_analyst_agent, invoice_parser_agent, reporting_agent],
    before_model_callback=input_safety_callback,
    before_tool_callback=spending_guard_callback,
)

root_agent = orchestrator_agent

# ===========================================================================
# 5. EXECUTION & CLI
# ===========================================================================

if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("💰 FinOps Command Center — Combined Agent Module")
    print("=" * 60)
    print(f"Agent loaded: {root_agent.name}")
    print(f"Sub-agents: {[sa.name for sa in root_agent.sub_agents]}")
    print("This file can be run directly using 'adk web combined_agent' after setting up '.env'.")
    print("=" * 60)
