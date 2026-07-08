# market_data/utils.py — Utilitários do app market_data
#
# Tarefa 4.2.3 — Lógica de rollover de contratos futuros WIN e WDO da B3

from datetime import date


# ── Mapeamento de meses de vencimento B3 ────────────────────────────────────
# Contratos WIN/WDO vencem na 3ª segunda-feira dos meses:
# Fevereiro (G), Abril (J), Junho (M), Agosto (Q), Outubro (V), Dezembro (Z)
_EXPIRY_MONTH_CODES = {
    2: 'G',
    4: 'J',
    6: 'M',
    8: 'Q',
    10: 'V',
    12: 'Z',
}

# Meses de vencimento em ordem
_EXPIRY_MONTHS = sorted(_EXPIRY_MONTH_CODES.keys())


def _next_expiry_month(reference: date) -> tuple[int, int]:
    """
    Retorna (ano, mês) do próximo mês de vencimento a partir de `reference`.

    B3 usa o critério de rollover: na semana de vencimento (3ª semana do mês)
    o mercado já negocia o contrato do próximo vencimento. Esta função retorna
    o mês de vencimento atual ou próximo de forma conservadora.
    """
    year = reference.year
    month = reference.month

    for expiry_month in _EXPIRY_MONTHS:
        if expiry_month >= month:
            return year, expiry_month

    # Todos os vencimentos do ano corrente já passaram → pula para fevereiro do próximo ano
    return year + 1, 2


def get_active_contract(asset_type: str, reference: date | None = None) -> str:
    """
    Retorna o ticker do contrato ativo para WIN (Ibovespa Futuro) ou WDO (Dólar Futuro).

    A B3 nomeia contratos futuros com o padrão:
        <raiz><código_mês><ano_2_dígitos>
    Exemplos: WINM25, WDOQ25

    Args:
        asset_type: 'WIN' ou 'WDO' (case-insensitive)
        reference:  Data de referência para cálculo do vencimento.
                    Padrão: data de hoje (date.today())

    Returns:
        Ticker do contrato ativo, ex: 'WINM25'

    Raises:
        ValueError: se asset_type não for 'WIN' ou 'WDO'

    Exemplos:
        >>> get_active_contract('WIN')   # em maio/2025 → 'WINM25'
        >>> get_active_contract('WDO')   # em maio/2025 → 'WDOM25'
    """
    asset_type = asset_type.upper().strip()

    if asset_type not in ('WIN', 'WDO'):
        raise ValueError(
            f'asset_type deve ser "WIN" ou "WDO", recebido: "{asset_type}"'
        )

    if reference is None:
        reference = date.today()

    expiry_year, expiry_month = _next_expiry_month(reference)
    month_code = _EXPIRY_MONTH_CODES[expiry_month]
    year_suffix = str(expiry_year)[-2:]  # ex: 2025 → '25'

    return f'{asset_type}{month_code}{year_suffix}'
