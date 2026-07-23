import json
import os
import re
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


def cadastrar_paciente(paciente_id, nome, peso, data_inicio_tratamento):
    """
    Cadastra um novo paciente com ID único informado externamente
    (no sistema real, o CPF). Lança exceção se o ID já existir.

    data_inicio_tratamento: string no formato "YYYY-MM-DD"
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
    }

    pacientes.append(paciente)
    _salvar_indice(pacientes)

    pasta_paciente = os.path.join(PASTA_PACIENTES, paciente["id"])
    os.makedirs(pasta_paciente, exist_ok=True)

    print(f"Paciente cadastrado: {paciente['nome']} (id: {paciente['id']})")
    return paciente


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