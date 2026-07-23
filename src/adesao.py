import json
import os
from datetime import date, datetime, timedelta

from dosagem import carregar_tabela_dosagem, encontrar_faixa_peso
from pacientes import buscar_paciente, PASTA_PACIENTES


def _parse_data(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _dias_de_tratamento(data_inicio, data_referencia):
    """
    Conta os dias de tratamento de forma INCLUSIVA: o próprio dia de início
    já conta como o 1º dia (o paciente já deveria tomar a dose daquele dia).
    Ex: início 23/07, referência 23/07 -> 1 dia de tratamento (não 0).
    """
    if isinstance(data_inicio, str):
        data_inicio = _parse_data(data_inicio)
    if isinstance(data_referencia, str):
        data_referencia = _parse_data(data_referencia)

    dias = (data_referencia - data_inicio).days + 1
    if dias < 1:
        raise ValueError("Data de referência é anterior à data de início do tratamento.")
    return dias


def calcular_fase_atual(data_inicio, data_referencia=None, tabela=None):
    """
    Determina em que fase do tratamento o paciente está, com base em
    quantos dias (inclusive o dia de início) se passaram.
    Retorna "fase_intensiva", "fase_manutencao" ou "tratamento_concluido".
    """
    if tabela is None:
        tabela = carregar_tabela_dosagem()
    if data_referencia is None:
        data_referencia = date.today()

    dias_passados = _dias_de_tratamento(data_inicio, data_referencia)

    dias_fase_intensiva = tabela["fase_intensiva"]["duracao_meses"] * 30
    dias_fase_manutencao = tabela["fase_manutencao"]["duracao_meses"] * 30

    if dias_passados <= dias_fase_intensiva:
        return "fase_intensiva"
    elif dias_passados <= dias_fase_intensiva + dias_fase_manutencao:
        return "fase_manutencao"
    else:
        return "tratamento_concluido"


def calcular_dose_esperada_acumulada(peso, data_inicio, data_referencia=None,
                                       tabela=None, esquema_manutencao=None):
    """
    Calcula o total esperado de comprimidos (por modelo) desde o início
    do tratamento até a data de referência, considerando a transição
    entre fase intensiva e fase de manutenção.

    esquema_manutencao: o esquema PRESCRITO PELO MÉDICO (ex: {"rh_300_150": 1}),
        obrigatório se o período incluir dias de fase de manutenção.
        Use dosagem.listar_opcoes_manutencao(peso) para ver as opções válidas.

    Retorna: {"total_esperado": {...}, "dias_passados": N, "fase_atual": "..."}
    """
    if tabela is None:
        tabela = carregar_tabela_dosagem()
    if data_referencia is None:
        data_referencia = date.today()

    dias_passados = _dias_de_tratamento(data_inicio, data_referencia)

    dias_fase_intensiva = tabela["fase_intensiva"]["duracao_meses"] * 30
    dias_fase_manutencao = tabela["fase_manutencao"]["duracao_meses"] * 30

    total = {}

    # Dias efetivamente na fase intensiva (limitado à duração da fase)
    dias_intensiva = min(dias_passados, dias_fase_intensiva)
    if dias_intensiva > 0:
        faixa = encontrar_faixa_peso(tabela["fase_intensiva"]["faixas_peso"], peso)
        if faixa is None:
            raise ValueError(f"Nenhuma faixa de peso encontrada para {peso}kg (fase intensiva).")
        modelo = tabela["fase_intensiva"]["modelo_comprimido"]
        total[modelo] = total.get(modelo, 0) + faixa["comprimidos_por_dia"] * dias_intensiva

    # Dias efetivamente na fase de manutenção (começa depois da intensiva)
    dias_manutencao = max(0, min(dias_passados - dias_fase_intensiva, dias_fase_manutencao))
    if dias_manutencao > 0:
        if esquema_manutencao is None:
            from dosagem import listar_opcoes_manutencao
            opcoes = listar_opcoes_manutencao(peso, tabela=tabela)
            raise ValueError(
                f"Paciente já está (ou passou) pela fase de manutenção, mas não há "
                f"esquema_manutencao prescrito cadastrado. Defina com "
                f"pacientes.definir_esquema_manutencao(). Opções válidas para {peso}kg: {opcoes}"
            )

        from dosagem import validar_esquema_manutencao
        validar_esquema_manutencao(peso, esquema_manutencao, tabela=tabela)

        for modelo, qtd in esquema_manutencao.items():
            total[modelo] = total.get(modelo, 0) + qtd * dias_manutencao

    fase_atual = calcular_fase_atual(data_inicio, data_referencia, tabela)

    return {
        "total_esperado": total,
        "dias_passados": dias_passados,
        "fase_atual": fase_atual,
    }


# ====================================
# HISTÓRICO DE LEITURAS (fotos já processadas pelo pipeline)
# ====================================

def registrar_leitura(paciente_id, data_leitura, resumo_consolidado):
    """
    Registra uma leitura (resultado de uma rodada do pipeline, já com
    resumo_consolidado.json gerado) no histórico do paciente.

    resumo_consolidado: a lista que já vem de main.py -- cada item tem
    "modelo" e "tomados" (quantidade de posições marcadas como tomadas
    naquela cartela específica).
    """
    pasta_paciente = os.path.join(PASTA_PACIENTES, paciente_id)
    os.makedirs(pasta_paciente, exist_ok=True)
    arquivo_historico = os.path.join(pasta_paciente, "historico.json")

    if os.path.exists(arquivo_historico):
        with open(arquivo_historico, "r", encoding="utf-8") as f:
            historico = json.load(f)
    else:
        historico = []

    entrada = {
        "data": data_leitura,
        "leituras": resumo_consolidado,
    }
    historico.append(entrada)

    with open(arquivo_historico, "w", encoding="utf-8") as f:
        json.dump(historico, f, indent=4, ensure_ascii=False)

    print(f"Leitura registrada para paciente {paciente_id} em {data_leitura}.")
    return entrada


def carregar_historico(paciente_id):
    arquivo_historico = os.path.join(PASTA_PACIENTES, paciente_id, "historico.json")
    if not os.path.exists(arquivo_historico):
        return []
    with open(arquivo_historico, "r", encoding="utf-8") as f:
        return json.load(f)


def somar_tomados_historico(paciente_id, data_limite=None):
    """
    Soma o total de comprimidos "tomados" (por modelo) considerando que a
    MESMA cartela pode ser fotografada várias vezes ao longo do consumo
    (o paciente registra o progresso, não troca de cartela a cada foto).

    Lógica: para cada modelo, as leituras são ordenadas por data. Enquanto
    o valor de "tomados" só aumenta (ou se mantém) entre leituras
    consecutivas, consideramos que é a MESMA cartela evoluindo -- nesse
    caso usamos sempre o valor mais recente, não somamos.

    Se o valor de "tomados" CAI em relação à leitura anterior, isso indica
    que a cartela foi trocada por uma nova (a anterior foi finalizada/
    descartada). Nesse momento, o total da cartela anterior (seu último
    valor visto) é somado ao acumulado, e o rastreamento reinicia com a
    nova cartela.

    Isso é uma heurística: assume que o usuário não pula fotos a ponto de
    duas cartelas diferentes do mesmo modelo parecerem uma sequência
    crescente única. Se precisar de robustez total, considere adicionar
    um identificador explícito de cartela (ex: número de lote) a cada
    leitura no futuro.
    """
    historico = carregar_historico(paciente_id)

    # Filtra por data limite, se informado
    if data_limite:
        data_lim = _parse_data(data_limite) if isinstance(data_limite, str) else data_limite
        historico = [
            e for e in historico
            if (_parse_data(e["data"]) if isinstance(e["data"], str) else e["data"]) <= data_lim
        ]

    # Ordena por data (garantia, caso o histórico não esteja em ordem)
    historico_ordenado = sorted(
        historico,
        key=lambda e: _parse_data(e["data"]) if isinstance(e["data"], str) else e["data"]
    )

    total_acumulado = {}      # total já "fechado" de cartelas anteriores
    ultimo_valor_visto = {}   # valor mais recente da cartela atual em uso

    for entrada in historico_ordenado:
        for leitura in entrada["leituras"]:
            if leitura.get("erro"):
                continue
            modelo = leitura["modelo"]
            tomados = leitura["tomados"]

            if modelo not in ultimo_valor_visto:
                ultimo_valor_visto[modelo] = tomados
                continue

            if tomados < ultimo_valor_visto[modelo]:
                # Queda no valor -- indica troca de cartela.
                # Fecha a contagem da cartela anterior e reinicia.
                total_acumulado[modelo] = total_acumulado.get(modelo, 0) + ultimo_valor_visto[modelo]
                ultimo_valor_visto[modelo] = tomados
            else:
                # Mesma cartela, valor igual ou maior -- atualiza para o mais recente
                ultimo_valor_visto[modelo] = tomados

    # Soma a cartela ainda em uso (a mais recente de cada modelo) ao total
    total_final = dict(total_acumulado)
    for modelo, valor in ultimo_valor_visto.items():
        total_final[modelo] = total_final.get(modelo, 0) + valor

    return total_final


# ====================================
# CÁLCULO DE ADERÊNCIA
# ====================================

def calcular_adesao(paciente_id, data_referencia=None, tabela=None):
    """
    Compara o total esperado (desde o início do tratamento até a data de
    referência) com o total efetivamente registrado no histórico do
    paciente. Usa o esquema_manutencao prescrito e salvo no cadastro do
    paciente (não escolhe automaticamente). Retorna um relatório com
    percentual de aderência por modelo.
    """
    paciente = buscar_paciente(paciente_id)
    if paciente is None:
        raise Exception(f"Paciente não encontrado: {paciente_id}")

    if data_referencia is None:
        data_referencia = str(date.today())

    esperado = calcular_dose_esperada_acumulada(
        paciente["peso"], paciente["data_inicio_tratamento"], data_referencia,
        tabela=tabela, esquema_manutencao=paciente.get("esquema_manutencao")
    )
    realizado = somar_tomados_historico(paciente_id, data_limite=data_referencia)

    relatorio = {
        "paciente": paciente["nome"],
        "peso": paciente["peso"],
        "data_inicio_tratamento": paciente["data_inicio_tratamento"],
        "data_referencia": data_referencia,
        "fase_atual": esperado["fase_atual"],
        "dias_passados": esperado["dias_passados"],
        "por_modelo": {},
    }

    todos_modelos = set(esperado["total_esperado"].keys()) | set(realizado.keys())
    for modelo in todos_modelos:
        qtd_esperada = esperado["total_esperado"].get(modelo, 0)
        qtd_realizada = realizado.get(modelo, 0)
        pct = (qtd_realizada / qtd_esperada * 100) if qtd_esperada > 0 else None

        relatorio["por_modelo"][modelo] = {
            "esperado": qtd_esperada,
            "realizado": qtd_realizada,
            "percentual_aderencia": round(pct, 1) if pct is not None else None,
        }

    return relatorio


def imprimir_relatorio_adesao(relatorio):
    print()
    print("========================================")
    print(f"RELATÓRIO DE ADERÊNCIA - {relatorio['paciente']}")
    print("========================================")
    print(f"Peso: {relatorio['peso']}kg")
    print(f"Início do tratamento: {relatorio['data_inicio_tratamento']}")
    print(f"Data de referência: {relatorio['data_referencia']}")
    print(f"Dias de tratamento: {relatorio['dias_passados']}")
    print(f"Fase atual: {relatorio['fase_atual']}")
    print()
    for modelo, dados in relatorio["por_modelo"].items():
        pct = dados["percentual_aderencia"]
        pct_str = f"{pct}%" if pct is not None else "N/A"
        print(f"  {modelo}: esperado={dados['esperado']} | "
              f"realizado={dados['realizado']} | aderência={pct_str}")
    print("========================================")


if __name__ == "__main__":
    # Exemplo de uso manual (requer um paciente já cadastrado)
    from pacientes import cadastrar_paciente, buscar_paciente

    cpf_exemplo = "123.456.789-00"

    p = buscar_paciente(cpf_exemplo)
    if p is None:
        # Esquema de manutenção informado no cadastro (decisão do médico,
        # neste exemplo escolhendo 1x rh_300_150 -- ver dosagem.listar_opcoes_manutencao)
        p = cadastrar_paciente(cpf_exemplo, "Paciente Exemplo", 65, "2026-05-01",
                                esquema_manutencao={"rh_300_150": 2})

    # Leitura 1: cartela nova, 3 de 6 já tomados
    registrar_leitura(p["id"], "2026-05-10", [
        {"modelo": "rhze", "total": 6, "tomados": 3, "posicoes_tomadas": ["P1", "P2", "P3"],
         "possivel_consumo": 0, "posicoes_possivel": [], "intactos": 3}
    ])

    # Leitura 2: mesma cartela, progrediu para 5 de 6 tomados
    # (não deve somar com a anterior, só atualizar para o valor mais recente)
    registrar_leitura(p["id"], "2026-05-13", [
        {"modelo": "rhze", "total": 6, "tomados": 5, "posicoes_tomadas": ["P1", "P2", "P3", "P4", "P5"],
         "possivel_consumo": 0, "posicoes_possivel": [], "intactos": 1}
    ])

    # Leitura 3: cartela NOVA (tomados caiu de 5 para 2) -- deve fechar a
    # cartela anterior (contribui com 5) e começar a contar a nova (2)
    registrar_leitura(p["id"], "2026-05-16", [
        {"modelo": "rhze", "total": 6, "tomados": 2, "posicoes_tomadas": ["P1", "P2"],
         "possivel_consumo": 0, "posicoes_possivel": [], "intactos": 4}
    ])

    # Total esperado: 5 (cartela 1, fechada) + 2 (cartela 2, em uso) = 7
    print("Total tomados (deve ser 7, não 10):", somar_tomados_historico(p["id"]))

    relatorio = calcular_adesao(p["id"], "2026-05-16")
    imprimir_relatorio_adesao(relatorio)