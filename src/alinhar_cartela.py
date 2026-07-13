import cv2
import numpy as np
import json
import os
import sys

TAMANHO_PATCH = 41
JANELA_BUSCA = 60
ESCALAS = [0.90, 0.95, 1.0, 1.05, 1.10]      # tolera pequena variação de escala residual
ANGULOS = [-8, -4, 0, 4, 8]                   # tolera pequena rotação residual (graus)
CONFIANCA_MINIMA = 0.5

# Parâmetros da checagem de distribuição espacial dos pontos de controle.
MARGEM_QUADRANTE = 0.5
MIN_QUADRANTES_COBERTOS = 3


def ordenar_pontos(pts):
    soma = pts.sum(axis=1)
    diferenca = np.diff(pts, axis=1)
    topo_esq = pts[np.argmin(soma)]
    base_dir = pts[np.argmax(soma)]
    topo_dir = pts[np.argmin(diferenca)]
    base_esq = pts[np.argmax(diferenca)]
    return np.array([topo_esq, topo_dir, base_dir, base_esq], dtype=np.float32)


def encontrar_cantos(img, nome_debug):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    bordas = cv2.Canny(blur, 30, 100)
    bordas = cv2.dilate(bordas, np.ones((5, 5), np.uint8), iterations=2)

    contornos, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        raise Exception("Nenhum contorno encontrado.")

    maior = max(contornos, key=cv2.contourArea)
    hull = cv2.convexHull(maior)

    aprox = None
    for fator in [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.1]:
        perimetro = cv2.arcLength(hull, True)
        tentativa = cv2.approxPolyDP(hull, fator * perimetro, True)
        if len(tentativa) == 4:
            aprox = tentativa
            break

    debug_img = img.copy()
    cv2.drawContours(debug_img, [hull], -1, (0, 255, 0), 3)

    if aprox is None:
        rect = cv2.minAreaRect(hull)
        aprox = cv2.boxPoints(rect).reshape(4, 1, 2).astype(np.int32)
        print("  AVISO: usando minAreaRect como fallback (contorno impreciso)")

    for p in aprox:
        cv2.circle(debug_img, tuple(p[0]), 10, (0, 0, 255), -1)

    os.makedirs("debug", exist_ok=True)
    cv2.imwrite(f"debug/{nome_debug}", debug_img)

    return ordenar_pontos(aprox.reshape(4, 2).astype(np.float32))


def buscar_template_multiescala(janela, template):
    """
    Busca o template testando pequenas variações de escala e rotação,
    pra tolerar o resíduo que sobra depois do alinhamento grosseiro.
    Retorna (confianca, x_local, y_local) da melhor correspondência.
    """
    melhor_confianca = -1
    melhor_pos = None
    th, tw = template.shape

    for escala in ESCALAS:
        for angulo in ANGULOS:
            novo_w = max(8, int(tw * escala))
            novo_h = max(8, int(th * escala))

            centro = (tw // 2, th // 2)
            matriz_rot = cv2.getRotationMatrix2D(centro, angulo, 1.0)
            template_rot = cv2.warpAffine(template, matriz_rot, (tw, th),
                                           borderMode=cv2.BORDER_REPLICATE)
            template_variante = cv2.resize(template_rot, (novo_w, novo_h))

            if template_variante.shape[0] > janela.shape[0] or template_variante.shape[1] > janela.shape[1]:
                continue

            resultado = cv2.matchTemplate(janela, template_variante, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(resultado)

            if max_val > melhor_confianca:
                melhor_confianca = max_val
                melhor_pos = (
                    max_loc[0] + novo_w // 2,
                    max_loc[1] + novo_h // 2
                )

    return melhor_confianca, melhor_pos


def testar_todas_orientacoes(img_ref, cantos_ref, img_foto, cantos_foto_bruto,
                              largura, altura, pontos_controle,
                              tamanho_patch=41, janela_busca=60):
    """
    Testa as 4 rotações E suas versões espelhadas (8 candidatos no total).
    Decide usando os PONTOS DE CONTROLE (não correlação global de pixels),
    porque em layouts repetitivos a correlação bruta pode não diferenciar
    bem orientação certa de errada.
    """
    gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
    meio_patch = tamanho_patch // 2

    melhor_score = -1
    melhor_H = None
    melhor_ordem = None
    melhor_descricao = None

    candidatos = []
    for deslocamento in range(4):
        pts_rotacionado = np.roll(cantos_foto_bruto, deslocamento, axis=0)
        candidatos.append((f"rotação {deslocamento}", pts_rotacionado, False))
        pts_espelhado = pts_rotacionado[::-1].copy()
        candidatos.append((f"rotação {deslocamento} espelhada", pts_espelhado, True))

    for descricao, pts_candidato, espelhado in candidatos:
        H_teste = cv2.getPerspectiveTransform(pts_candidato, cantos_ref)
        candidato_img = cv2.warpPerspective(img_foto, H_teste, (largura, altura))
        gray_candidato = cv2.cvtColor(candidato_img, cv2.COLOR_BGR2GRAY)

        soma_confianca = 0.0
        pontos_reconhecidos = 0

        for nome, (xr, yr) in pontos_controle.items():
            y0, y1 = yr - meio_patch, yr + meio_patch + 1
            x0, x1 = xr - meio_patch, xr + meio_patch + 1
            if y0 < 0 or x0 < 0 or y1 > gray_ref.shape[0] or x1 > gray_ref.shape[1]:
                continue
            template = gray_ref[y0:y1, x0:x1]

            jy0 = max(0, yr - janela_busca)
            jy1 = min(gray_candidato.shape[0], yr + janela_busca)
            jx0 = max(0, xr - janela_busca)
            jx1 = min(gray_candidato.shape[1], xr + janela_busca)
            janela = gray_candidato[jy0:jy1, jx0:jx1]

            if janela.shape[0] < template.shape[0] or janela.shape[1] < template.shape[1]:
                continue

            resultado = cv2.matchTemplate(janela, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(resultado)

            soma_confianca += max_val
            if max_val >= 0.5:
                pontos_reconhecidos += 1

        score = pontos_reconhecidos * 10 + soma_confianca

        print(f"  {descricao}: {pontos_reconhecidos} pontos reconhecidos "
              f"(confiança >= 0.5), soma_confianca={soma_confianca:.2f}")

        if score > melhor_score:
            melhor_score = score
            melhor_H = H_teste
            melhor_ordem = pts_candidato
            melhor_descricao = descricao

    return melhor_H, melhor_ordem, melhor_score, melhor_descricao


def checar_distribuicao(pontos, largura, altura):
    """
    Verifica se os pontos cobrem uma área espacial mínima e pelo menos
    MIN_QUADRANTES_COBERTOS dos 4 quadrantes da imagem. Retorna (ok, motivo).
    """
    if len(pontos) == 0:
        return False, "nenhum ponto"

    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]

    amplitude_x = (max(xs) - min(xs)) / largura
    amplitude_y = (max(ys) - min(ys)) / altura

    if amplitude_x < MARGEM_QUADRANTE or amplitude_y < MARGEM_QUADRANTE:
        return False, f"pontos concentrados numa faixa pequena (ampl_x={amplitude_x:.2f}, ampl_y={amplitude_y:.2f})"

    meio_x, meio_y = largura / 2, altura / 2
    quadrantes = set()
    for x, y in pontos:
        qx = 0 if x < meio_x else 1
        qy = 0 if y < meio_y else 1
        quadrantes.add((qx, qy))

    if len(quadrantes) < MIN_QUADRANTES_COBERTOS:
        return False, f"só {len(quadrantes)}/4 quadrantes cobertos"

    return True, "ok"


def alinhar_cartela(modelo):
    """
    Alinha a foto do usuário de um modelo específico contra sua referência.
    Lê:  modelos/{modelo}/referencia.png, pontos_controle.json
         imagens/uploads/{modelo}_foto_usuario.png
    Salva: alinhadas/{modelo}_alinhada.png
    Retorna o caminho do arquivo salvo.
    """
    referencia_path = f"modelos/{modelo}/referencia.png"
    pontos_controle_path = f"modelos/{modelo}/pontos_controle.json"
    foto_usuario_path = f"imagens/uploads/{modelo}_foto_usuario.png"
    saida_path = f"alinhadas/{modelo}_alinhada.png"

    print("Carregando imagens...")
    img_ref = cv2.imread(referencia_path)
    img_foto = cv2.imread(foto_usuario_path)

    if img_ref is None:
        raise Exception(f"Erro ao carregar {referencia_path}")
    if img_foto is None:
        raise Exception(f"Erro ao carregar {foto_usuario_path}")

    with open(pontos_controle_path, "r", encoding="utf-8") as f:
        pontos_controle = json.load(f)

    altura, largura = img_ref.shape[:2]

    # ETAPA 1: alinhamento grosseiro via 4 cantos
    print("Detectando cantos (alinhamento grosseiro)...")
    cantos_ref = encontrar_cantos(img_ref, "cantos_referencia.png")
    cantos_foto = encontrar_cantos(img_foto, "cantos_foto.png")

    area_ref = cv2.contourArea(cantos_ref.reshape(-1, 1, 2).astype(np.int32))
    area_foto = cv2.contourArea(cantos_foto.reshape(-1, 1, 2).astype(np.int32))
    if area_foto < area_ref * 0.15:
        raise Exception(
            "A área detectada na foto do usuário é muito menor que o esperado. "
            "A cartela pode estar cortada, muito distante, ou os cantos não foram "
            "bem detectados. Peça uma nova foto, mais próxima e com a cartela inteira visível."
        )

    print("Testando orientações (corrige fotos em retrato/paisagem/espelhadas)...")
    H0, cantos_foto, score_orientacao, descricao_orientacao = testar_todas_orientacoes(
        img_ref, cantos_ref, img_foto, cantos_foto, largura, altura, pontos_controle,
        tamanho_patch=TAMANHO_PATCH, janela_busca=JANELA_BUSCA
    )
    print(f"Orientação escolhida: {descricao_orientacao} | score={score_orientacao:.2f}")

    alinhada_grosseira = cv2.warpPerspective(img_foto, H0, (largura, altura))
    os.makedirs("debug", exist_ok=True)
    cv2.imwrite("debug/alinhada_grosseira.png", alinhada_grosseira)

    gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
    gray_grosseira = cv2.cvtColor(alinhada_grosseira, cv2.COLOR_BGR2GRAY)

    # ETAPA 2: refina pontos de controle (multi-escala/rotação)
    print("Refinando pontos de controle (tolerante a escala/rotação residual)...")

    meio_patch = TAMANHO_PATCH // 2
    pts_ref_final = []
    pts_grosseira_final = []
    debug_img = alinhada_grosseira.copy()

    for nome, (xr, yr) in pontos_controle.items():
        y0, y1 = yr - meio_patch, yr + meio_patch + 1
        x0, x1 = xr - meio_patch, xr + meio_patch + 1
        if y0 < 0 or x0 < 0 or y1 > gray_ref.shape[0] or x1 > gray_ref.shape[1]:
            print(f"  {nome}: fora da borda, ignorado")
            continue
        template = gray_ref[y0:y1, x0:x1]

        jy0 = max(0, yr - JANELA_BUSCA)
        jy1 = min(gray_grosseira.shape[0], yr + JANELA_BUSCA)
        jx0 = max(0, xr - JANELA_BUSCA)
        jx1 = min(gray_grosseira.shape[1], xr + JANELA_BUSCA)

        janela = gray_grosseira[jy0:jy1, jx0:jx1]
        if janela.shape[0] < 10 or janela.shape[1] < 10:
            print(f"  {nome}: janela de busca pequena demais, ignorado")
            continue

        confianca, pos_local = buscar_template_multiescala(janela, template)
        print(f"  {nome}: confiança {confianca:.2f}", end="")

        if confianca < CONFIANCA_MINIMA or pos_local is None:
            print(" -- ignorado (baixa confiança)")
            continue

        x_encontrado = jx0 + pos_local[0]
        y_encontrado = jy0 + pos_local[1]

        pts_ref_final.append([xr, yr])
        pts_grosseira_final.append([x_encontrado, y_encontrado])

        cv2.circle(debug_img, (x_encontrado, y_encontrado), 6, (0, 0, 255), -1)
        cv2.putText(debug_img, nome, (x_encontrado + 8, y_encontrado - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        print(f" -- encontrado em ({x_encontrado},{y_encontrado})")

    cv2.imwrite("debug/pontos_controle_encontrados.png", debug_img)

    print(f"\nPontos de controle válidos: {len(pts_ref_final)}")

    # ETAPA 3: homografia de correção fina
    if len(pts_ref_final) >= 4:
        distribuicao_ok, motivo = checar_distribuicao(pts_ref_final, largura, altura)
        print(f"Distribuição espacial dos pontos: {motivo}")

        if not distribuicao_ok:
            print("AVISO: pontos mal distribuídos -- correção fina PODE distorcer áreas sem")
            print("cobertura. Usando apenas alinhamento grosseiro (mais seguro nesse caso).")
            print("Sugestão: adicione pontos de controle na(s) área(s) sem cobertura.")
            alinhada = alinhada_grosseira
        else:
            pts_ref_arr = np.array(pts_ref_final, dtype=np.float32)
            pts_grosseira_arr = np.array(pts_grosseira_final, dtype=np.float32)

            H_correcao, mask = cv2.findHomography(pts_grosseira_arr, pts_ref_arr, cv2.RANSAC, 5.0)
            inliers = int(mask.sum())
            taxa_inliers = inliers / len(pts_ref_final)
            print(f"Inliers correção fina: {inliers}/{len(pts_ref_final)} ({100*taxa_inliers:.1f}%)")

            if taxa_inliers < 0.5:
                print("AVISO: baixa taxa de inliers -- usando apenas alinhamento grosseiro (mais seguro).")
                alinhada = alinhada_grosseira
            else:
                alinhada = cv2.warpPerspective(alinhada_grosseira, H_correcao, (largura, altura))
                print("Homografia de correção fina aplicada.")
    else:
        print("AVISO: poucos pontos de controle válidos -- usando apenas alinhamento grosseiro.")
        alinhada = alinhada_grosseira

    os.makedirs("alinhadas", exist_ok=True)
    cv2.imwrite(saida_path, alinhada)

    print()
    print("================================")
    print("Cartela alinhada com sucesso")
    print("================================")
    print(saida_path)

    return saida_path


# Permite continuar rodando este arquivo sozinho pelo terminal, para debug:
# python src/alinhar_cartela.py rh_150_75
if __name__ == "__main__":
    modelo_cli = "rh_150_75"
    if len(sys.argv) > 1:
        modelo_cli = sys.argv[1]
    alinhar_cartela(modelo_cli)