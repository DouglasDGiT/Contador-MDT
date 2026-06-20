import cv2
import json
import os

imagem_path = "imagens/referencia/cartela_referencia.png"

imagem = cv2.imread(imagem_path)

if imagem is None:
    raise Exception("Não foi possível carregar a imagem.")

blisters = {}

dias = [
    "Day_2","Day_3","Day_4","Day_5","Day_6","Day_7","Day_8",
    "Day_9","Day_10","Day_11","Day_12","Day_13","Day_14","Day_15",
    "Day_16","Day_17","Day_18","Day_19","Day_20","Day_21","Day_22",
    "Day_23","Day_24","Day_25","Day_26","Day_27","Day_28"
]

indice = 0

while indice < len(dias):

    dia = dias[indice]

    print(f"\nSelecione o blister: {dia}")
    print("Arraste o retângulo e pressione ENTER")

    roi = cv2.selectROI(
        "Mapeamento MDT",
        imagem,
        showCrosshair=True,
        fromCenter=False
    )

    x, y, w, h = roi

    blisters[dia] = [int(x), int(y), int(w), int(h)]

    indice += 1

cv2.destroyAllWindows()

os.makedirs("config", exist_ok=True)

with open("config/blisters.json", "w") as f:
    json.dump(
        blisters,
        f,
        indent=4
    )

print("\nMapeamento salvo em:")
print("config/blisters.json")