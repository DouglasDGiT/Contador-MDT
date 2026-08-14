import json
import re
import unicodedata

from db import get_connection, init_db

# Garante que as tabelas existem assim que este módulo é importado
init_db()


def normalizar_id(paciente_id):
    """
    Remove pontuação do ID (útil para CPF/SINAN: "123.456-00" -> "12345600"),
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


def _row_para_dict(row):
    d = dict(row)
    d["esquema_manutencao"] = json.loads(d["esquema_manutencao"]) if d.get("esquema_manutencao") else None
    return d


def cadastrar_paciente(paciente_id, nome, peso, data_inicio_tratamento, esquema_manutencao=None):
    """
    Cadastra um novo paciente com ID único informado externamente
    (no sistema real, o número do SINAN). Lança exceção se o ID já existir.

    data_inicio_tratamento: string no formato "YYYY-MM-DD"
    esquema_manutencao: dict opcional com o esquema de manutenção JÁ
        PRESCRITO PELO MÉDICO (ex: {"rh_300_150": 1}), usado quando o
        paciente chegar na fase de manutenção. Pode ser definido depois,
        via definir_esquema_manutencao(), se ainda não for conhecido no
        momento do cadastro.
    """
    paciente_id = normalizar_id(paciente_id)

    if buscar_paciente(paciente_id) is not None:
        raise Exception(
            f"Já existe um paciente cadastrado com esse ID ({paciente_id}). "
            f"Use buscar_paciente() para consultar, ou atualizar_peso() para editar."
        )

    conn = get_connection()
    conn.execute(
        "INSERT INTO pacientes (id, nome, peso, data_inicio_tratamento, esquema_manutencao) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            paciente_id, nome, peso, data_inicio_tratamento,
            json.dumps(esquema_manutencao, ensure_ascii=False) if esquema_manutencao else None,
        ),
    )
    conn.commit()
    conn.close()

    print(f"Paciente cadastrado: {nome} (id: {paciente_id})")
    return buscar_paciente(paciente_id)


def buscar_paciente(paciente_id):
    paciente_id = normalizar_id(paciente_id)
    conn = get_connection()
    row = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
    conn.close()
    return _row_para_dict(row) if row else None


def buscar_pacientes_por_nome(nome_busca):
    """
    Busca pacientes cujo nome cadastrado bata (exatamente, após normalizar)
    com o texto informado. Como nome NÃO é garantidamente único (diferente
    do ID/SINAN), retorna uma LISTA -- pode vir vazia, com 1, ou com vários
    resultados (nesse caso, quem chamou precisa desambiguar com o usuário).
    """
    alvo = normalizar_nome(nome_busca)
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pacientes").fetchall()
    conn.close()
    return [_row_para_dict(r) for r in rows if normalizar_nome(r["nome"]) == alvo]


def listar_pacientes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pacientes ORDER BY nome").fetchall()
    conn.close()
    return [_row_para_dict(r) for r in rows]


def atualizar_peso(paciente_id, novo_peso):
    """
    Atualiza o peso do paciente (relevante se a faixa de peso mudar
    durante o tratamento, o que altera a dose esperada).
    """
    paciente_id = normalizar_id(paciente_id)
    conn = get_connection()
    cursor = conn.execute("UPDATE pacientes SET peso = ? WHERE id = ?", (novo_peso, paciente_id))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise Exception(f"Paciente não encontrado: {paciente_id}")

    paciente = buscar_paciente(paciente_id)
    print(f"Peso atualizado: {paciente['nome']} -> {novo_peso}kg")
    return paciente


def definir_esquema_manutencao(paciente_id, esquema_manutencao):
    """
    Define ou atualiza o esquema de manutenção prescrito pelo médico
    (ex: {"rh_300_150": 1} ou {"rh_150_75": 3}). Necessário antes de
    calcular aderência na fase de manutenção.
    """
    paciente_id = normalizar_id(paciente_id)
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE pacientes SET esquema_manutencao = ? WHERE id = ?",
        (json.dumps(esquema_manutencao, ensure_ascii=False), paciente_id),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise Exception(f"Paciente não encontrado: {paciente_id}")

    paciente = buscar_paciente(paciente_id)
    print(f"Esquema de manutenção definido para {paciente['nome']}: {esquema_manutencao}")
    return paciente


if __name__ == "__main__":
    from datetime import date
    p = cadastrar_paciente("123.456.789-00", "Paciente Teste", 65, str(date.today()))
    print(buscar_paciente("12345678900"))
    print(buscar_paciente("123.456.789-00"))
    print(listar_pacientes())