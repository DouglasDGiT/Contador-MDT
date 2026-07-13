import cv2
import os
import json
import sys
import numpy as np


# ====================================
# MÉTRICAS DISPONÍVEIS
# ====================================
#
# "saturacao": mede o % de pixels com saturação de cor alta (canal S do
# HSV). Funciona bem quando o sinal de rompimento é uma mudança geral de
# quanto colorido o pixel é.
#
# "matiz_verde_amarelo": mede o % de pixels dentro de uma faixa específica
# de matiz (H do HSV, tipicamente verde-amarelo) com saturação mínima.
# Mais robusto que a saturação genérica quando reflexos/embaçado no
# plástico reduzem a saturação de uma cor que ainda está presente --
# a faixa de matiz continua reconhecendo a cor mesmo mais "fraca".

def calcular_pct_saturado(img, limiar_saturacao=60):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturacao = hsv[:, :, 1]
    return np.sum(saturacao > limiar_saturacao) / saturacao.size * 100


def calcular_pct_matiz_verde_amarelo(img, matiz_min=25, matiz_max=95, saturacao_min=30):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    matiz = hsv[:, :, 0]
    saturacao = hsv[:, :, 1]
    mascara = (matiz >= matiz_min) & (matiz <= matiz_max) & (saturacao > saturacao_min)
    return np.sum(mascara) / mascara.size * 100


METRICAS = {
    "saturacao": calcular_pct_saturado,
    "matiz_verde_amarelo": calcular_pct_matiz_verde_amarelo,
}


def calcular_score(caminho_img, metrica, parametros_metrica):
    img = cv2.imread(caminho_img)
    if img is None:
        return None

    funcao = METRICAS.get(metrica)
    if funcao is None:
        raise Exception(
            f"Métrica desconhecida: '{metrica}'. "
            f"Opções válidas: {list(METRICAS.keys())}"
        )

    return funcao(img, **parametros_metrica)


def comparar_blisters(modelo, imprimir=True):
    """
    Analisa os recortes de um modelo específico e classifica cada posição
    como TOMADO / POSSIVEL / INTACTO, conforme a config (métrica, direção
    e limiares) definida em modelos/{modelo}/config.json.
    Retorna a lista de resultados: [{"posicao", "score", "status"}, ...]
    """
    pasta_teste = f"recortes/{modelo}"
    config_path = f"modelos/{modelo}/config.json"

    if not os.path.exists(config_path):
        raise Exception(
            f"Config não encontrada: {config_path}\n"
            f'Crie um config.json com: {{"metrica": "saturacao" ou '
            f'"matiz_verde_amarelo", "direcao": "alta_e_tomado" ou '
            f'"baixa_e_tomado", "limiar_tomado": <numero>, '
            f'"limiar_possivel": <numero>, "parametros_metrica": {{}}}}'
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Compatibilidade com configs antigas (direcao "alta_saturacao_e_tomado" /
    # "baixa_saturacao_e_tomado"), que assumiam sempre a métrica "saturacao"
    metrica = config.get("metrica", "saturacao")
    direcao_raw = config["direcao"]
    if direcao_raw in ("alta_saturacao_e_tomado", "baixa_saturacao_e_tomado"):
        direcao = "alta_e_tomado" if direcao_raw == "alta_saturacao_e_tomado" else "baixa_e_tomado"
    else:
        direcao = direcao_raw

    limiar_tomado = config["limiar_tomado"]
    limiar_possivel = config["limiar_possivel"]
    parametros_metrica = config.get("parametros_metrica", {})

    if metrica not in METRICAS:
        raise Exception(f"Métrica inválida em {config_path}: {metrica}. Opções: {list(METRICAS.keys())}")

    if direcao not in ("alta_e_tomado", "baixa_e_tomado"):
        raise Exception(f"Valor inválido para 'direcao' em {config_path}: {direcao_raw}")

    if not os.path.isdir(pasta_teste):
        raise Exception(f"Pasta de recortes não encontrada: {pasta_teste}")

    resultados = []
    for arquivo in sorted(os.listdir(pasta_teste)):
        if not arquivo.endswith(".png"):
            continue

        caminho = os.path.join(pasta_teste, arquivo)
        score = calcular_score(caminho, metrica, parametros_metrica)
        if score is None:
            continue

        if direcao == "alta_e_tomado":
            if score > limiar_tomado:
                status = "TOMADO"
            elif score > limiar_possivel:
                status = "POSSIVEL"
            else:
                status = "INTACTO"
        else:
            if score < limiar_tomado:
                status = "TOMADO"
            elif score < limiar_possivel:
                status = "POSSIVEL"
            else:
                status = "INTACTO"

        resultados.append({
            "posicao": arquivo.replace(".png", ""),
            "score": round(float(score), 2),
            "status": status
        })

    if len(resultados) == 0:
        raise Exception(f"Nenhuma imagem encontrada em {pasta_teste}")

    if direcao == "alta_e_tomado":
        resultados.sort(key=lambda x: x["score"], reverse=True)
    else:
        resultados.sort(key=lambda x: x["score"])

    if imprimir:
        print()
        print("====================================")
        print(f"AUDITORIA DE CONSUMO - {modelo}")
        print("====================================")
        print()
        print(f"Métrica: {metrica}")
        print(f"Direção: {direcao}")
        print(f"Limiar TOMADO: {limiar_tomado}%")
        print(f"Limiar POSSÍVEL: {limiar_possivel}%")
        print()
        print("RESULTADOS:")
        print()
        for r in resultados:
            print(f"{r['posicao']}.png: {r['score']:.2f}% | {r['status']}")
        print()
        print("Fim da análise.")

    return resultados


# Permite continuar rodando este arquivo sozinho pelo terminal, para debug:
# python src/comparar_blisters.py rh_150_75
if __name__ == "__main__":
    modelo_cli = "rh_150_75"
    if len(sys.argv) > 1:
        modelo_cli = sys.argv[1]
    comparar_blisters(modelo_cli)