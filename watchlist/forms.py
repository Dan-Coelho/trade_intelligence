# watchlist/forms.py — Formulários do app watchlist
#
# Tarefa 7.4.1 — PriceAlertForm(forms.ModelForm):
#   Campos: condition, target_price
#   Meta: model = PriceAlert, fields = [...]

from django import forms

from watchlist.models import PriceAlert


class PriceAlertForm(forms.ModelForm):
    """
    Formulário para criação de alertas de preço.

    Campos expostos ao usuário:
        condition    — Condição do alerta: ABOVE (acima de) ou BELOW (abaixo de).
        target_price — Preço alvo em R$ (decimal com até 6 casas).

    O `asset` e o `user` são preenchidos automaticamente pela view
    (não expostos no formulário para segurança).

    Validação:
        - target_price deve ser positivo.
    """

    class Meta:
        model  = PriceAlert
        fields = ['condition', 'target_price']
        widgets = {
            'condition': forms.Select(attrs={
                'id':    'alert-condition',
                'class': 'alert-input',
            }),
            'target_price': forms.NumberInput(attrs={
                'id':          'alert-target-price',
                'class':       'alert-input',
                'placeholder': '0.00',
                'step':        '0.01',
                'min':         '0.000001',
            }),
        }
        labels = {
            'condition':    'Condição',
            'target_price': 'Preço Alvo (R$)',
        }

    def clean_target_price(self):
        price = self.cleaned_data.get('target_price')
        if price is not None and price <= 0:
            raise forms.ValidationError('O preço alvo deve ser maior que zero.')
        return price
