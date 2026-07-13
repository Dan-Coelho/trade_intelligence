# risk/forms.py — Formulário de gestão de risco
#
# Tarefa 7.5.1 — RiskForm: campos de capital, win_rate, avg_win, avg_loss e ticker

from django import forms


class RiskForm(forms.Form):
    """
    Formulário para cálculo de position sizing baseado em Kelly simplificado e ATR.

    Campos:
        ticker      — ticker do ativo (ex: PETR4, WINFUT)
        user_capital — capital disponível do usuário em R$
        win_rate    — taxa de acerto histórica (0–100%)
        avg_win     — ganho médio por operação vencedora em R$
        avg_loss    — perda média por operação perdedora em R$
    """

    ticker = forms.CharField(
        max_length=20,
        required=True,
        label="Ticker",
        widget=forms.HiddenInput(),
        error_messages={"required": "Informe o ticker do ativo."},
    )

    user_capital = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=1,
        required=True,
        label="Capital disponível (R$)",
        error_messages={
            "required": "Informe o capital disponível.",
            "min_value": "O capital deve ser maior que zero.",
        },
    )

    win_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=1,
        max_value=99,
        required=False,
        initial=55,
        label="Taxa de acerto (%)",
        help_text="Porcentagem de operações vencedoras (ex: 55 = 55%).",
    )

    avg_win = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=0.01,
        required=False,
        initial=200,
        label="Ganho médio por trade (R$)",
        help_text="Resultado médio de operações vencedoras em R$.",
    )

    avg_loss = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=0.01,
        required=False,
        initial=100,
        label="Perda média por trade (R$)",
        help_text="Resultado médio de operações perdedoras em R$.",
    )

    def clean_ticker(self):
        return self.cleaned_data["ticker"].strip().upper()

    def clean_win_rate(self):
        value = self.cleaned_data.get("win_rate")
        if value is None:
            return 55  # padrão
        return value

    def clean_avg_win(self):
        value = self.cleaned_data.get("avg_win")
        if value is None:
            return 200  # padrão
        return value

    def clean_avg_loss(self):
        value = self.cleaned_data.get("avg_loss")
        if value is None:
            return 100  # padrão
        return value
