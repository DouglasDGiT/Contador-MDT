import json
import os
import re
import unicodedata
from datetime import date

PASTA_PACIENTES = "pacientes"
ARQUIVO_INDICE = os.path.join(PASTA_PACIENTES, "pacientes.json")


def _carregar_indice():
    if not os.path.exists(ARQUIVO_INDICE):
        return []
    with open(ARQUIVO_INDICE, "r", encoding="utf-8") as f:
        return json.load(f)


def _salvar_indice(pacientes):
    os.makedirs(PASTA_PACIENTES, exist_ok=True)
    with open(ARQUIVO_INDICE, "w", encoding="utf-8") as f:
        json.dump(pacientes, f, indent=4, ensure_ascii=False)


def normalizar_id(paciente_id):
    """
    Remove pontuação do ID (útil para CPF: "123.456.789-00" -> "12345678900"),
    garantindo que o mesmo paciente não seja cadastrado duas vezes só por
    causa de formatação diferente na hora de digitar.
    """
    return re.sub(r"[^0-9A-Za-z]", "", str(paciente_id))


def normalizar_nome(nome):
    """
    Remove acentos, baixa para minúsculas e colapsa espaços extras, para
    que "José da Silva", "jose  DA silva" e "JOSÉ DA SILVA" sejam tratados
    como o mesmo texto na hora de buscar por nome.
    """
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", sem_acento.strip().lower())


def buscar_pacientes_por_nome(nome_busca):
    """
    Busca pacientes cujo nome cadastrado bata (exatamente, após normalizar)
    com o texto informado. Como nome NÃO é garantidamente único (diferente
    do ID/SINAN), retorna uma LISTA -- pode vir vazia, com 1, ou com vários
    resultados (nesse caso, quem chamou precisa desambiguar com o usuário).
    """
    alvo = normalizar_nome(nome_busca)
    pacientes = _carregar_indice()
    return [p for p in pacientes if normalizar_nome(p["nome"]) == alvo]


def cadastrar_paciente(paciente_id, nome, peso, data_inicio_tratamento, esquema_manutencao=None):
    """
    Cadastra um novo paciente com ID único informado externamente
    (no sistema real, o CPF). Lança exceção se o ID já existir.

    data_inicio_tratamento: string no formato "YYYY-MM-DD"
    esquema_manutencao: dict opcional com o esquema de manutenção JÁ
        PRESCRITO PELO MÉDICO (ex: {"rh_300_150": 1}), usado quando o
        paciente chegar na fase de manutenção. Pode ser definido depois,
        via definir_esquema_manutencao(), se ainda não for conhecido no
        momento do cadastro (comum, já que a fase intensiva vem primeiro).
    """
    paciente_id = normalizar_id(paciente_id)

    if buscar_paciente(paciente_id) is not None:
        raise Exception(
            f"Já existe um paciente cadastrado com esse ID ({paciente_id}). "
            f"Use buscar_paciente() para consultar, ou atualizar_peso() para editar."
        )

    pacientes = _carregar_indice()

    paciente = {
        "id": paciente_id,
        "nome": nome,
        "peso": peso,
        "data_inicio_tratamento": data_inicio_tratamento,
        "esquema_manutencao": esquema_manutencao,
    }

    pacientes.append(paciente)
    _salvar_indice(pacientes)

    pasta_paciente = os.path.join(PASTA_PACIENTES, paciente["id"])
    os.makedirs(pasta_paciente, exist_ok=True)

    print(f"Paciente cadastrado: {paciente['nome']} (id: {paciente['id']})")
    return paciente


def definir_esquema_manutencao(paciente_id, esquema_manutencao):
    """
    Define ou atualiza o esquema de manutenção prescrito pelo médico
    (ex: {"rh_300_150": 1} ou {"rh_150_75": 3}). Necessário antes de
    calcular aderência na fase de manutenção.
    """
    paciente_id = normalizar_id(paciente_id)
    pacientes = _carregar_indice()
    for p in pacientes:
        if p["id"] == paciente_id:
            p["esquema_manutencao"] = esquema_manutencao
            _salvar_indice(pacientes)
            print(f"Esquema de manutenção definido para {p['nome']}: {esquema_manutencao}")
            return p
    raise Exception(f"Paciente não encontrado: {paciente_id}")


def buscar_paciente(paciente_id):
    paciente_id = normalizar_id(paciente_id)
    pacientes = _carregar_indice()
    for p in pacientes:
        if p["id"] == paciente_id:
            return p
    return None


def listar_pacientes():
    return _carregar_indice()


def atualizar_peso(paciente_id, novo_peso):
    """
    Atualiza o peso do paciente (relevante se a faixa de peso mudar
    durante o tratamento, o que altera a dose esperada).
    """
    paciente_id = normalizar_id(paciente_id)
    pacientes = _carregar_indice()
    for p in pacientes:
        if p["id"] == paciente_id:
            p["peso"] = novo_peso
            _salvar_indice(pacientes)
            print(f"Peso atualizado: {p['nome']} -> {novo_peso}kg")
            return p
    raise Exception(f"Paciente não encontrado: {paciente_id}")


if __name__ == "__main__":
    # Exemplo de uso manual
    p = cadastrar_paciente("123.456.789-00", "Paciente Teste", 65, str(date.today()))
    print(buscar_paciente("12345678900"))       # busca funciona mesmo sem pontuação
    print(buscar_paciente("123.456.789-00"))    # e também com pontuação
    print(listar_pacientes())