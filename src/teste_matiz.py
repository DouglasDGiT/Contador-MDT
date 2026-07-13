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
    matiz = hsv[:, :, 0]
    saturacao = hsv[:, :, 1]

    mascara_verde_amarelo = (matiz >= 25) & (matiz <= 95) & (saturacao > 30)
    pct_verde_amarelo = np.sum(mascara_verde_amarelo) / mascara_verde_amarelo.size * 100

    resultados.append((arquivo, pct_verde_amarelo))

resultados.sort(key=lambda x: x[1])

print("Arquivo | pct verde/amarelo")
for nome, pct in resultados:
    print(f"{nome}: {pct:.2f}%")
