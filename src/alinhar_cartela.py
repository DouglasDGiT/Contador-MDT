import cv2
import numpy as np
import os


def alinhar_cartela(referencia_path, foto_path, saida_path):

    print("Carregando imagens...")

    referencia = cv2.imread(referencia_path)
    foto = cv2.imread(foto_path)

    if referencia is None:
        raise Exception(
            f"Não foi possível carregar: {referencia_path}"
        )

    if foto is None:
        raise Exception(
            f"Não foi possível carregar: {foto_path}"
        )

    print("Convertendo para escala de cinza...")

    ref_gray = cv2.cvtColor(
        referencia,
        cv2.COLOR_BGR2GRAY
    )

    foto_gray = cv2.cvtColor(
        foto,
        cv2.COLOR_BGR2GRAY
    )

    print("Detectando pontos ORB...")

    orb = cv2.ORB_create(5000)

    kp1, des1 = orb.detectAndCompute(
        ref_gray,
        None
    )

    kp2, des2 = orb.detectAndCompute(
        foto_gray,
        None
    )

    if des1 is None or des2 is None:
        raise Exception(
            "Não foi possível encontrar pontos suficientes."
        )

    print(
        f"Pontos referência: {len(kp1)}"
    )

    print(
        f"Pontos foto: {len(kp2)}"
    )

    matcher = cv2.BFMatcher(
        cv2.NORM_HAMMING,
        crossCheck=True
    )

    matches = matcher.match(
        des1,
        des2
    )

    matches = sorted(
        matches,
        key=lambda x: x.distance
    )

    matches = matches[:300]

    print(
        f"Matches utilizados: {len(matches)}"
    )

    pontos_ref = np.zeros(
        (len(matches), 2),
        dtype=np.float32
    )

    pontos_foto = np.zeros(
        (len(matches), 2),
        dtype=np.float32
    )

    for i, match in enumerate(matches):

        pontos_ref[i] = kp1[
            match.queryIdx
        ].pt

        pontos_foto[i] = kp2[
            match.trainIdx
        ].pt

    print("Calculando homografia...")

    H, mascara = cv2.findHomography(
        pontos_foto,
        pontos_ref,
        cv2.RANSAC
    )

    if H is None:
        raise Exception(
            "Falha ao calcular homografia."
        )

    altura, largura = referencia.shape[:2]

    print("Alinhando imagem...")

    alinhada = cv2.warpPerspective(
        foto,
        H,
        (largura, altura)
    )

    os.makedirs(
        os.path.dirname(saida_path),
        exist_ok=True
    )

    cv2.imwrite(
        saida_path,
        alinhada
    )

    print()
    print("================================")
    print("Cartela alinhada com sucesso")
    print("================================")
    print(saida_path)

    return alinhada