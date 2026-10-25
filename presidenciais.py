"""
Apuração em tempo real - Eleição presidencial (Brasil)

Como rodar:
    pip install streamlit requests pandas plotly
    streamlit run apuracao_eleicao.py

Fonte: arquivos JSON públicos do Portal Resultados do TSE
(https://resultados.tse.jus.br). Os números oficiais são os do TSE.
"""

import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Apuração Presidente", page_icon="🗳️", layout="wide")

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DA FONTE DE DADOS
# ---------------------------------------------------------------------------
# O TSE publica um JSON por eleição. O padrão do endereço (usado em 2022) é:
#   https://resultados.tse.jus.br/oficial/ele2026/<ID>/dados-simplificados/br/br-c0001-e<ID com 6 dígitos>-r.json
# O <ID> do 2º turno de 2026 precisa ser conferido no Portal Resultados
# (aba Rede/Network do navegador, ao abrir a página do Presidente). Se o
# padrão acima mudar, cole a URL completa na barra lateral.
ID_PADRAO = "545"  # ATENÇÃO: valor de 2022 (2º turno). Confirme o de 2026.
ANO = "2026"


def montar_url(eleicao_id: str) -> str:
    return (
        f"https://resultados.tse.jus.br/oficial/ele{ANO}/{eleicao_id}/"
        f"dados-simplificados/br/br-c0001-e{int(eleicao_id):06d}-r.json"
    )


def num(valor) -> float:
    """O TSE manda números como texto com vírgula decimal ('47,85')."""
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


@st.cache_data(ttl=20, show_spinner=False)
def buscar(url: str) -> dict:
    r = requests.get(url, timeout=15, headers={"User-Agent": "apuracao-app/1.0"})
    r.raise_for_status()
    return r.json()


def demo() -> dict:
    """Dados fictícios só para testar a interface antes da apuração."""
    return {
        "dg": "25/10/2026", "hg": "00:00:00",
        "pst": "50,00", "st": "499248",
        "vv": "60000000", "pvv": "95,00", "vb": "1000000", "pvb": "1,50",
        "tvn": "2000000", "ptvn": "3,50", "ea": "30000000", "pea": "20,00",
        "cand": [
            {"nm": "CANDIDATO A", "sgp": "-", "n": "13", "vap": "31000000", "pvap": "51,67", "seq": "1"},
            {"nm": "CANDIDATO B", "sgp": "-", "n": "22", "vap": "29000000", "pvap": "48,33", "seq": "2"},
        ],
    }


def para_dataframe(dados: dict) -> pd.DataFrame:
    linhas = []
    for c in dados.get("cand", []):
        linhas.append({
            "Candidato": c.get("nm", "?"),
            "Partido": c.get("sgp", ""),
            "Nº": c.get("n", ""),
            "Votos": int(num(c.get("vap"))),
            "% válidos": num(c.get("pvap")),
        })
    df = pd.DataFrame(linhas)
    return df.sort_values("Votos", ascending=False).reset_index(drop=True) if not df.empty else df


# ---------------------------------------------------------------------------
# BARRA LATERAL
# ---------------------------------------------------------------------------
st.sidebar.header("Configuração")
modo_demo = st.sidebar.toggle("Modo demonstração (dados fictícios)", value=False)
eleicao_id = st.sidebar.text_input("ID da eleição no TSE", ID_PADRAO)
url_manual = st.sidebar.text_input("URL completa do JSON (opcional)", "")
intervalo = st.sidebar.slider("Atualizar a cada (segundos)", 15, 120, 30)
st.sidebar.caption(
    "Os números oficiais são os do Portal Resultados do TSE: "
    "https://resultados.tse.jus.br"
)

st.title("🗳️ Apuração em tempo real: Presidente do Brasil")
st.caption("2º turno · 25/10/2026 · divulgação a partir das 17h (Brasília)")


@st.fragment(run_every=intervalo)
def painel():
    url = url_manual.strip() or montar_url(eleicao_id)
    try:
        dados = demo() if modo_demo else buscar(url)
    except Exception as e:  # rede, 404 (ID errado), JSON inválido...
        st.warning(
            "Não consegui ler os dados do TSE (ainda não publicados ou endereço "
            f"incorreto). Detalhe: {e}"
        )
        st.code(url)
        return

    df = para_dataframe(dados)
    if df.empty:
        st.info("Aguardando o início da totalização.")
        return

    secoes = num(dados.get("pst"))
    st.progress(min(secoes / 100, 1.0), text=f"Seções totalizadas: {secoes:.2f}%")

    # Cartões dos candidatos
    cols = st.columns(len(df))
    for col, (_, r) in zip(cols, df.iterrows()):
        col.metric(f"{r['Candidato']} ({r['Partido']} {r['Nº']})",
                   f"{r['% válidos']:.2f}%", f"{r['Votos']:,}".replace(",", "."))

    # Diferença entre os dois primeiros
    if len(df) >= 2:
        dif_pp = df.loc[0, "% válidos"] - df.loc[1, "% válidos"]
        dif_v = df.loc[0, "Votos"] - df.loc[1, "Votos"]
        st.write(
            f"**Diferença:** {dif_pp:.2f} p.p. "
            f"({dif_v:,} votos) a favor de {df.loc[0, 'Candidato']}".replace(",", ".")
        )
        if secoes < 100:
            st.caption(
                "Resultado parcial: a ordem pode mudar conforme novas seções "
                "são totalizadas. Só vale o resultado proclamado pelo TSE."
            )

    g1, g2 = st.columns(2)
    with g1:
        fig = px.bar(df, x="Candidato", y="Votos", text="% válidos",
                     title="Votos por candidato")
        fig.update_traces(texttemplate="%{text:.2f}%")
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        brancos, nulos = num(dados.get("vb")), num(dados.get("tvn"))
        validos = num(dados.get("vv"))
        resumo = pd.DataFrame({
            "Tipo": ["Válidos", "Brancos", "Nulos"],
            "Votos": [validos, brancos, nulos],
        })
        st.plotly_chart(px.pie(resumo, names="Tipo", values="Votos",
                               title="Composição dos votos apurados"),
                        use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption(
        f"Arquivo do TSE gerado em {dados.get('dg', '?')} {dados.get('hg', '')} · "
        f"última consulta {datetime.now():%H:%M:%S}"
    )


painel()