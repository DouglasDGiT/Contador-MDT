import os
import sys
import json
import shutil
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alinhar_cartela import alinhar_cartela
from recortar_blisters import recortar_blisters
from comparar_blisters import comparar_blisters
from pacientes import buscar_paciente, cadastrar_paciente
from adesao import registrar_leitura, calcular_adesao, imprimir_relatorio_adesao

PASTA_MODELOS = "modelos"
PASTA_UPLOADS = "imagens/uploads"


def listar_modelos_disponiveis():
    if not os.path.isdir(PASTA_MODELOS):
        return []

    modelos = []
    for nome in sorted(os.listdir(PASTA_MODELOS)):
        caminho = os.path.join(PASTA_MODELOS, nome)
        if not os.path.isdir(caminho):
            continue

        arquivos_necessarios = ["referencia.png", "blisters.json",
                                 "pontos_controle.json", "config.json"]
        faltando = [a for a in arquivos_necessarios
                    if not os.path.exists(os.path.join(caminho, a))]

        modelos.append((nome, faltando))

    return modelos


def identificar_paciente():
    """
    Pede o ID do paciente (CPF, no sistema real). Se não existir, oferece
    cadastro na hora. Retorna o registro do paciente.
    """
    print()
    print("====================================")
    print("IDENTIFICAÇÃO DO PACIENTE")
    print("====================================")

    paciente_id = input("CPF do paciente: ").strip()

    paciente = buscar_paciente(paciente_id)

    if paciente is not None:
        print(f"Paciente encontrado: {paciente['nome']} "
              f"(peso: {paciente['peso']}kg, início: {paciente['data_inicio_tratamento']})")

        atualizar = input("Atualizar peso cadastrado? (s/n): ").strip().lower()
        if atualizar == "s":
            from pacientes import atualizar_peso
            novo_peso = float(input("Novo peso (kg): ").strip())
            paciente = atualizar_peso(paciente_id, novo_peso)

        return paciente

    print("Paciente não encontrado. Cadastro necessário.")
    nome = input("Nome do paciente: ").strip()
    peso = float(input("Peso (kg): ").strip())
    data_inicio = input(
        f"Data de início do tratamento (AAAA-MM-DD, ENTER para hoje [{date.today()}]): "
    ).strip()
    if data_inicio == "":
        data_inicio = str(date.today())

    return cadastrar_paciente(paciente_id, nome, peso, data_inicio)


def escolher_cartelas_para_processar():
    modelos = listar_modelos_disponiveis()

    if not modelos:
        print("Nenhum modelo encontrado em 'modelos/'.")
        sys.exit(1)

    print()
    print("====================================")
    print("MODELOS DISPONÍVEIS")
    print("====================================")
    for i, (nome, faltando) in enumerate(modelos, start=1):
        status = "OK" if not faltando else f"INCOMPLETO (faltando: {', '.join(faltando)})"
        print(f"  {i}. {nome}  [{status}]")
    print()

    selecionadas = []

    while True:
        escolha = input(
            f"Escolha um modelo para processar (1-{len(modelos)}), "
            f"ou ENTER para finalizar a lista: "
        ).strip()

        if escolha == "":
            break

        if not escolha.isdigit() or not (1 <= int(escolha) <= len(modelos)):
            print("Opção inválida, tente novamente.")
            continue

        nome, faltando = modelos[int(escolha) - 1]
        if faltando:
            print(f"AVISO: modelo '{nome}' incompleto (faltando: {', '.join(faltando)}).")
            confirmar = input("Continuar mesmo assim? (s/n): ").strip().lower()
            if confirmar != "s":
                continue

        caminho_padrao = os.path.join(PASTA_UPLOADS, f"{nome}_foto_usuario.png")
        caminho_foto = input(
            f"  Caminho da foto para '{nome}' (ENTER para usar {caminho_padrao}): "
        ).strip()
        if caminho_foto == "":
            caminho_foto = caminho_padrao

        if not os.path.exists(caminho_foto):
            print(f"  AVISO: arquivo não encontrado em '{caminho_foto}'. Pulando esse modelo.")
            continue

        selecionadas.append((nome, caminho_foto))
        print(f"  -> '{nome}' adicionado à fila.\n")

    return selecionadas


def processar_cartela(modelo, caminho_foto):
    print()
    print(f"==== Processando modelo: {modelo} ====")
    print(f"Foto: {caminho_foto}")

    os.makedirs(PASTA_UPLOADS, exist_ok=True)
    destino = os.path.join(PASTA_UPLOADS, f"{modelo}_foto_usuario.png")
    if os.path.abspath(caminho_foto) != os.path.abspath(destino):
        shutil.copyfile(caminho_foto, destino)

    try:
        alinhar_cartela(modelo)
    except Exception as e:
        print(f"  ERRO no alinhamento: {e}")
        return {"modelo": modelo, "erro": f"falha no alinhamento: {e}", "resultados": []}

    try:
        recortar_blisters(modelo)
    except Exception as e:
        print(f"  ERRO no recorte: {e}")
        return {"modelo": modelo, "erro": f"falha no recorte: {e}", "resultados": []}

    try:
        resultados = comparar_blisters(modelo, imprimir=True)
    except Exception as e:
        print(f"  ERRO na comparação: {e}")
        return {"modelo": modelo, "erro": f"falha na comparação: {e}", "resultados": []}

    return {"modelo": modelo, "erro": None, "resultados": resultados}


def montar_resumo_consolidado(relatorios):
    """
    Monta o resumo no mesmo formato que já era salvo em
    resultados/resumo_consolidado.json, e retorna a lista (não só imprime),
    para poder ser passada para registrar_leitura().
    """
    resumo = []
    for r in relatorios:
        modelo = r["modelo"]

        if r["erro"]:
            resumo.append({"modelo": modelo, "erro": r["erro"]})
            continue

        tomados = [x for x in r["resultados"] if x["status"] == "TOMADO"]
        possiveis = [x for x in r["resultados"] if x["status"] == "POSSIVEL"]
        intactos = [x for x in r["resultados"] if x["status"] == "INTACTO"]
        total = len(r["resultados"])

        resumo.append({
            "modelo": modelo,
            "total": total,
            "tomados": len(tomados),
            "posicoes_tomadas": [t["posicao"] for t in tomados],
            "possivel_consumo": len(possiveis),
            "posicoes_possivel": [p["posicao"] for p in possiveis],
            "intactos": len(intactos),
        })

    return resumo


def imprimir_resumo_consolidado(resumo):
    print()
    print("========================================")
    print("RESUMO CONSOLIDADO")
    print("========================================")

    for r in resumo:
        modelo = r["modelo"]
        print()
        print(f"--- {modelo} ---")

        if r.get("erro"):
            print(f"  ERRO: {r['erro']}")
            continue

        print(f"  Total de posições: {r['total']}")
        print(f"  Tomados: {r['tomados']} {r['posicoes_tomadas'] if r['posicoes_tomadas'] else ''}")
        print(f"  Possível consumo: {r['possivel_consumo']} "
              f"{r['posicoes_possivel'] if r['posicoes_possivel'] else ''}")
        print(f"  Intactos: {r['intactos']}")

    print()
    print("========================================")

    os.makedirs("resultados", exist_ok=True)
    caminho_saida = os.path.join("resultados", "resumo_consolidado.json")
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(resumo, f, indent=4, ensure_ascii=False)
    print(f"Resumo salvo em: {caminho_saida}")


def main():
    print()
    print("====================================")
    print("CONTADOR MDT - ANÁLISE MULTI-CARTELA")
    print("====================================")

    paciente = identificar_paciente()

    cartelas = escolher_cartelas_para_processar()

    if not cartelas:
        print("Nenhuma cartela selecionada. Encerrando.")
        sys.exit(0)

    relatorios = []
    for modelo, caminho_foto in cartelas:
        relatorio = processar_cartela(modelo, caminho_foto)
        relatorios.append(relatorio)

    resumo = montar_resumo_consolidado(relatorios)
    imprimir_resumo_consolidado(resumo)

    # Registra a leitura no histórico do paciente e calcula aderência
    data_hoje = str(date.today())
    registrar_leitura(paciente["id"], data_hoje, resumo)

    relatorio_adesao = calcular_adesao(paciente["id"], data_hoje)
    imprimir_relatorio_adesao(relatorio_adesao)


if __name__ == "__main__":
    main()