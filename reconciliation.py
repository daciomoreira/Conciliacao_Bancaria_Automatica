import re
import pandas as pd
import streamlit as st
from datetime import datetime
from itertools import combinations

class Conciliador:
    def __init__(self, trans_ofx, trans_rel):
        """
        trans_ofx: Lista de transações do extrato bancário (OFX).
        trans_rel: Lista de transações do relatório (ERP/Financeiro).
        """
        self.trans_ofx = trans_ofx
        self.trans_rel = trans_rel.copy()
        self.resultado = []
        self.nao_conciliadas_rel = trans_rel.copy()

    def executar(self):
        """
        Executa o fluxo principal de conciliação:
        1. Tenta casar transações (exato ou soma dupla).
        2. Marca as não conciliadas.
        3. Retorna um DataFrame final com as colunas:
           - Extrato Data, Extrato Valor, Extrato Descrição
           - Relatório Data, Relatório Valor, Relatório Descrição
           - Status
        """
        # Mensagens de feedback para o usuário
        st.write("🔍 IA iniciando análise de transações...")
        st.write(f"📊 Processando {len(self.trans_ofx)} transações do extrato bancário")
        st.write(f"📋 Comparando com {len(self.trans_rel)} lançamentos do relatório")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Processar conciliações com feedback
        status_text.write("🧠 Analisando padrões de transações...")
        self._processar_conciliacoes_com_feedback(progress_bar, status_text)
        
        # Processar não conciliados
        status_text.write("⚖️ Identificando transações não conciliadas...")
        self._processar_nao_conciliados()
        
        # Gerar resultado final
        status_text.write("✅ Finalizando conciliação e gerando relatório...")
        progress_bar.progress(100)
        
        df = self._gerar_dataframe()
        
        # Estatísticas finais
        conciliados = df[df['Status'].str.startswith('Conciliado')].shape[0]
        nao_conciliados = df[df['Status'] == 'Não conciliado'].shape[0]
        total = df.shape[0]
        
        taxa_conciliacao = (conciliados / total) * 100 if total > 0 else 0
        
        st.write(f"✨ Conciliação finalizada! Taxa de sucesso: {taxa_conciliacao:.1f}%")
        st.write(f"✓ {conciliados} transações conciliadas | ✗ {nao_conciliados} não conciliadas")
        
        # Adicionar resumo dos dias conciliados
        self._mostrar_resumo_dias()
        
        return df
    def _processar_conciliacoes_com_feedback(self, progress_bar, status_text):
        """
        Versão do _processar_conciliacoes com feedback visual para o usuário
        """
        nao_conciliadas_ofx = [ofx_item for ofx_item in self.trans_ofx if not any(r["ofx"] == ofx_item for r in self.resultado)]
        total = len(nao_conciliadas_ofx)
        
        for i, ofx_item in enumerate(nao_conciliadas_ofx):
            # Atualizar progresso
            progress = int((i / total) * 70)  # Usa 70% da barra para esta etapa
            progress_bar.progress(progress)
            
            # Mensagens dinâmicas para dar sensação de IA trabalhando
            if i % 5 == 0:  # A cada 5 transações, muda a mensagem
                mensagens = [
                    "🔄 Comparando padrões de transações...",
                    "🧮 Calculando correspondências exatas...",
                    "🔍 Buscando combinações de valores...",
                    "📅 Analisando datas e valores...",
                    "🧩 Verificando possíveis agrupamentos...",
                    "⚙️ Processando algoritmos de conciliação...",
                    "📊 Aplicando análise estatística...",
                    "🤖 IA trabalhando na conciliação..."
                ]
                import random
                status_text.write(random.choice(mensagens))
            
            # Mostrar detalhes da transação atual (versão simplificada)
            if i % 10 == 0:  # A cada 10 transações
                data_str = ofx_item["data"].strftime('%d/%m/%Y') if ofx_item["data"] else "N/A"
                valor_str = f"R$ {abs(ofx_item['valor']):.2f}".replace('.', ',')
                status_text.write(f"💱 Analisando transação de {data_str}: {valor_str}")
            
            # Processar a conciliação
            match = self._encontrar_melhor_match(ofx_item)
            if match:
                self._registrar_match(ofx_item, match)
        
        # Atualizar para 70% ao finalizar
        progress_bar.progress(70)
    def _encontrar_melhor_match(self, ofx_item):
        """
        Tenta encontrar uma correspondência exata ou por soma dupla
        para a transação do extrato.
        """
        data = ofx_item["data"].date() if ofx_item["data"] else None
        valor = ofx_item["valor"]
        
        exato = self._achar_match_exato(data, valor)
        if exato:
            return (exato, "Conciliado")
        
        duplo = self._achar_match_duplo(data, valor)
        if duplo:
            return (duplo, "Conciliado (Soma)")
        
        # Verificar se este item do extrato pode fazer parte de uma soma
        # que corresponde a um único item do relatório
        inverso = self._achar_match_inverso(ofx_item)
        if inverso:
            return (inverso, "Conciliado (Soma)")
        
        return None

    def _achar_match_exato(self, data, valor, tol=1e-4):
        """
        Tenta achar uma única transação do relatório que case
        com a data e o valor do extrato dentro de uma tolerância.
        """
        for r in self.nao_conciliadas_rel:
            if r["data"] and r["data"].date() == data:
                if abs(r["valor"] - valor) < tol:
                    self.nao_conciliadas_rel.remove(r)
                    return r
        return None

    def _achar_match_duplo(self, data, valor, tol=1e-4):
        """
        Tenta achar uma combinação de transações do relatório cuja soma dos valores
        case com a data e o valor do extrato dentro de uma tolerância.
        Limita o número de combinações verificadas para evitar processamento infinito.
        """
        candidatas = [r for r in self.nao_conciliadas_rel if r["data"] and r["data"].date() == data]
        max_combinations = 1000  # Limite de combinações a serem verificadas
        checked_combinations = 0
    
        for n in range(2, len(candidatas) + 1):  # Start from 2 to include pairs and more
            for combo in combinations(candidatas, n):
                if checked_combinations >= max_combinations:
                    return None  # Retorna None se o limite de combinações for atingido
                soma = sum(item["valor"] for item in combo)
                if abs(soma - valor) < tol:
                    for m in combo:
                        self.nao_conciliadas_rel.remove(m)
                    return list(combo)
                checked_combinations += 1
        return None
        
    def _achar_match_inverso(self, ofx_item, tol=1e-4):
        """
        Verifica se este item do extrato, combinado com outros itens do extrato,
        pode corresponder a um único item do relatório.
        Útil para casos como múltiplas tarifas no extrato que somam uma única tarifa no relatório.
        """
        data = ofx_item["data"].date() if ofx_item["data"] else None
        if not data:
            return None
            
        # Encontrar outros itens do extrato com a mesma data que ainda não foram conciliados
        itens_mesma_data = [
            item for item in self.trans_ofx 
            if item["data"] and item["data"].date() == data
            and not any(r["ofx"] == item for r in self.resultado)
            and item != ofx_item  # Excluir o próprio item
        ]
        
        # Adicionar o item atual à lista
        todos_itens = [ofx_item] + itens_mesma_data
        
        # Verificar combinações de 2 a N itens (limitado a combinações razoáveis)
        max_combinacoes = min(5, len(todos_itens))  # Limitar para evitar explosão combinatória
        
        for n in range(2, max_combinacoes + 1):
            for combo in combinations(todos_itens, n):
                # Se o item atual não estiver na combinação, pular
                if ofx_item not in combo:
                    continue
                    
                soma_extrato = sum(item["valor"] for item in combo)
                
                # Procurar um item no relatório com valor correspondente à soma
                for rel_item in self.nao_conciliadas_rel:
                    if rel_item["data"] and rel_item["data"].date() == data:
                        if abs(rel_item["valor"] - soma_extrato) < tol:
                            # Encontrou! Marcar todos os itens do extrato como conciliados
                            # exceto o atual (que será marcado pelo chamador)
                            outros_itens = [item for item in combo if item != ofx_item]
                            
                            # Registrar os outros itens como conciliados
                            for outro in outros_itens:
                                self.resultado.append({
                                    "ofx": outro,
                                    "rel": rel_item,  # Mesmo item do relatório
                                    "status": "Conciliado (Soma)"
                                })
                            
                            # Remover o item do relatório da lista de não conciliados
                            self.nao_conciliadas_rel.remove(rel_item)
                            
                            # Retornar o item do relatório para o item atual
                            return rel_item
        
        return None
    def _registrar_match(self, ofx_item, match):
        """
        Adiciona as linhas conciliadas (exato ou soma) no resultado final.
        Caso seja soma dupla, a primeira linha fica com 'Conciliado',
        e as demais com 'Conciliado (Soma)'.
        """
        tipo = match[1]
        itens_rel = match[0] if isinstance(match[0], list) else [match[0]]
        
        for idx, rel_item in enumerate(itens_rel):
            self.resultado.append({
                "ofx": ofx_item,
                "rel": rel_item,
                "status": tipo if idx == 0 else "Conciliado (Soma)"
            })

    def _processar_nao_conciliados(self):
        """
        Marca como não conciliado tudo que sobrou (tanto no extrato quanto no relatório).
        """
        # Transações do extrato que não tiveram match
        for ofx_item in self.trans_ofx:
            if not any(r["ofx"] == ofx_item for r in self.resultado):
                self.resultado.append({
                    "ofx": ofx_item,
                    "rel": None,
                    "status": "Não conciliado"
                })
        
        # Transações do relatório que não tiveram match
        for rel_item in self.nao_conciliadas_rel:
            self.resultado.append({
                "ofx": None,
                "rel": rel_item,
                "status": "Não conciliado"
            })

    def _gerar_dataframe(self):
        """
        Gera um DataFrame final com colunas de Extrato e Relatório,
        exibindo data (DD/MM/AAAA), valor (R$ X,XX), descrição e status.
        """
        linhas = []
        for item in self.resultado:
            ofx = item["ofx"]
            rel = item["rel"]
            
            linha = {
                "Extrato Data": ofx["data"].strftime('%d/%m/%Y') if (ofx and pd.notnull(ofx["data"])) else "",
                "Extrato Valor": f"R$ {ofx['valor']:.2f}".replace('.', ',') if ofx else "",
                "Extrato Descrição": ofx["descricao"] if ofx else "",
                "Relatório Data": rel["data"].strftime('%d/%m/%Y') if (rel and pd.notnull(rel["data"])) else "",
                "Relatório Valor": f"R$ {rel['valor']:.2f}".replace('.', ',') if rel else "",
                "Relatório Descrição": rel["descricao"] if rel else "",
                "Status": item["status"]
            }
            linhas.append(linha)
        return pd.DataFrame(linhas)
        
    def _mostrar_resumo_dias(self):
        """
        Exibe um resumo dos dias conciliados e não conciliados
        """
        # Agrupar transações por dia
        dias_agrupados = self.agrupar_por_dia([])
        
        # Contar dias conciliados e não conciliados
        dias_conciliados = sum(1 for row in dias_agrupados if row["tag"] == "match")
        dias_nao_conciliados = sum(1 for row in dias_agrupados if row["tag"] == "no-match")
        total_dias = len(dias_agrupados)
        
        # Calcular valores totais
        total_extrato = 0
        total_relatorio = 0
        
        for row in dias_agrupados:
            # Extrair valores numéricos das strings formatadas
            valor_extrato_str = row["values"][1].replace("R$", "").replace(".", "").replace(",", ".").strip()
            valor_relatorio_str = row["values"][4].replace("R$", "").replace(".", "").replace(",", ".").strip()
            
            try:
                total_extrato += float(valor_extrato_str)
            except ValueError:
                pass
                
            try:
                total_relatorio += float(valor_relatorio_str)
            except ValueError:
                pass
                
        diferenca_total = abs(total_extrato - total_relatorio)
        
        # Exibir resumo em formato de card
        st.markdown("### 📆 Resumo por Dias")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Dias Conciliados", 
                value=f"{dias_conciliados}/{total_dias}",
                delta=f"{(dias_conciliados/total_dias*100):.1f}%" if total_dias > 0 else "0%"
            )
            
        with col2:
            st.metric(
                label="Total Extrato", 
                value=f"R$ {total_extrato:.2f}".replace('.', ',')
            )
            
        with col3:
            st.metric(
                label="Total Relatório", 
                value=f"R$ {total_relatorio:.2f}".replace('.', ','),
                delta=f"Diferença: R$ {diferenca_total:.2f}".replace('.', ','),
                delta_color="inverse" if diferenca_total > 0.01 else "normal"
            )
        
        # Listar dias com problemas se houver
        if dias_nao_conciliados > 0:
            dias_problema = [row["values"][0] for row in dias_agrupados if row["tag"] == "no-match"]
            st.warning(f"⚠️ Dias com diferenças: {', '.join(dias_problema)}")
    # --------------------------------------------------
    # AGRUPAMENTO POR DIA
    # --------------------------------------------------
    def agrupar_por_dia(self, rows):
        """
        Agrupa as transações por dia, calculando totais para extrato e relatório.
        - Extrato: soma todos os valores do OFX
        - Relatório: soma apenas valores conciliados, respeitando filtros
        """
        # Organizar por data
        rows_by_date = {}
        
        # Primeiro, agrupar todas as transações do extrato por data
        for trans in self.trans_ofx:
            date_str = trans['data'].strftime('%d/%m/%Y')
            if date_str not in rows_by_date:
                rows_by_date[date_str] = {
                    'extrato_total': 0,
                    'relatorio_total': 0,
                    'rows': []
                }
            # Somar todos os valores do extrato, respeitando o sinal
            rows_by_date[date_str]['extrato_total'] += trans['valor']
        
        # Processar as transações do relatório que foram conciliadas
        for item in self.resultado:
            rel_item = item['rel']
            status = item['status']
            
            # Considerar apenas itens conciliados do relatório
            if rel_item and status in ["Conciliado", "Conciliado (Soma)"]:
                date_str = rel_item['data'].strftime('%d/%m/%Y')
                
                if date_str not in rows_by_date:
                    rows_by_date[date_str] = {
                        'extrato_total': 0,
                        'relatorio_total': 0,
                        'rows': []
                    }
                
                # Somar valores do relatório (já filtrados por conta e natureza C/D)
                rows_by_date[date_str]['relatorio_total'] += rel_item['valor']
        
        # Criar linhas agregadas
        aggregated_rows = []
        for date_str, data in sorted(rows_by_date.items()):
            extrato_total = data['extrato_total']
            relatorio_total = data['relatorio_total']
            
            # Formatar os valores para exibição
            extrato_valor_fmt = f"R$ {extrato_total:.2f}".replace('.', ',')
            relatorio_valor_fmt = f"R$ {relatorio_total:.2f}".replace('.', ',')
            
            # Determinar o status com base na diferença
            diff = abs(extrato_total - relatorio_total)
            status = "Conciliado" if diff < 0.01 else "Não conciliado"
            
            aggregated_row = {
                "values": [
                    date_str,
                    extrato_valor_fmt,
                    "",  # Espaço em branco
                    date_str,
                    relatorio_valor_fmt,
                    "",  # Espaço em branco
                    status
                ],
                "tag": "match" if status == "Conciliado" else "no-match"
            }
            aggregated_rows.append(aggregated_row)
        
        return aggregated_rows
        day_sums = {}
        
        for r in rows:
            vals = r["values"]
            # Garantir que as strings estejam limpas (strip) e, se não existirem, usar string vazia
            edata_str = vals[0].strip() if vals[0] else ""
            evalor_str = vals[1].strip() if vals[1] else ""
            rdata_str = vals[3].strip() if vals[3] else ""
            rvalor_str = vals[4].strip() if vals[4] else ""
            
            # Converter para float – se o valor estiver vazio, definir como 0.0
            e_val = self._parse_valor(evalor_str) if evalor_str else 0.0
            r_val = self._parse_valor(rvalor_str) if rvalor_str else 0.0
        
            # Agregar o valor do extrato (OFX) se houver data
            if edata_str:
                try:
                    dt_extrato = self._parse_data_str(edata_str)  # Converte para datetime
                    d_fmt_extrato = dt_extrato.strftime("%d/%m/%Y")
                    if d_fmt_extrato not in day_sums:
                        day_sums[d_fmt_extrato] = {"extrato": 0.0, "rel": 0.0}
                    day_sums[d_fmt_extrato]["extrato"] += e_val
                except Exception as ex:
                    # Se ocorrer erro na conversão, ignore essa linha para o extrato
                    pass
        
            # Agregar o valor do relatório (se houver data)
            if rdata_str:
                try:
                    dt_rel = self._parse_data_str(rdata_str)
                    d_fmt_rel = dt_rel.strftime("%d/%m/%Y")
                    if d_fmt_rel not in day_sums:
                        day_sums[d_fmt_rel] = {"extrato": 0.0, "rel": 0.0}
                    day_sums[d_fmt_rel]["rel"] += r_val
                except Exception as ex:
                    # Se ocorrer erro na conversão, ignore essa linha para o relatório
                    pass
        
        # Gerar as linhas de agregação, ordenando as datas
        aggregator_rows = []
        for d in sorted(day_sums.keys(), key=lambda x: datetime.strptime(x, "%d/%m/%Y")):
            extrato_val = day_sums[d]["extrato"]
            rel_val = day_sums[d]["rel"]
            diff = extrato_val - rel_val
            
            status = "Dia conciliado" if abs(diff) < 0.01 else f"Diferença: R$ {diff:.2f}"
            tag = "verde" if abs(diff) < 0.01 else "vermelho"
            
            aggregator_rows.append({
                "values": [
                    d,  # Período (DD/MM/AAAA)
                    f"R$ {extrato_val:.2f}".replace('.', ','),
                    "",
                    d,  # Data Relatório
                    f"R$ {rel_val:.2f}".replace('.', ','),
                    "",
                    status
                ],
                "tag": tag
            })
        
        return aggregator_rows


    def _parse_valor(self, valor_str):
        """
        Remove caracteres não numéricos e converte a string em float,
        tratando ponto e vírgula.
        """
        try:
            # Remove tudo que não for dígito, ponto ou vírgula
            clean_str = re.sub(r"[^0-9,.-]", "", valor_str)
            # Troca vírgula por ponto
            clean_str = clean_str.replace(",", ".")
            return float(clean_str)
        except:
            return 0.0

    def _parse_data_str(self, data_str):
        """
        Interpreta a string no formato DD/MM/YYYY.
        Caso não consiga, retorna a data/hora atual.
        """
        try:
            return datetime.strptime(data_str.strip(), "%d/%m/%Y")
        except:
            return datetime.now()