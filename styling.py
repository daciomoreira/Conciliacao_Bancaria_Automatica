import pandas as pd

def colorir_linhas(df):
    """
    Aplica cores às linhas do DataFrame com base no status de conciliação.
    - Verde: Conciliado
    - Amarelo: Conciliado (Soma)
    - Vermelho: Não conciliado
    """
    return df.style.apply(
        lambda row: [
            'background-color: #c8e6c9' if row['Status'] == 'Conciliado' else
            'background-color: #fff9c4' if row['Status'] == 'Conciliado (Soma)' else
            'background-color: #ffcdd2' if 'Não conciliado' in str(row['Status']) else
            ''
            for _ in row
        ],
        axis=1
    )

def colorir_linhas_agregado(df, tags):
    """
    Aplica cores às linhas do DataFrame agregado com base na coluna Status (índice 6).
    - Verde: Conciliado
    - Amarelo: Conciliado (Soma)
    - Vermelho: Não conciliado ou qualquer outro valor
    """
    return df.style.apply(
        lambda row: [
            'background-color: #c8e6c9' if 'Conciliado' in str(row[6]) and 'Soma' not in str(row[6]) and 'Não' not in str(row[6]) else
            'background-color: #fff9c4' if 'Conciliado (Soma)' in str(row[6]) else
            'background-color: #ffcdd2'
            for _ in row
        ],
        axis=1
    )