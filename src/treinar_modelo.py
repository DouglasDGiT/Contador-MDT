import cv2

ref = cv2.imread(
    "recortes/recortes_referencia/Day_7.png",
    cv2.IMREAD_GRAYSCALE
)

teste = cv2.imread(
    "recortes/recortes_teste/Day_7.png",
    cv2.IMREAD_GRAYSCALE
)

diff = cv2.absdiff(ref, teste)

_, thresh = cv2.threshold(
    diff,
    40,
    255,
    cv2.THRESH_BINARY
)

cv2.imwrite(
    "Day7_DIFERENCA_BINARIA.png",
    thresh
)

print("Imagem salva")