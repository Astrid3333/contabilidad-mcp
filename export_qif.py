"""
export_qif.py — Exporta transacciones a formato QIF (Quicken Interchange
Format), compatible con importación directa en GnuCash y KMyMoney.

QIF organiza las transacciones por cuenta. Cada cuenta se exporta como un
bloque separado con sus movimientos. Tanto GnuCash (Archivo > Importar >
Transacciones QIF) como KMyMoney (Archivo > Importar > QIF) lo leen sin
problemas.

Referencia de formato QIF:
    !Type:Bank          -> tipo de cuenta (usamos Bank para todo, es lo más compatible)
    D<fecha>            -> fecha MM/DD/YYYY
    T<monto>            -> monto (positivo=ingreso a la cuenta, negativo=egreso)
    P<descripcion>      -> payee / descripción
    L<categoria>        -> categoría (la cuenta contraparte)
    M<memo>             -> memo opcional (referencia)
    ^                   -> fin de transacción
"""

from datetime import datetime
from db import get_conn
from accounting import DEBIT_NORMAL, _get_account, AccountingError


def _to_qif_date(date_str: str) -> str:
    """Convierte YYYY-MM-DD a MM/DD/YYYY (formato QIF estándar)."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%m/%d/%Y")


def export_account_qif(account: str, from_date: str = None, to_date: str = None) -> str:
    """
    Genera el contenido QIF para una cuenta específica.
    Para cada línea de un asiento en esta cuenta, busca la(s) cuenta(s)
    contraparte del mismo asiento para usarlas como categoría.
    """
    with get_conn() as conn:
        acc_row = _get_account(conn, account)
        is_debit_normal = acc_row["type"] in DEBIT_NORMAL

        q = """
            SELECT je.id as entry_id, je.date, je.description, je.reference,
                   jl.debit, jl.credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE jl.account_id = ?
        """
        params = [acc_row["id"]]
        if from_date:
            q += " AND je.date >= ?"
            params.append(from_date)
        if to_date:
            q += " AND je.date <= ?"
            params.append(to_date)
        q += " ORDER BY je.date, je.id"
        lines = conn.execute(q, params).fetchall()

        qif_lines = ["!Type:Bank"]
        for l in lines:
            amount = (l["debit"] - l["credit"]) if is_debit_normal else (l["credit"] - l["debit"])

            # Buscar cuenta(s) contraparte del mismo asiento para usarlas de categoría
            counterparts = conn.execute(
                """SELECT a.name FROM journal_lines jl2
                   JOIN accounts a ON a.id = jl2.account_id
                   WHERE jl2.entry_id = ? AND jl2.account_id != ?""",
                (l["entry_id"], acc_row["id"]),
            ).fetchall()
            category = counterparts[0]["name"] if counterparts else "Sin categoría"

            qif_lines.append(f"D{_to_qif_date(l['date'])}")
            qif_lines.append(f"T{amount:.2f}")
            qif_lines.append(f"P{l['description']}")
            qif_lines.append(f"L{category}")
            if l["reference"]:
                qif_lines.append(f"M{l['reference']}")
            qif_lines.append("^")

    return "\n".join(qif_lines) + "\n"


def export_all_accounts_qif(from_date: str = None, to_date: str = None) -> dict:
    """
    Exporta todas las cuentas con movimientos a QIF.
    Devuelve un dict {nombre_cuenta: contenido_qif} ya que cada cuenta es
    un archivo/sección QIF independiente (así lo esperan GnuCash/KMyMoney).
    """
    with get_conn() as conn:
        accounts = conn.execute("SELECT code, name FROM accounts WHERE active = 1 ORDER BY code").fetchall()

    result = {}
    for a in accounts:
        content = export_account_qif(a["code"], from_date, to_date)
        # Solo incluir cuentas que tengan al menos una transacción real
        if content.count("^") > 0:
            result[f"{a['code']}_{a['name']}"] = content
    return result
