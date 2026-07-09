import cv2
import os
import numpy as np

MODELO = "rh_150_75"
PASTA_TESTE = f"recortes/{MODELO}"

resultados = []

for arquivo in sorted(os.listdir(PASTA_TESTE)):
    if not arquivo.endswith(".png"):
        continue

    caminho = os.path.join(PASTA_TESTE, arquivo)
    img = cv2.imread(caminho)
    if img is None:
        continue

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturacao = hsv[:, :, 1]

    pct_saturado = np.sum(saturacao > 60) / saturacao.size * 100

    resultados.append((arquivo, pct_saturado))

if len(resultados) == 0:
    raise Exception(f"Nenhuma imagem encontrada em {PASTA_TESTE}")

valores = np.array([s for _, s in resultados])
mediana = np.median(valores)
mad = np.median(np.abs(valores - mediana)) * 1.4826  # equivalente robusto ao desvio padrão

# Como a maioria dos scores é ~0, usamos limiares absolutos + estatísticos,
# o que fica mais seguro nesse tipo de distribuição (muitos zeros, poucos outliers)
LIMIAR_TOMADO_ABSOLUTO = 15.0    # % de pixels saturados -- ajuste conforme necessário
LIMIAR_POSSIVEL_ABSOLUTO = 5.0

resultados.sort(key=lambda x: x[1], reverse=True)

print(f"\nMediana: {mediana:.2f}% | MAD: {mad:.2f}\n")
print("RESULTADOS:\n")

for nome, score in resultados:
    if score > LIMIAR_TOMADO_ABSOLUTO:
        status = "🔴 TOMADO (ALTA CONFIANÇA)"
    elif score > LIMIAR_POSSIVEL_ABSOLUTO:
        status = "🟡 POSSÍVEL CONSUMO"
    else:
        status = "🟢 INTACTO"
    print(f"{nome}: {score:.2f}% saturado | {status}")