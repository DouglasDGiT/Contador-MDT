import os
import sys
import json
import shutil

# Garante que 'src' está no caminho de import, e importa as funções
# diretamente dos outros scripts -- tudo roda no mesmo processo Python,
# então não existe risco de rodar uma versão desatualizada de arquivo
# salva no disco (o que já causou bugs difíceis de rastrear antes).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alinhar_cartela import alinhar_cartela
from recortar_blisters import recortar_blisters
from comparar_blisters import comparar_blisters

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
    """
    Roda o pipeline completo (copiar foto -> alinhar -> recortar -> analisar)
    para uma única cartela, devolvendo o resumo estruturado.
    """
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


def imprimir_resumo_consolidado(relatorios):
    print()
    print("========================================")
    print("RESUMO CONSOLIDADO")
    print("========================================")

    resumo_json = []

    for r in relatorios:
        modelo = r["modelo"]
        print()
        print(f"--- {modelo} ---")

        if r["erro"]:
            print(f"  ERRO: {r['erro']}")
            resumo_json.append({"modelo": modelo, "erro": r["erro"]})
            continue

        tomados = [x for x in r["resultados"] if x["status"] == "TOMADO"]
        possiveis = [x for x in r["resultados"] if x["status"] == "POSSIVEL"]
        intactos = [x for x in r["resultados"] if x["status"] == "INTACTO"]
        total = len(r["resultados"])

        print(f"  Total de posições: {total}")
        print(f"  Tomados: {len(tomados)} {[t['posicao'] for t in tomados] if tomados else ''}")
        print(f"  Possível consumo: {len(possiveis)} {[p['posicao'] for p in possiveis] if possiveis else ''}")
        print(f"  Intactos: {len(intactos)}")

        resumo_json.append({
            "modelo": modelo,
            "total": total,
            "tomados": len(tomados),
            "posicoes_tomadas": [t["posicao"] for t in tomados],
            "possivel_consumo": len(possiveis),
            "posicoes_possivel": [p["posicao"] for p in possiveis],
            "intactos": len(intactos),
        })

    print()
    print("========================================")

    os.makedirs("resultados", exist_ok=True)
    caminho_saida = os.path.join("resultados", "resumo_consolidado.json")
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(resumo_json, f, indent=4, ensure_ascii=False)
    print(f"Resumo salvo em: {caminho_saida}")


def main():
    print()
    print("====================================")
    print("CONTADOR MDT - ANÁLISE MULTI-CARTELA")
    print("====================================")

    cartelas = escolher_cartelas_para_processar()

    if not cartelas:
        print("Nenhuma cartela selecionada. Encerrando.")
        sys.exit(0)

    relatorios = []
    for modelo, caminho_foto in cartelas:
        relatorio = processar_cartela(modelo, caminho_foto)
        relatorios.append(relatorio)

    imprimir_resumo_consolidado(relatorios)


if __name__ == "__main__":
    main()