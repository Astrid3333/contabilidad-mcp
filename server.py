"""
server.py — Servidor MCP de Contabilidad (FastMCP).

Expone todas las funciones de accounting.py como herramientas MCP,
consumibles desde Claude Desktop.
"""

from fastmcp import FastMCP
import db
import accounting as acc
import export_qif as qif

db.init_db()
mcp = FastMCP("contabilidad-mcp")


# ── Cuentas ────────────────────────────────────────────────────────────────

@mcp.tool()
def crear_cuenta(codigo: str, nombre: str, tipo: str, gravable: bool = False) -> dict:
    """
    Crea una cuenta contable.
    tipo: ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
    """
    return acc.create_account(codigo, nombre, tipo, gravable)


@mcp.tool()
def listar_cuentas(tipo: str = None) -> list:
    """Lista todas las cuentas. Filtra por tipo si se especifica."""
    return acc.list_accounts(tipo)


@mcp.tool()
def saldo_cuenta(codigo: str) -> dict:
    """Retorna el saldo actual de una cuenta."""
    return acc.account_balance(codigo)


# ── Transacciones ──────────────────────────────────────────────────────────

@mcp.tool()
def registrar_transaccion(fecha: str, descripcion: str, lineas: list, referencia: str = None) -> dict:
    """
    Registra un asiento contable de partida doble.
    fecha: YYYY-MM-DD
    lineas: [{"account": "1000", "debit": 100, "credit": 0}, ...]
    La suma de débitos debe ser igual a la suma de créditos.
    """
    return acc.record_transaction(fecha, descripcion, lineas, referencia)


@mcp.tool()
def libro_mayor(codigo_cuenta: str, desde: str = None, hasta: str = None) -> list:
    """
    Retorna el libro mayor de una cuenta (todos sus movimientos).
    desde/hasta: YYYY-MM-DD (opcionales)
    """
    return acc.general_ledger(codigo_cuenta, desde, hasta)


@mcp.tool()
def balance_comprobacion(desde: str = None, hasta: str = None) -> list:
    """Balance de comprobación (trial balance): saldos de todas las cuentas."""
    return acc.trial_balance(desde, hasta)


# ── Reportes ───────────────────────────────────────────────────────────────

@mcp.tool()
def estado_resultados(desde: str, hasta: str) -> dict:
    """
    Estado de resultados (P&L) para el período dado.
    desde/hasta: YYYY-MM-DD
    """
    return acc.income_statement(desde, hasta)


@mcp.tool()
def balance_general(fecha: str) -> dict:
    """
    Balance general (balance sheet) a una fecha dada.
    fecha: YYYY-MM-DD
    """
    return acc.balance_sheet(fecha)


# ── Impuestos ──────────────────────────────────────────────────────────────

@mcp.tool()
def resumen_iva(desde: str, hasta: str, tasa: float = 0.19) -> dict:
    """
    Resumen de IVA para el período. tasa por defecto 19% (Chile/UE).
    Retorna: base_gravable, iva_calculado, total.
    """
    return acc.tax_summary(desde, hasta, tasa)


# ── Exportación ────────────────────────────────────────────────────────────

@mcp.tool()
def exportar_qif(codigo_cuenta: str) -> str:
    """
    Exporta los movimientos de una cuenta en formato QIF
    (compatible con GnuCash y KMyMoney).
    """
    return qif.export_account_qif(codigo_cuenta)


@mcp.tool()
def exportar_todas_qif() -> str:
    """Exporta todas las cuentas en un único archivo QIF."""
    return qif.export_all_qif()


if __name__ == "__main__":
    mcp.run()
