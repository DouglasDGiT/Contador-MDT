import cv2
import json
import os


def recortar_blisters(imagem_path, json_path, pasta_saida):

    print(f"\nProcessando: {imagem_path}")

    os.makedirs(pasta_saida, exist_ok=True)

    imagem = cv2.imread(imagem_path)

    if imagem is None:
        raise Exception(
            f"Erro ao carregar a imagem: {imagem_path}"
        )

    with open(json_path, "r") as f:
        blisters = json.load(f)

    contador = 0

    for nome, dados in blisters.items():

        x, y, w, h = dados

        roi = imagem[y:y+h, x:x+w]

        caminho_saida = os.path.join(
            pasta_saida,
            f"{nome}.png"
        )

        cv2.imwrite(
            caminho_saida,
            roi
        )

        contador += 1

        print(f"Salvo: {caminho_saida}")

    print(
        f"\n{contador} blisters recortados com sucesso."
    )


if __name__ == "__main__":

    JSON = "config/blisters.json"

    # Recortes da referência
    recortar_blisters(
        imagem_path="imagens/referencia/cartela_referencia.png",
        json_path=JSON,
        pasta_saida="recortes/recortes_referencia"
    )

    # Recortes da cartela alinhada
    recortar_blisters(
        imagem_path="alinhadas/cartela_alinhada.png",
        json_path=JSON,
        pasta_saida="recortes/recortes_teste"
    )