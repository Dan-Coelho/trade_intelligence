# backtest/forms.py — Formulário de configuração de backtest
#
# Tarefa 7.3.1 — BacktestForm(forms.Form):
#   Campos: ticker, start_date, end_date, strategy, initial_capital
#   Validação clean(): start_date < end_date

from datetime import date, timedelta

from django import forms


class BacktestForm(forms.Form):
    """
    Formulário para configurar e disparar um backtest de estratégia.

    Campos:
        ticker          — Código do ativo (ex.: PETR4, WINM25).
        start_date      — Data de início do backtest.
        end_date        — Data de fim do backtest.
        strategy        — Estratégia a ser testada.
        initial_capital — Capital inicial em R$.

    Validações:
        - start_date deve ser anterior a end_date.
        - O período mínimo é de 30 dias.
        - end_date não pode ser futura.
    """

    STRATEGY_CHOICES = [
        ('sma_crossover',  'Cruzamento de Médias (SMA 9/21)'),
        ('rsi_reversal',   'Reversão por RSI (sobrecomprado/sobrevendido)'),
        ('macd_signal',    'Sinal MACD (cruzamento linha/sinal)'),
        ('bollinger_band', 'Bandas de Bollinger (breakout)'),
        ('buy_and_hold',   'Buy & Hold (benchmark)'),
    ]

    ticker = forms.CharField(
        label='Ativo',
        max_length=12,
        widget=forms.TextInput(attrs={
            'id':          'bt-ticker',
            'placeholder': 'Ex.: PETR4, WINM25',
            'class':       'bt-input',
            'autocomplete': 'off',
        }),
        help_text='Código do ativo listado na B3.',
    )

    start_date = forms.DateField(
        label='Data de Início',
        widget=forms.DateInput(attrs={
            'id':    'bt-start-date',
            'type':  'date',
            'class': 'bt-input',
        }),
        initial=date.today() - timedelta(days=365),
    )

    end_date = forms.DateField(
        label='Data de Fim',
        widget=forms.DateInput(attrs={
            'id':    'bt-end-date',
            'type':  'date',
            'class': 'bt-input',
            'max':   str(date.today()),
        }),
        initial=date.today(),
    )

    strategy = forms.ChoiceField(
        label='Estratégia',
        choices=STRATEGY_CHOICES,
        widget=forms.Select(attrs={
            'id':    'bt-strategy',
            'class': 'bt-input',
        }),
    )

    initial_capital = forms.DecimalField(
        label='Capital Inicial (R$)',
        min_value=1_000,
        max_value=10_000_000,
        decimal_places=2,
        initial=10_000,
        widget=forms.NumberInput(attrs={
            'id':    'bt-capital',
            'class': 'bt-input',
            'step':  '1000',
            'min':   '1000',
        }),
        help_text='Mínimo R$ 1.000.',
    )

    def clean(self):
        """
        Validações cruzadas:
            1. start_date < end_date.
            2. Período mínimo de 30 dias.
            3. end_date não pode ser futura.
        """
        cleaned = super().clean()
        start  = cleaned.get('start_date')
        end    = cleaned.get('end_date')

        if start and end:
            if end > date.today():
                self.add_error('end_date', 'A data de fim não pode ser futura.')

            if start >= end:
                self.add_error('start_date', 'A data de início deve ser anterior à data de fim.')

            elif (end - start).days < 30:
                self.add_error(
                    'start_date',
                    'O período do backtest deve ser de pelo menos 30 dias.',
                )

        return cleaned
