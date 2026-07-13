import cv2
import json
import os
import sys


def recortar_blisters(modelo):
    """
    Recorta as cavidades da cartela alinhada de um modelo específico,
    usando as coordenadas salvas em modelos/{modelo}/blisters.json.
    Retorna a pasta onde os recortes foram salvos.
    """
    imagem_path = f"alinhadas/{modelo}_alinhada.png"
    json_path = f"modelos/{modelo}/blisters.json"
    pasta_saida = f"recortes/{modelo}"

    os.makedirs(pasta_saida, exist_ok=True)

    imagem = cv2.imread(imagem_path)
    if imagem is None:
        raise Exception(f"Erro ao carregar: {imagem_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        blisters = json.load(f)

    contador = 0
    for nome, dados in blisters.items():
        x, y, w, h = dados
        roi = imagem[y:y + h, x:x + w]
        caminho_saida = os.path.join(pasta_saida, f"{nome}.png")
        cv2.imwrite(caminho_saida, roi)
        contador += 1
        print(f"Salvo: {caminho_saida}")

    print()
    print("================================")
    print(f"{contador} cavidades recortadas")
    print("================================")
    print()
    print(f"Modelo: {modelo}")
    print(f"Pasta: {pasta_saida}")

    return pasta_saida


# Permite continuar rodando este arquivo sozinho pelo terminal, para debug:
# python src/recortar_blisters.py rh_150_75
if __name__ == "__main__":
    modelo_cli = "rh_150_75"
    if len(sys.argv) > 1:
        modelo_cli = sys.argv[1]
    recortar_blisters(modelo_cli)