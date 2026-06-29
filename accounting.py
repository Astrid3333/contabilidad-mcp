"""
accounting.py — Lógica de negocio del MCP de Contabilidad.

Toda la lógica vive aquí, separada de las herramientas MCP (server.py),
para que se pueda testear sin depender de FastMCP.
"""

from datetime import datetime
from db import get_conn, ACCOUNT_TYPES

DEBIT_NORMAL = ("ASSET", "EXPENSE")     # tipos cuyo saldo normal es deudor
CREDIT_NORMAL = ("LIABILITY", "EQUITY", "REVENUE")  # saldo normal acreedor


class AccountingError(Exception):
    pass


# ---------------------------------------------------------------------------
# Cuentas
# ---------------------------------------------------------------------------

def create_account(code: str, name: str, type_: str, taxable: bool = False) -> dict:
    type_ = type_.upper()
    if type_ not in ACCOUNT_TYPES:
        raise AccountingError(f"Tipo de cuenta inválido: {type_}. Use uno de {ACCOUNT_TYPES}")
    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO accounts (code, name, type, taxable) VALUES (?, ?, ?, ?)",
                (code, name, type_, int(taxable)),
            )
            conn.commit()
        except Exception as e:
            raise AccountingError(f"No se pudo crear la cuenta: {e}")
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_accounts(only_active: bool = True) -> list[dict]:
    with get_conn() as conn:
        q = "SELECT * FROM accounts"
        if only_active:
            q += " WHERE active = 1"
        q += " ORDER BY code"
        return [dict(r) for r in conn.execute(q).fetchall()]


def _get_account(conn, identifier: str):
    """Busca una cuenta por código o por nombre (case-insensitive)."""
    row = conn.execute("SELECT * FROM accounts WHERE code = ?", (identifier,)).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT * FROM accounts WHERE lower(name) = lower(?)", (identifier,)
        ).fetchone()
    if row is None:
        raise AccountingError(f"Cuenta no encontrada: '{identifier}'")
    return row


# ---------------------------------------------------------------------------
# Transacciones (asientos de partida doble)
# ---------------------------------------------------------------------------

def record_transaction(date: str, description: str, lines: list[dict], reference: str | None = None) -> dict:
    """
    lines: [{"account": "1000", "debit": 1000, "credit": 0}, ...]
    La suma de débitos debe ser igual a la suma de créditos (tolerancia 0.01).
    """
    if not lines or len(lines) < 2:
        raise AccountingError("Un asiento requiere al menos 2 líneas (débito y crédito).")

    total_debit = sum(float(l.get("debit", 0)) for l in lines)
    total_credit = sum(float(l.get("credit", 0)) for l in lines)
    if abs(total_debit - total_credit) > 0.01:
        raise AccountingError(
            f"El asiento no balancea: débitos={total_debit:.2f} vs créditos={total_credit:.2f}"
        )

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise AccountingError("La fecha debe tener formato YYYY-MM-DD")

    with get_conn() as conn:
        resolved = []
        for l in lines:
            acc = _get_account(conn, l["account"])
            debit = float(l.get("debit", 0))
            credit = float(l.get("credit", 0))
            if debit > 0 and credit > 0:
                raise AccountingError(f"La línea de '{acc['name']}' no puede tener débito y crédito a la vez")
            resolved.append((acc["id"], debit, credit))

        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date, description, reference),
        )
        entry_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO journal_lines (entry_id, account_id, debit, credit) VALUES (?, ?, ?, ?)",
            [(entry_id, acc_id, d, c) for acc_id, d, c in resolved],
        )
        conn.commit()

    return {"entry_id": entry_id, "date": date, "description": description,
            "total": total_debit, "lines": len(lines)}


def get_ledger(account: str, from_date: str | None = None, to_date: str | None = None) -> dict:
    """Libro mayor de una cuenta: lista de movimientos y saldo acumulado."""
    with get_conn() as conn:
        acc = _get_account(conn, account)
        q = """
            SELECT je.date, je.description, je.reference, jl.debit, jl.credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE jl.account_id = ?
        """
        params = [acc["id"]]
        if from_date:
            q += " AND je.date >= ?"
            params.append(from_date)
        if to_date:
            q += " AND je.date <= ?"
            params.append(to_date)
        q += " ORDER BY je.date, je.id"
        rows = conn.execute(q, params).fetchall()

    is_debit_normal = acc["type"] in DEBIT_NORMAL
    balance = 0.0
    movements = []
    for r in rows:
        delta = (r["debit"] - r["credit"]) if is_debit_normal else (r["credit"] - r["debit"])
        balance += delta
        movements.append({
            "date": r["date"], "description": r["description"], "reference": r["reference"],
            "debit": r["debit"], "credit": r["credit"], "balance": round(balance, 2),
        })

    return {"account": acc["name"], "code": acc["code"], "type": acc["type"],
            "movements": movements, "ending_balance": round(balance, 2)}


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def _account_balances(conn, as_of_date: str | None = None) -> list[dict]:
    q = """
        SELECT a.id, a.code, a.name, a.type,
               COALESCE(SUM(jl.debit), 0) AS total_debit,
               COALESCE(SUM(jl.credit), 0) AS total_credit
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_id = a.id
        LEFT JOIN journal_entries je ON je.id = jl.entry_id
    """
    params = []
    if as_of_date:
        q += " AND je.date <= ?"
        params.append(as_of_date)
    q += " WHERE a.active = 1 GROUP BY a.id ORDER BY a.code"

    # nota: el LEFT JOIN con filtro de fecha en ON requiere reescribir si as_of_date es None
    if as_of_date is None:
        q = q.replace("AND je.date <= ?", "")

    results = []
    for r in conn.execute(q, params).fetchall():
        is_debit_normal = r["type"] in DEBIT_NORMAL
        balance = (r["total_debit"] - r["total_credit"]) if is_debit_normal else (r["total_credit"] - r["total_debit"])
        results.append({
            "code": r["code"], "name": r["name"], "type": r["type"], "balance": round(balance, 2),
        })
    return results


def trial_balance(as_of_date: str | None = None) -> dict:
    """Balance de comprobación: todas las cuentas con su saldo."""
    with get_conn() as conn:
        balances = _account_balances(conn, as_of_date)
    total_debit_side = sum(b["balance"] for b in balances if b["type"] in DEBIT_NORMAL)
    total_credit_side = sum(b["balance"] for b in balances if b["type"] in CREDIT_NORMAL)
    return {
        "as_of_date": as_of_date or "hoy",
        "accounts": balances,
        "total_debit_side": round(total_debit_side, 2),
        "total_credit_side": round(total_credit_side, 2),
        "balanced": abs(total_debit_side - total_credit_side) < 0.01,
    }


def balance_sheet(as_of_date: str | None = None) -> dict:
    """Balance general: Activos = Pasivos + Patrimonio."""
    with get_conn() as conn:
        balances = _account_balances(conn, as_of_date)
    assets = [b for b in balances if b["type"] == "ASSET"]
    liabilities = [b for b in balances if b["type"] == "LIABILITY"]
    equity = [b for b in balances if b["type"] == "EQUITY"]

    total_assets = round(sum(b["balance"] for b in assets), 2)
    total_liabilities = round(sum(b["balance"] for b in liabilities), 2)
    total_equity = round(sum(b["balance"] for b in equity), 2)

    return {
        "as_of_date": as_of_date or "hoy",
        "assets": assets, "total_assets": total_assets,
        "liabilities": liabilities, "total_liabilities": total_liabilities,
        "equity": equity, "total_equity": total_equity,
        "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
    }


def income_statement(from_date: str, to_date: str) -> dict:
    """Estado de resultados (P&L) entre dos fechas."""
    with get_conn() as conn:
        q = """
            SELECT a.code, a.name, a.type,
                   COALESCE(SUM(jl.debit), 0) AS total_debit,
                   COALESCE(SUM(jl.credit), 0) AS total_credit
            FROM accounts a
            LEFT JOIN journal_lines jl ON jl.account_id = a.id
            LEFT JOIN journal_entries je ON je.id = jl.entry_id AND je.date BETWEEN ? AND ?
            WHERE a.type IN ('REVENUE', 'EXPENSE') AND a.active = 1
            GROUP BY a.id ORDER BY a.code
        """
        rows = conn.execute(q, (from_date, to_date)).fetchall()

    revenue, expense = [], []
    for r in rows:
        is_debit_normal = r["type"] in DEBIT_NORMAL
        balance = (r["total_debit"] - r["total_credit"]) if is_debit_normal else (r["total_credit"] - r["total_debit"])
        item = {"code": r["code"], "name": r["name"], "amount": round(balance, 2)}
        (expense if r["type"] == "EXPENSE" else revenue).append(item)

    total_revenue = round(sum(i["amount"] for i in revenue), 2)
    total_expense = round(sum(i["amount"] for i in expense), 2)
    net_income = round(total_revenue - total_expense, 2)

    return {
        "from_date": from_date, "to_date": to_date,
        "revenue": revenue, "total_revenue": total_revenue,
        "expense": expense, "total_expense": total_expense,
        "net_income": net_income,
    }


# ---------------------------------------------------------------------------
# Categorización automática
# ---------------------------------------------------------------------------

def add_category_rule(keyword: str, account: str) -> dict:
    with get_conn() as conn:
        acc = _get_account(conn, account)
        conn.execute(
            "INSERT INTO category_rules (keyword, account_id) VALUES (?, ?)",
            (keyword.lower(), acc["id"]),
        )
        conn.commit()
    return {"keyword": keyword.lower(), "account": acc["name"]}


def suggest_category(description: str) -> dict | None:
    """Sugiere una cuenta según reglas de palabras clave guardadas."""
    desc_lower = description.lower()
    with get_conn() as conn:
        rules = conn.execute(
            """SELECT cr.keyword, a.code, a.name FROM category_rules cr
               JOIN accounts a ON a.id = cr.account_id"""
        ).fetchall()
    for rule in rules:
        if rule["keyword"] in desc_lower:
            return {"matched_keyword": rule["keyword"], "suggested_account": rule["name"], "code": rule["code"]}
    return None


# ---------------------------------------------------------------------------
# Impuestos (genérico, tipo IVA)
# ---------------------------------------------------------------------------

def calculate_tax(from_date: str, to_date: str, tax_rate: float) -> dict:
    """
    Calcula impuesto genérico (ej. IVA) sobre cuentas marcadas como taxable=1.
    tax_rate: ej. 0.19 para 19%.
    Devuelve impuesto débito (sobre ventas/revenue) e impuesto crédito
    (sobre compras/expense), y el neto a pagar.
    """
    with get_conn() as conn:
        q = """
            SELECT a.type, COALESCE(SUM(jl.debit), 0) AS total_debit,
                   COALESCE(SUM(jl.credit), 0) AS total_credit
            FROM accounts a
            LEFT JOIN journal_lines jl ON jl.account_id = a.id
            LEFT JOIN journal_entries je ON je.id = jl.entry_id AND je.date BETWEEN ? AND ?
            WHERE a.taxable = 1 AND a.active = 1
            GROUP BY a.type
        """
        rows = conn.execute(q, (from_date, to_date)).fetchall()

    revenue_base = 0.0
    expense_base = 0.0
    for r in rows:
        if r["type"] == "REVENUE":
            revenue_base += r["total_credit"] - r["total_debit"]
        elif r["type"] == "EXPENSE":
            expense_base += r["total_debit"] - r["total_credit"]

    tax_on_sales = round(revenue_base * tax_rate, 2)
    tax_on_purchases = round(expense_base * tax_rate, 2)
    net_tax = round(tax_on_sales - tax_on_purchases, 2)

    return {
        "from_date": from_date, "to_date": to_date, "tax_rate": tax_rate,
        "taxable_revenue": round(revenue_base, 2), "tax_on_sales": tax_on_sales,
        "taxable_expense": round(expense_base, 2), "tax_on_purchases": tax_on_purchases,
        "net_tax_payable": net_tax,
        "note": "Positivo = a pagar. Negativo = crédito a favor.",
    }
