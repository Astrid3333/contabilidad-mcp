import os, sys, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["ACCOUNTING_DB_PATH"] = "/tmp/test_contabilidad.db"
import db
import accounting as acc

@pytest.fixture(autouse=True)
def fresh_db():
    path = os.environ["ACCOUNTING_DB_PATH"]
    if os.path.exists(path):
        os.remove(path)
    db.init_db()
    yield
    if os.path.exists(path):
        os.remove(path)

def chart():
    acc.create_account("1000", "Caja", "ASSET")
    acc.create_account("2100", "IVA debito", "LIABILITY")
    acc.create_account("3000", "Capital", "EQUITY")
    acc.create_account("4000", "Ventas", "REVENUE")
    acc.create_account("5200", "Arriendo", "EXPENSE")

def test_crear_cuenta():
    r = acc.create_account("1000", "Caja", "ASSET")
    assert r["code"] == "1000"

def test_tipo_invalido():
    with pytest.raises(acc.AccountingError):
        acc.create_account("9999", "Mala", "INVALIDO")

def test_asiento_balanceado():
    chart()
    r = acc.record_transaction("2026-06-01", "Venta", [
        {"account": "1000", "debit": 1190, "credit": 0},
        {"account": "4000", "debit": 0, "credit": 1000},
        {"account": "2100", "debit": 0, "credit": 190},
    ])
    assert r["id"] is not None

def test_asiento_desbalanceado():
    chart()
    with pytest.raises(acc.AccountingError):
        acc.record_transaction("2026-06-01", "Mal", [
            {"account": "1000", "debit": 500, "credit": 0},
            {"account": "4000", "debit": 0, "credit": 300},
        ])

def test_saldo_cuenta():
    chart()
    acc.record_transaction("2026-06-01", "Venta", [
        {"account": "1000", "debit": 1190, "credit": 0},
        {"account": "4000", "debit": 0, "credit": 1000},
        {"account": "2100", "debit": 0, "credit": 190},
    ])
    assert acc.account_balance("1000")["balance"] == 1190

def test_estado_resultados():
    chart()
    acc.record_transaction("2026-06-01", "Venta", [
        {"account": "1000", "debit": 1190, "credit": 0},
        {"account": "4000", "debit": 0, "credit": 1000},
        {"account": "2100", "debit": 0, "credit": 190},
    ])
    acc.record_transaction("2026-06-05", "Arriendo", [
        {"account": "5200", "debit": 300, "credit": 0},
        {"account": "1000", "debit": 0, "credit": 300},
    ])
    er = acc.income_statement("2026-06-01", "2026-06-30")
    assert er["net_income"] == 700
