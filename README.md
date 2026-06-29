# contabilidad-mcp

Servidor MCP de contabilidad de partida doble (double-entry) para Claude Desktop.
Generico e internacional — funciona para cualquier moneda y jurisdiccion.

## Caracteristicas

- Cuentas: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
- Asientos con validacion de balance (debitos = creditos)
- Libro mayor, balance de comprobacion, P&L, balance general
- Resumen de IVA configurable (por defecto 19%)
- Exportacion QIF para GnuCash y KMyMoney
- SQLite local (cero configuracion)

## Instalacion

    git clone https://github.com/Astrid3333/contabilidad-mcp.git
    cd contabilidad-mcp
    pip install -r requirements.txt

## Configuracion Claude Desktop

Agrega a ~/.config/Claude/claude_desktop_config.json:

    "contabilidad": {
      "command": "python3",
      "args": ["/home/astrid/contabilidad-mcp/server.py"],
      "env": {
        "ACCOUNTING_DB_PATH": "/home/astrid/contabilidad-mcp/contabilidad.db"
      }
    }

## Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| crear_cuenta | Crea una cuenta contable |
| listar_cuentas | Lista cuentas (filtrable por tipo) |
| saldo_cuenta | Saldo actual de una cuenta |
| registrar_transaccion | Registra un asiento de partida doble |
| libro_mayor | Movimientos de una cuenta |
| balance_comprobacion | Trial balance |
| estado_resultados | P&L para un periodo |
| balance_general | Balance sheet a una fecha |
| resumen_iva | Calculo de IVA del periodo |
| exportar_qif | Exporta cuenta a formato QIF |
| exportar_todas_qif | Exporta todas las cuentas a QIF |

## Ejemplo de asiento

    registrar_transaccion(
      fecha="2026-06-01",
      descripcion="Venta boleta 0001",
      lineas=[
        {"account": "1000", "debit": 1190, "credit": 0},
        {"account": "4000", "debit": 0,    "credit": 1000},
        {"account": "2100", "debit": 0,    "credit": 190},
      ]
    )

## Contexto

Construido en Castro, Chiloe, Region de Los Lagos, Chile.
Parte del ecosistema MCP: https://github.com/Astrid3333/mcp-ecosystem-chiloe

## Licencia

MIT
