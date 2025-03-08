import streamlit as st
import pandas as pd
import os
import json
import io
import base64
import plotly.express as px
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from data_loader import ler_ofx, carregar_relatorio_dataframe, converter_dataframe
from reconciliation import Conciliador
from styling import colorir_linhas, colorir_linhas_agregado

# Configuração da página
st.set_page_config(
    page_title="IA Conciliação",
    layout="wide",
    page_icon="💲",
    initial_sidebar_state="expanded"
)

# Diretórios
os.makedirs("profiles", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# -----------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------

def carregar_logo():
    """Exibe a logo centralizada na sidebar"""
    try:
        logo_path = os.path.join('assets', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                logo_bytes = f.read()
                logo_base64 = base64.b64encode(logo_bytes).decode()
            
            st.sidebar.markdown(
                f'<div style="text-align: center; margin-bottom: 2rem;">'
                f'<img src="data:image/png;base64,{logo_base64}" width="200">'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.sidebar.title("CONCILIADOR PRO")
    except Exception as e:
        st.sidebar.title("CONCILIADOR PRO")

def inicializar_sessao():
    """Inicializa variáveis de sessão"""
    session_defaults = {
        'colunas_mapeadas': {
            'data': None, 'valor': None, 'descricao': None,
            'conta': None, 'natureza': None, 'receita': None, 'despesa': None
        },
        'tipo_relatorio': "Única coluna com Natureza (C/D)",
        'filtros_status': ["Conciliado", "Conciliado (Soma)", "Não conciliado"],
        'df_resultado': None,
        'df_agregado': None,
        'df_diario': None,
        'aggregator_rows': None,
        'backup_profiles': []
    }

    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def atualizar_filtros():
    """Atualiza os filtros sem recarregar os dados"""
    if st.session_state.df_resultado is not None:
        # Filtro por status
        df_filtrado = st.session_state.df_resultado[
            st.session_state.df_resultado['Status'].isin(st.session_state.filtros_status)
        ]   
    
        
        st.session_state.df_filtrado = df_filtrado

# -----------------------------------------------
# GERENCIAMENTO DE PERFIS
# -----------------------------------------------

def gerenciar_perfis():
    """Interface para gerenciamento de perfis na sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Perfis de Mapeamento")
    
    # Listar perfis existentes
    perfis = [f.replace(".json", "") for f in os.listdir("profiles") if f.endswith(".json")]
    
    # Seleção de perfil
    perfil_selecionado = st.sidebar.selectbox(
        "Selecione um perfil:",
        [""] + perfis,
        key="perfil_selecionado"
    )
    
    # Botões de ação
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Carregar Perfil", key="btn_carregar"):
            if perfil_selecionado:
                carregar_perfil(perfil_selecionado)
    with col2:
        if st.button("Deletar Perfil", key="btn_deletar"):
            if perfil_selecionado:
                os.remove(os.path.join("profiles", f"{perfil_selecionado}.json"))
                st.sidebar.success("Perfil removido!")
    
    # Criação de novo perfil
    with st.sidebar.form("novo_perfil_form"):
        novo_perfil = st.text_input("Nome do novo perfil:")
        if st.form_submit_button("Salvar Perfil Atual"):
            if novo_perfil:
                salvar_perfil(novo_perfil)
                st.sidebar.success("Perfil salvo!")

def salvar_perfil(nome):
    """Salva as configurações atuais em um perfil"""
    perfil = {
        "mapeamento": st.session_state.colunas_mapeadas,
        "tipo_relatorio": st.session_state.tipo_relatorio
    }
    with open(os.path.join("profiles", f"{nome}.json"), "w") as f:
        json.dump(perfil, f)

def carregar_perfil(nome):
    """Carrega um perfil salvo"""
    with open(os.path.join("profiles", f"{nome}.json"), "r") as f:
        perfil = json.load(f)
    st.session_state.colunas_mapeadas = perfil["mapeamento"]
    st.session_state.tipo_relatorio = perfil["tipo_relatorio"]
    st.sidebar.success("Perfil carregado!")

# -----------------------------------------------
# INTERFACE PRINCIPAL
# -----------------------------------------------

def main():
    # Inicialização
    inicializar_sessao()
    carregar_logo()    
    gerenciar_perfis()
    # Filtros dinâmicos
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros de Status")
    status_opcoes = ["Conciliado", "Conciliado (Soma)", "Não conciliado"]
    for status in status_opcoes:
        key = f"filter_{status}"
        if st.sidebar.checkbox(status, key=key, value=status in st.session_state.filtros_status):
            if status not in st.session_state.filtros_status:
                st.session_state.filtros_status.append(status)
        else:
            if status in st.session_state.filtros_status:
                st.session_state.filtros_status.remove(status)
    
    # Botão para atualizar filtros
    if st.sidebar.button("🔄 Atualizar Filtros", use_container_width=True):
        atualizar_filtros()
    # Conteúdo principal
    st.markdown('<div id="inicio"></div>', unsafe_allow_html=True)
    st.title("IA CONCILIAÇÃO BANCÁRIA AUTOMÁTICA")
    
    # Upload de arquivos
    col1, col2 = st.columns(2)
    with col1:
        ofx_file = st.file_uploader("Arquivo OFX/Bancário", type=["ofx"])
    with col2:
        rel_file = st.file_uploader("Relatório ERP/Financeiro", type=["csv"])
    
    # Configuração do mapeamento
    if rel_file:
        try:
            df_rel = carregar_relatorio_dataframe(rel_file, rel_file.name)
            colunas = df_rel.columns.tolist()
            
            st.markdown("### 🔧 Configuração do Mapeamento")
            
            # Seleção do tipo de relatório
            st.session_state.tipo_relatorio = st.selectbox(
                "Formato do Relatório:",
                ["Única coluna com Natureza (C/D)", "Colunas separadas Receita/Despesa"],
                index=0 if st.session_state.tipo_relatorio.startswith("Única") else 1
            )
            
            # Mapeamento de colunas
            col1, col2 = st.columns(2)
            with col1:
                campos_base = ['data', 'descricao', 'conta']
                for campo in campos_base:
                    st.session_state.colunas_mapeadas[campo] = st.selectbox(
                        f"Coluna de {campo.title()}",
                        colunas,
                        index=colunas.index(st.session_state.colunas_mapeadas[campo]) 
                        if st.session_state.colunas_mapeadas[campo] in colunas else 0
                    )
            
            with col2:
                if st.session_state.tipo_relatorio == "Única coluna com Natureza (C/D)":
                    campos = ['valor', 'natureza']
                else:
                    campos = ['receita', 'despesa']
                
                for campo in campos:
                    st.session_state.colunas_mapeadas[campo] = st.selectbox(
                        f"Coluna de {campo.title()}",
                        colunas,
                        index=colunas.index(st.session_state.colunas_mapeadas[campo]) 
                        if st.session_state.colunas_mapeadas[campo] in colunas else 0
                    )
            
            # Filtro por conta
            contas = df_rel[st.session_state.colunas_mapeadas['conta']].dropna().unique().tolist()
            conta_filtro = st.selectbox("Filtrar por Conta (Opcional)", [""] + contas)
        
        except Exception as e:
            st.error(f"Erro no processamento: {str(e)}")

    # Execução da conciliação
    if st.button("▶️ EXECUTAR CONCILIAÇÃO", use_container_width=False):
        if ofx_file and rel_file:
            with st.spinner("Processando..."):
                try:
                    # Carregar dados
                    trans_ofx = ler_ofx(ofx_file)
                    df_rel = carregar_relatorio_dataframe(rel_file, rel_file.name)
                    
                    # Filtrar linhas com Natureza válida
                    df_rel = df_rel[df_rel[st.session_state.colunas_mapeadas['natureza']].isin(['C', 'D'])]

                    trans_rel = converter_dataframe(
                        df_rel,
                        st.session_state.colunas_mapeadas,
                        st.session_state.tipo_relatorio,
                        conta_filtro if conta_filtro else None
                    )
                    
                    # Processar conciliação
                    conciliador = Conciliador(trans_ofx, trans_rel)
                    df_resultado = conciliador.executar()
                    
                    # Gerar dados para agregação
                    rows_aux = [{
                        "values": [
                            row["Extrato Data"],
                            row["Extrato Valor"],
                            row["Extrato Descrição"],
                            row["Relatório Data"],
                            row["Relatório Valor"],
                            row["Relatório Descrição"],
                            row["Status"]
                        ],
                        "tag": ""
                    } for _, row in df_resultado.iterrows()]
                    
                    # Processar dados para gráfico
                    try:
                        df_diario = pd.DataFrame(trans_rel)
                        if not df_diario.empty:
                            # Converter a coluna 'data' para datetime e extrair somente a data
                            df_diario['data'] = pd.to_datetime(df_diario['data']).dt.date
                            
                            # Agrupar os dados por dia (apenas dias com movimentação serão mantidos)
                            df_diario = df_diario.groupby('data').agg({
                                'receita': 'sum',
                                'despesa': 'sum'
                            }).reset_index()
                            
                            # Converter as datas para o formato "dd/mm/aaaa"
                            df_diario['data'] = df_diario['data'].apply(lambda d: d.strftime("%d/%m/%Y"))
                            
                            st.session_state.df_diario = df_diario
                    except Exception as chart_error:
                        st.error(f"Erro ao processar dados para gráfico: {str(chart_error)}")
                    
                    # Armazenar resultados
                    st.session_state.df_resultado = df_resultado
                    st.session_state.df_filtrado = df_resultado[df_resultado['Status'].isin(st.session_state.filtros_status)]
                    st.session_state.aggregator_rows = conciliador.agrupar_por_dia(rows_aux)
                    # Adicionar diferença para dias não conciliados
                    for row in st.session_state.aggregator_rows:
                        if row["values"][6] == "Não conciliado":
                            # Converter valores para float, tratando possíveis strings ou valores nulos
                            try:
                                extrato_valor = float(str(row["values"][1]).replace("R$", "").replace(".", "").replace(",", ".").strip()) if row["values"][1] else 0
                            except (ValueError, TypeError):
                                extrato_valor = 0
                                
                            try:
                                relatorio_valor = float(str(row["values"][4]).replace("R$", "").replace(".", "").replace(",", ".").strip()) if row["values"][4] else 0
                            except (ValueError, TypeError):
                                relatorio_valor = 0
                                
                            diferenca = extrato_valor - relatorio_valor
                            # Atualizar status com a diferença
                            row["values"][6] = f"Não conciliado (Diferença: R$ {diferenca:.2f})"
                            row["tag"] = "nao_conciliado"
                        elif row["values"][6] == "Conciliado":
                            row["tag"] = "conciliado"
                        elif row["values"][6] == "Conciliado (Soma)":
                            row["tag"] = "conciliado_soma"
                    st.session_state.df_agregado = pd.DataFrame(
                        [r["values"] for r in st.session_state.aggregator_rows],
                        columns=[
                            "Período", 
                            "Total Extrato", 
                            " ",
                            "Data Relatório", 
                            "Total Relatório", 
                            "  ",
                            "Status"
                        ]
                    )
                    
                    st.success("✅ Conciliação concluída com sucesso!")
                
                except Exception as e:
                    st.error(f"Erro durante o processamento: {str(e)}")
        else:
            st.error("⚠️ Por favor, carregue ambos os arquivos")

    # Exibição dos resultados
    if st.session_state.df_resultado is not None:
        # Resultados detalhados
        with st.expander("📋 Detalhes da Conciliação", expanded=True):
            # Criar uma cópia do DataFrame para ajustar o tamanho da coluna
            df_display = st.session_state.df_filtrado.copy()
            
            # Limitar o tamanho do texto na coluna 'Relatório Descrição'
            if 'Relatório Descrição' in df_display.columns:
                df_display['Relatório Descrição'] = df_display['Relatório Descrição'].astype(str).apply(
                    lambda x: x[:50] + '...' if len(x) > 50 else x
                )
            
            st.dataframe(
                colorir_linhas(df_display),
                use_container_width=True,
                height=700,
                column_config={
                    "Relatório Descrição": st.column_config.TextColumn(
                        "Relatório Descrição",
                        width="medium",
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        width="medium",
                    )
                }
            )
        
        # Agregações diárias
        with st.expander("📅 Movimentações Agregadas por Dia", expanded=True):
            st.dataframe(
                colorir_linhas_agregado(
                    st.session_state.df_agregado,
                    [r["tag"] for r in st.session_state.aggregator_rows]
                ),
                use_container_width=True,
                height=980
            )
        
        # Gráfico diário
        with st.expander("📊 Gráfico Diário - Receitas vs Despesas", expanded=True):
            if 'df_diario' in st.session_state and not st.session_state.df_diario.empty:
                fig = px.bar(
                    st.session_state.df_diario,
                    x='data',
                    y=['receita', 'despesa'],
                    labels={'value': 'Valor (R$)', 'data': 'Data'},
                    color_discrete_map={'receita': '#2ecc71', 'despesa': '#e74c3c'},
                    barmode='group'
                )
                fig.update_layout(
                    title='Movimentações Financeiras Diárias',
                    xaxis_title='Data',
                    yaxis_title='Valor (R$)',
                    legend_title='Tipo',
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Não há dados suficientes para gerar o gráfico")
        
        # Download em múltiplos formatos
        st.markdown("### 📥 Exportar Resultados")
        formato_exportacao = st.radio(
            "Selecione o formato de exportação:",
            options=["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"],
            horizontal=True
        )
        
        if formato_exportacao == "Excel (.xlsx)":
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                st.session_state.df_filtrado.to_excel(writer, sheet_name='Detalhes', index=False)
                st.session_state.df_agregado.to_excel(writer, sheet_name='Agregado', index=False)
                if 'df_diario' in st.session_state:
                    st.session_state.df_diario.to_excel(writer, sheet_name='Gráfico', index=False)
            
            st.download_button(
                label="📥 BAIXAR RELATÓRIO EM EXCEL",
                data=excel_buffer.getvalue(),
                file_name="conciliação_completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        elif formato_exportacao == "CSV (.csv)":
            csv_buffer = io.StringIO()
            st.session_state.df_filtrado.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
            
            st.download_button(
                label="📥 BAIXAR RELATÓRIO EM CSV",
                data=csv_buffer.getvalue(),
                file_name="conciliação_completa.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Opção para baixar também os dados agregados
            if st.checkbox("Incluir dados agregados", value=False):
                csv_agregado = io.StringIO()
                st.session_state.df_agregado.to_csv(csv_agregado, index=False, sep=';', encoding='utf-8-sig')
                
                st.download_button(
                    label="📥 BAIXAR DADOS AGREGADOS EM CSV",
                    data=csv_agregado.getvalue(),
                    file_name="conciliação_agregada.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        elif formato_exportacao == "PDF (.pdf)":
            # Criar buffer para PDF
            pdf_buffer = io.BytesIO()
            
            # Criar documento PDF com tamanho personalizado para melhor ajuste
            doc = SimpleDocTemplate(
                pdf_buffer, 
                pagesize=(landscape(A4)[0] * 1.5, landscape(A4)[1]),  # Aumentando a largura em 50%
                leftMargin=20, 
                rightMargin=20,
                topMargin=30, 
                bottomMargin=30
            )
            elements = []
            
            # Adicionar cabeçalho com logo e nome da empresa
            styles = getSampleStyleSheet()
            header_style = styles['Heading1']
            header_style.alignment = 1  # Centralizado
            
            # Verificar se existe logo e adicionar
            logo_path = os.path.join('assets', 'logo.png')
            if os.path.exists(logo_path):
                from reportlab.platypus import Image
                logo = Image(logo_path, width=100, height=50)
                elements.append(logo)
                elements.append(Spacer(1, 10))
            
            # Adicionar título e nome da empresa
            elements.append(Paragraph("Relatório de Conciliação Bancária", header_style))
            company_style = styles['Heading2']
            company_style.alignment = 1  # Centralizado
            elements.append(Paragraph("Dados Inteligentes", company_style))
            elements.append(Paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
            elements.append(Spacer(1, 20))
            
            # Adicionar resumo da conciliação
            if st.session_state.df_resultado is not None:
                total_transacoes = len(st.session_state.df_resultado)
                conciliadas = len(st.session_state.df_resultado[st.session_state.df_resultado['Status'].str.contains('Conciliado')])
                nao_conciliadas = total_transacoes - conciliadas
                taxa_sucesso = (conciliadas / total_transacoes * 100) if total_transacoes > 0 else 0
                
                # Calcular dias conciliados vs total de dias
                dias_unicos = st.session_state.df_agregado['Período'].nunique()
                dias_conciliados = st.session_state.df_agregado[st.session_state.df_agregado['Status'].str.contains('Conciliado')]['Período'].nunique()
                
                # Obter valores totais
                try:
                    total_extrato = sum([float(str(val).replace('R$', '').replace('.', '').replace(',', '.').strip()) 
                                        for val in st.session_state.df_agregado['Total Extrato'] if val and str(val).strip()])
                    total_relatorio = sum([float(str(val).replace('R$', '').replace('.', '').replace(',', '.').strip()) 
                                          for val in st.session_state.df_agregado['Total Relatório'] if val and str(val).strip()])
                    diferenca = total_extrato - total_relatorio
                except:
                    total_extrato = 0
                    total_relatorio = 0
                    diferenca = 0
                
                # Criar tabela de resumo
                resumo_style = styles['Heading3']
                resumo_style.alignment = 1
                elements.append(Paragraph("Resumo da Conciliação", resumo_style))
                elements.append(Spacer(1, 5))
                
                # Dados do resumo
                resumo_data = [
                    ["Conciliação finalizada!", f"Taxa de sucesso: {taxa_sucesso:.1f}%"],
                    [f"✓ {conciliadas} transações conciliadas", f"✗ {nao_conciliadas} não conciliadas"],
                    ["Resumo por Dias", ""],
                    [f"Dias Conciliados: {dias_conciliados}/{dias_unicos}", f"({dias_conciliados/dias_unicos*100:.1f}% dos dias)"],
                    [f"Total Extrato: R$ {total_extrato:.2f}", f"Total Relatório: R$ {total_relatorio:.2f}"],
                    [f"Diferença: R$ {diferenca:.2f}", ""]
                ]
                
                # Criar tabela de resumo
                resumo_table = Table(resumo_data, colWidths=[250, 250])
                resumo_style = [
                    ('BACKGROUND', (0, 0), (1, 0), colors.lightgreen),
                    ('BACKGROUND', (0, 2), (1, 2), colors.lightblue),
                    ('GRID', (0, 0), (1, -1), 0.5, colors.grey),
                    ('ALIGN', (0, 0), (1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
                    ('VALIGN', (0, 0), (1, -1), 'MIDDLE'),
                    ('FONTSIZE', (0, 0), (1, -1), 10),
                ]
                resumo_table.setStyle(TableStyle(resumo_style))
                elements.append(resumo_table)
                elements.append(Spacer(1, 20))
            
            # Função para criar tabela com cores
            def create_table(df, title, status_col=None):
                title_style = styles['Heading2']
                title_style.alignment = 1  # Centralizado
                elements.append(Paragraph(title, title_style))
                elements.append(Spacer(1, 10))
                
                # Usar todo o DataFrame sem limitar linhas
                df_display = df.copy()
                
                # Formatar valores monetários para tabela de gráfico diário
                if title == "Dados do Gráfico Diário" and 'receita' in df_display.columns and 'despesa' in df_display.columns:
                    df_display['receita'] = df_display['receita'].apply(lambda x: f"R$ {float(x):.2f}" if pd.notnull(x) else "")
                    df_display['despesa'] = df_display['despesa'].apply(lambda x: f"R$ {float(x):.2f}" if pd.notnull(x) else "")
                
                # Truncar textos longos
                for col in df_display.columns:
                    if df_display[col].dtype == 'object':  # Se for texto
                        df_display[col] = df_display[col].astype(str).apply(
                            lambda x: (x[:40] + '...') if len(x) > 40 else x
                        )
                
                # Converter DataFrame para lista
                data = [df_display.columns.tolist()] + df_display.values.tolist()
                
                # Calcular larguras das colunas com base no conteúdo
                col_widths = []
                available_width = landscape(A4)[0] * 1.5 - 80  # Aumentando a margem lateral
                
                # Primeiro, determinar o tamanho mínimo necessário para cada coluna
                min_widths = []
                for i in range(len(data[0])):
                    col_content = [str(row[i]) for row in data]
                    max_len = max([len(content) for content in col_content])
                    # Converter comprimento do texto em unidades de largura aproximadas
                    min_widths.append(max_len * 4)
                
                # Calcular a largura total necessária
                total_min_width = sum(min_widths)
                
                # Distribuir o espaço disponível proporcionalmente
                if total_min_width > 0:
                    for width in min_widths:
                        col_width = (width / total_min_width) * available_width
                        # Garantir uma largura mínima razoável
                        col_widths.append(max(col_width, 40))
                else:
                    # Fallback: dividir igualmente se não conseguir calcular
                    col_widths = [available_width / len(data[0])] * len(data[0])
                
                # Todas as tabelas usam o mesmo alinhamento central
                table = Table(data, colWidths=col_widths, hAlign='CENTER')
                
                # Estilo base da tabela
                style = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),  # Tamanho reduzido para cabeçalho
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),  # Tamanho reduzido para conteúdo
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('WORDWRAP', (0, 0), (-1, -1), True),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Aumentar padding para melhor espaçamento
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]
                
                # Adicionar cores com base no status (se aplicável)
                if status_col is not None and status_col in df_display.columns:
                    for i, row in enumerate(data[1:], 1):  # Começar do índice 1 (após o cabeçalho)
                        status_idx = df_display.columns.get_loc(status_col)
                        status = row[status_idx]
                        
                        if "Conciliado" in str(status) and "Soma" not in str(status):
                            style.append(('BACKGROUND', (0, i), (-1, i), colors.lightgreen))
                        elif "Conciliado (Soma)" in str(status):
                            style.append(('BACKGROUND', (0, i), (-1, i), colors.lightblue))
                        elif "Não conciliado" in str(status):
                            style.append(('BACKGROUND', (0, i), (-1, i), colors.mistyrose))
                
                table.setStyle(TableStyle(style))
                elements.append(table)
                elements.append(Spacer(1, 20))
            
            # Adicionar tabelas ao PDF com cores baseadas no status
            create_table(st.session_state.df_filtrado, "Detalhes da Conciliação", "Status")
            create_table(st.session_state.df_agregado, "Movimentações Agregadas por Dia", "Status")
            
            if 'df_diario' in st.session_state and not st.session_state.df_diario.empty:
                create_table(st.session_state.df_diario, "Dados do Gráfico Diário")
            
            # Adicionar rodapé
            footer_text = f"Gerado por IA Conciliação - Dados Inteligentes em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            elements.append(Paragraph(footer_text, styles['Italic']))
            
            # Gerar PDF
            doc.build(elements)
            
            # Botão de download
            st.download_button(
                label="📥 BAIXAR RELATÓRIO EM PDF",
                data=pdf_buffer.getvalue(),
                file_name="conciliação_completa.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    # Seções informativas
    st.markdown("---")
    st.markdown('<div id="instrucoes"></div>', unsafe_allow_html=True)
    st.markdown("## 📑 Instruções")
    st.markdown("""
    **Guia Rápido:**
    1. Carregue o arquivo OFX (extrato bancário)
    2. Carregue o relatório do sistema (CSV/Excel)
    3. Configure o mapeamento das colunas
    4. Execute a conciliação
    5. Utilize os filtros para análise detalhada
    6. Exporte os resultados para Excel quando necessário
    """)
    
    st.markdown("---")
    st.markdown('<div id="sobre"></div>', unsafe_allow_html=True)
    st.markdown("## 🛄 Sobre")
    st.markdown("""
    **IA de Conciliação Bancária Automática**  
    Versão 3.0  
    Desenvolvido por: **Dácio Moreira - Dados Inteligentes**  
    Contato: daciohm@gmail.com
    """)

if __name__ == "__main__":
    main()