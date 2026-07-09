import cv2
import json
import os

# ====================================
# CONFIGURAÇÃO
# ====================================

MODELO = "rh_150_75"

IMAGEM = "alinhadas/cartela_alinhada.png"
JSON = f"modelos/{MODELO}/blisters.json"
PASTA_SAIDA = f"recortes/{MODELO}"

# ====================================
# CRIA PASTA DE SAÍDA
# ====================================

os.makedirs(PASTA_SAIDA, exist_ok=True)

# ====================================
# CARREGA IMAGEM ALINHADA
# ====================================

imagem = cv2.imread(IMAGEM)

if imagem is None:
    raise Exception(f"Erro ao carregar: {IMAGEM}")

# ====================================
# CARREGA COORDENADAS
# ====================================

with open(JSON, "r", encoding="utf-8") as f:
    blisters = json.load(f)

# ====================================
# RECORTA CADA CAVIDADE
# ====================================

contador = 0

for nome, dados in blisters.items():

    x, y, w, h = dados

    roi = imagem[y:y+h, x:x+w]

    caminho_saida = os.path.join(
        PASTA_SAIDA,
        f"{nome}.png"
    )

    cv2.imwrite(
        caminho_saida,
        roi
    )

    contador += 1

    print(f"Salvo: {caminho_saida}")

# ====================================
# FINALIZAÇÃO
# ====================================

print()
print("================================")
print(f"{contador} cavidades recortadas")
print("================================")
print()
print(f"Pasta: {PASTA_SAIDA}")