import cv2
import os
import numpy as np

PASTA_TESTE = "recortes/recortes_teste"

resultados = []

# ==========================
# ANALISA TODOS OS BLISTERS
# ==========================

for arquivo in sorted(os.listdir(PASTA_TESTE)):

    caminho = os.path.join(
        PASTA_TESTE,
        arquivo
    )

    img = cv2.imread(
        caminho,
        cv2.IMREAD_GRAYSCALE
    )

    if img is None:
        continue

    # Região central do blister
    h, w = img.shape

    miolo = img[
        int(h * 0.20):int(h * 0.80),
        int(w * 0.20):int(w * 0.80)
    ]

    # Desvio padrão
    score = np.std(miolo)

    resultados.append(
        (arquivo, score)
    )

# ==================================
# CÁLCULO AUTOMÁTICO DO LIMIAR
# ==================================

valores = [score for _, score in resultados]

media = np.mean(valores)
desvio = np.std(valores)

# 2 desvios padrão acima da média
limiar = media + (2 * desvio)

# ==================================
# ORDENA RESULTADOS
# ==================================

resultados.sort(
    key=lambda x: x[1],
    reverse=True
)

print("\n==============================")
print("AUDITORIA DE CONSUMO MDT")
print("==============================\n")

print(f"Média: {media:.2f}")
print(f"Desvio padrão global: {desvio:.2f}")
print(f"Limiar calculado: {limiar:.2f}")

print("\nRESULTADOS:\n")

# ==================================
# CLASSIFICAÇÃO
# ==================================

for nome, score in resultados:

    distancia = score - limiar

    if distancia >= 3:
        status = "🔴 TOMADO (ALTA CONFIANÇA)"

    elif distancia >= 0:
        status = "🟡 POSSÍVEL CONSUMO"

    else:
        status = "🟢 INTACTO"

    print(
    f"{nome}: {score:.2f} -> {status}"
)

print("\nFim da análise.")