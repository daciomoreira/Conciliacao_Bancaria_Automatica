import pandas as pd
import ofxparse
import os
import io
from datetime import datetime

def ler_ofx(file_obj):
    """Lê o arquivo OFX a partir de um objeto file-like com tratamento de encoding"""
    try:
        # Tenta ler como UTF-8 primeiro
        try:
            file_content = file_obj.getvalue().decode('utf-8')
        except UnicodeDecodeError:
            # Se falhar, tenta ISO-8859-1 (Latin-1)
            file_obj.seek(0)
            file_content = file_obj.getvalue().decode('iso-8859-1')
        
        file_content = ajustar_formato_ofx(file_content)
        
        file_obj = io.StringIO(file_content)
        ofx = ofxparse.OfxParser.parse(file_obj)
        
        transacoes = []
        for conta in ofx.accounts:
            for t in conta.statement.transactions:
                transacoes.append({
                    "data": t.date,
                    "valor": float(t.amount),
                    "descricao": t.memo.strip() if t.memo else "",
                    "receita": max(float(t.amount), 0),
                    "despesa": abs(min(float(t.amount), 0))
                })
        
        transacoes.sort(key=lambda x: x["data"] if x["data"] else datetime.now())
        return transacoes
    
    except Exception as e:
        raise ValueError(f"Erro ao processar arquivo OFX: {str(e)}")


def ajustar_formato_ofx(content: str) -> str:
    """
    Ajusta o conteúdo do arquivo OFX para lidar com variações conhecidas,
    como a ausência de quebras de linha ou a presença de BOM.
    """
    if content.startswith('\ufeff'):
        content = content.lstrip('\ufeff')
    
    if "OFXHEADER" in content and not content.startswith("<?xml"):
        partes = content.split("<OFX>")
        if len(partes) > 1:
            cabecalho = partes[0].strip()
            corpo = "<OFX>" + partes[1]
            cabecalho = "\n".join(cabecalho.splitlines())
            content = f"{cabecalho}\n{corpo}"
    
    return content


def carregar_relatorio_dataframe(file_obj, filename):
    """Carrega diferentes formatos de relatório com tratamento de encoding"""
    extensao = os.path.splitext(filename)[1].lower()
    
    try:
        if extensao == '.csv':
            for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
                try:
                    file_obj.seek(0)
                    df = pd.read_csv(file_obj, encoding=encoding, on_bad_lines='skip', engine='python', sep=None)
                    if not df.empty:
                        return df
                except Exception:
                    try:
                        file_obj.seek(0)
                        df = pd.read_csv(file_obj, encoding=encoding, on_bad_lines='skip', engine='python', sep=";")
                        if not df.empty:
                            return df
                    except Exception:
                        continue
            raise ValueError("Não foi possível determinar o encoding ou o separador do arquivo CSV")
            
        elif extensao in ['.xls', '.xlsx']:
            # Ler tudo como string
            return pd.read_excel(file_obj, dtype=str, engine='openpyxl')
        else:
            raise ValueError("Formato não suportado")
            
    except Exception as e:
        raise ValueError(f"Erro ao carregar arquivo: {str(e)}")


def parse_valor(valor_str: str) -> float:
    """
    Converte uma string numérica para float, removendo símbolos de moeda,
    espaços e ajustando separadores decimais.
    """
    valor_str = str(valor_str).strip().replace("R$", "").replace(" ", "")
    if not valor_str:
        return 0.0
    
    if valor_str.count(",") == 1 and valor_str.count(".") == 0:
        valor_str = valor_str.replace(",", ".")
    elif valor_str.count(",") == 1 and valor_str.count(".") >= 1:
        valor_str = valor_str.replace(".", "").replace(",", ".")
    try:
        return float(valor_str)
    except:
        return 0.0


def parse_data_dd_mm_aaaa(data_str: str):
    """
    Converte uma string de data que está (supostamente) em DD/MM/AAAA.
    Se não bater com esse formato, retorna None.
    """
    data_str = str(data_str).strip()
    if not data_str:
        return None
    try:
        # Força o formato dd/mm/yyyy
        dt = datetime.strptime(data_str, "%d/%m/%Y")
        return dt
    except:
        return None


def converter_dataframe(df, colunas_mapeadas, tipo_relatorio, filtro_conta=None):
    """Converte DataFrame do relatório para formato interno"""
    transacoes = []
    
    for _, row in df.iterrows():
        # Extração dos dados
        data_str = row.get(colunas_mapeadas['data'], '')
        desc_str = str(row.get(colunas_mapeadas['descricao'], '')).strip()
        conta_str = str(row.get(colunas_mapeadas['conta'], '')).strip()
        
        # Força parse de data como DD/MM/YYYY
        data_convertida = parse_data_dd_mm_aaaa(data_str)
        
        # Cálculo dos valores
        if tipo_relatorio == "Única coluna com Natureza (C/D)":
            valor_str = row.get(colunas_mapeadas['valor'], '')
            natureza_str = str(row.get(colunas_mapeadas['natureza'], '')).strip().upper()
            
            valor = parse_valor(valor_str)
            
            if natureza_str == 'D':
                valor = -abs(valor)
            elif natureza_str == 'C':
                valor = abs(valor)
            
            receita = max(valor, 0.0)
            despesa = abs(min(valor, 0.0))
        else:
            receita_str = row.get(colunas_mapeadas['receita'], '')
            despesa_str = row.get(colunas_mapeadas['despesa'], '')
            
            receita = parse_valor(receita_str)
            despesa = parse_valor(despesa_str)
            valor = receita - despesa

        transacoes.append({
            "data": data_convertida,
            "valor": valor,
            "receita": receita,
            "despesa": despesa,
            "descricao": desc_str,
            "conta": conta_str
        })
    
    if filtro_conta:
        transacoes = [t for t in transacoes if t["conta"] == filtro_conta]
    
    transacoes.sort(key=lambda x: x["data"] if x["data"] else datetime.now())
    return transacoes
