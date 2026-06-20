import cv2
import json

imagem = cv2.imread(
    "imagens/referencia/cartela_referencia.png"
)

with open(
    "config/blisters.json",
    "r"
) as f:

    blisters = json.load(f)

for nome, dados in blisters.items():

    x, y, w, h = dados

    cv2.rectangle(
        imagem,
        (x, y),
        (x + w, y + h),
        (0, 255, 0),
        2
    )

    cv2.putText(
        imagem,
        nome,
        (x, y - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (0, 0, 255),
        1
    )

cv2.imshow(
    "Validacao MDT",
    imagem
)

cv2.waitKey(0)
cv2.destroyAllWindows()