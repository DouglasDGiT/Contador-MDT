import json


def carregar_tabela_dosagem(caminho="dosagem_tb.json"):
    with open(caminho, "r", encoding="utf-8-sig") as f:       return json.load(f)


def encontrar_faixa_peso(faixas, peso):
    for faixa in faixas:
        peso_min = faixa["peso_min"]
        peso_max = faixa["peso_max"]
        if peso >= peso_min and (peso_max is None or peso <= peso_max):
            return faixa
    return None


def listar_opcoes_manutencao(peso, tabela=None):
    if tabela is None:
        tabela = carregar_tabela_dosagem()
    faixa = encontrar_faixa_peso(tabela["fase_manutencao"]["faixas_peso"], peso)
    if faixa is None:
        raise ValueError(f"Nenhuma faixa de peso encontrada para {peso}kg (fase manutencao).")
    return faixa["opcoes"]


def validar_esquema_manutencao(peso, esquema_escolhido, tabela=None):
    opcoes_validas = listar_opcoes_manutencao(peso, tabela=tabela)
    if esquema_escolhido not in opcoes_validas:
        raise ValueError(f"Esquema {esquema_escolhido} nao e uma opcao valida para {peso}kg. Opcoes validas: {opcoes_validas}")
    return True


def calcular_dose_esperada(peso, fase, tabela=None, esquema_manutencao=None):
    if tabela is None:
        tabela = carregar_tabela_dosagem()
    if fase not in ("fase_intensiva", "fase_manutencao"):
        raise ValueError(f"Fase invalida: {fase}. Use 'fase_intensiva' ou 'fase_manutencao'.")
    dados_fase = tabela[fase]
    if fase == "fase_intensiva":
        faixa = encontrar_faixa_peso(dados_fase["faixas_peso"], peso)
        if faixa is None:
            raise ValueError(f"Nenhuma faixa de peso encontrada para {peso}kg.")
        return {
            "modelo_comprimido": dados_fase["modelo_comprimido"],
            "dose_diaria": {dados_fase["modelo_comprimido"]: faixa["comprimidos_por_dia"]},
            "duracao_meses": dados_fase["duracao_meses"],
        }
    if esquema_manutencao is None:
        opcoes = listar_opcoes_manutencao(peso, tabela=tabela)
        raise ValueError(f"Para fase_manutencao e necessario informar esquema_manutencao. Opcoes validas para {peso}kg: {opcoes}")
    validar_esquema_manutencao(peso, esquema_manutencao, tabela=tabela)
    return {
        "modelo_comprimido": None,
        "dose_diaria": esquema_manutencao,
        "duracao_meses": dados_fase["duracao_meses"],
    }


def calcular_dose_esperada_periodo(peso, fase, dias, tabela=None, esquema_manutencao=None):
    dose = calcular_dose_esperada(peso, fase, tabela=tabela, esquema_manutencao=esquema_manutencao)
    total = {modelo: qtd * dias for modelo, qtd in dose["dose_diaria"].items()}
    return {"dias": dias, "total_esperado": total, "dose_diaria": dose["dose_diaria"]}


if __name__ == "__main__":
    tabela = carregar_tabela_dosagem()
    print("Exemplo -- paciente de 45kg, fase intensiva:")
    print(calcular_dose_esperada(45, "fase_intensiva", tabela))
    print("\nExemplo -- paciente de 65kg, opcoes validas de manutencao:")
    print(listar_opcoes_manutencao(65, tabela))
    print("\nExemplo -- paciente de 65kg, medico prescreveu 2x rh_300_150:")
    print(calcular_dose_esperada(65, "fase_manutencao", tabela, esquema_manutencao={"rh_300_150": 2}))
    print("\nExemplo -- paciente de 45kg, fase intensiva, 14 dias:")
    print(calcular_dose_esperada_periodo(45, "fase_intensiva", 14, tabela))

