import cv2

dias = [
    "Day_2",
    "Day_7",
    "Day_8"
]

for dia in dias:

    ref = cv2.imread(
        f"recortes/recortes_referencia/{dia}.png",
        cv2.IMREAD_GRAYSCALE
    )

    teste = cv2.imread(
        f"recortes/recortes_teste/{dia}.png",
        cv2.IMREAD_GRAYSCALE
    )

    if ref is None or teste is None:
        print(f"Erro ao carregar {dia}")
        continue

    # Normalizar iluminação
    ref = cv2.equalizeHist(ref)
    teste = cv2.equalizeHist(teste)

    # Suavizar ruído
    ref = cv2.GaussianBlur(
        ref,
        (5, 5),
        0
    )

    teste = cv2.GaussianBlur(
        teste,
        (5, 5),
        0
    )

    # Diferença
    diff = cv2.absdiff(
        ref,
        teste
    )

    # Mantém apenas diferenças grandes
    _, thresh = cv2.threshold(
        diff,
        50,
        255,
        cv2.THRESH_BINARY
    )

    # Conta pixels brancos
    score = cv2.countNonZero(
        thresh
    )

    print(
        f"{dia}: {score}"
    )

    # Salva imagens para inspeção
    cv2.imwrite(
        f"{dia}_diff.png",
        diff
    )

    cv2.imwrite(
        f"{dia}_threshold.png",
        thresh
    )

print("\nTeste concluído.")