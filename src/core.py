"""
core.py -- Lógica de negócio compartilhada entre qualquer "porta de entrada"
(hoje, o site). Esta camada não sabe nada sobre HTTP,
formulários ou mensagens -- só recebe SINAN + caminho de uma foto, e
devolve um resultado estruturado.
"""

import os
import shutil
from datetime import date

from alinhar_cartela import alinhar_cartela
from recortar_blisters import recortar_blisters
from comparar_blisters import comparar_blisters
from pacientes import buscar_paciente, buscar_pacientes_por_nome
from adesao import registrar_leitura, calcular_adesao, calcular_fase_atual, hoje_brasil


def identificar_paciente_por_texto(texto):
    """
    Aceita o texto digitado pelo paciente (SINAN ou nome completo) e tenta
    identificar de qual se trata:
      - Se for só dígitos (ignorando espaços/pontuação) -> busca por SINAN.
      - Caso contrário -> busca por nome (pode haver mais de um resultado).

    Retorna um dicionário:
      {"paciente": <dict ou None>, "candidatos": <lista, só populada se
       houver mais de 1 resultado por nome>}
    """
    texto_limpo = texto.strip()
    so_digitos = texto_limpo.replace(" ", "").replace(".", "").replace("-", "").isdigit()

    if so_digitos:
        paciente = buscar_paciente(texto_limpo)
        return {"paciente": paciente, "candidatos": []}

    candidatos = buscar_pacientes_por_nome(texto_limpo)
    if len(candidatos) == 1:
        return {"paciente": candidatos[0], "candidatos": []}
    elif len(candidatos) == 0:
        return {"paciente": None, "candidatos": []}
    else:
        # Mais de um paciente com esse nome -- quem chamou precisa
        # perguntar ao usuário qual deles é, antes de prosseguir
        return {"paciente": None, "candidatos": candidatos}


def decidir_modelo_esperado(paciente, fase):
    """
    Decide qual modelo de cartela esperar, dado a fase do tratamento.
    Na fase de manutenção com esquema de 2 modelos simultâneos, não é
    possível decidir sozinho -- retorna None e a camada de cima deve
    perguntar explicitamente qual cartela está sendo enviada.
    """
    if fase == "fase_intensiva":
        return "rhze"
    elif fase == "fase_manutencao":
        esquema = paciente.get("esquema_manutencao")
        if esquema and len(esquema) == 1:
            return list(esquema.keys())[0]
        return None
    return None


def montar_resumo(modelo, resultados):
    tomados = [r for r in resultados if r["status"] == "TOMADO"]
    possiveis = [r for r in resultados if r["status"] == "POSSIVEL"]
    intactos = [r for r in resultados if r["status"] == "INTACTO"]
    return {
        "modelo": modelo,
        "total": len(resultados),
        "tomados": len(tomados),
        "posicoes_tomadas": [t["posicao"] for t in tomados],
        "possivel_consumo": len(possiveis),
        "posicoes_possivel": [p["posicao"] for p in possiveis],
        "intactos": len(intactos),
    }


def processar_envio_foto(paciente_id, caminho_foto_temporario, modelo_forcado=None):
    """
    Função central: recebe o ID (SINAN) já identificado do paciente e o
    caminho de um arquivo de imagem já salvo em disco, roda o pipeline
    completo e devolve um dicionário com o resultado.

    A identificação do paciente (se veio de SINAN digitado direto, ou de
    nome já desambiguado) acontece ANTES de chamar esta função -- ver
    identificar_paciente_por_texto().

    modelo_forcado: usado quando o paciente precisa enviar mais de uma
    cartela (ex: fase de manutenção com 2 modelos) e a porta de entrada
    já perguntou explicitamente qual delas é.
    """
    paciente = buscar_paciente(paciente_id)
    if paciente is None:
        return {
            "sucesso": False,
            "mensagem": "Número do SINAN não encontrado. Procure o agente de saúde "
                        "para verificar o cadastro.",
        }

    fase = calcular_fase_atual(
        paciente["data_inicio_tratamento"],
        fase_inicial=paciente.get("fase_inicial") or "fase_intensiva",
    )
    modelo = modelo_forcado or decidir_modelo_esperado(paciente, fase)

    if modelo is None:
        return {
            "sucesso": False,
            "mensagem": "Não foi possível determinar automaticamente qual medicamento "
                        "esperar. Informe qual cartela está enviando.",
            "requer_escolha_modelo": True,
            "paciente": paciente,
        }

    destino = f"imagens/uploads/{modelo}_foto_usuario.png"
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copyfile(caminho_foto_temporario, destino)

    try:
        alinhar_cartela(modelo)
        recortar_blisters(modelo)
        resultados = comparar_blisters(modelo, imprimir=False)
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": "Não foi possível processar a foto. Verifique a iluminação "
                        "e o enquadramento da cartela e tente novamente.",
            "erro_tecnico": str(e),
        }

    resumo = montar_resumo(modelo, resultados)
    registrar_leitura(paciente["id"], str(hoje_brasil()), [resumo])

    return {
        "sucesso": True,
        "mensagem": f"{resumo['tomados']} de {resumo['total']} comprimidos "
                    f"identificados como tomados nesta cartela.",
        "resumo": resumo,
        "paciente": paciente,
        "fase": fase,
    }