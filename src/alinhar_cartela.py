import cv2
import numpy as np
import json
import os

MODELO = "rh_150_75"
REFERENCIA = f"modelos/{MODELO}/referencia.png"
PONTOS_CONTROLE = f"modelos/{MODELO}/pontos_controle.json"
FOTO_USUARIO = "imagens/uploads/foto_usuario.png"
SAIDA = "alinhadas/cartela_alinhada.png"

TAMANHO_PATCH = 41
JANELA_BUSCA = 60
ESCALAS = [0.90, 0.95, 1.0, 1.05, 1.10]      # tolera pequena variação de escala residual
ANGULOS = [-8, -4, 0, 4, 8]                   # tolera pequena rotação residual (graus)
CONFIANCA_MINIMA = 0.5


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
                # centro do template encontrado (compensando o tamanho variante)
                melhor_pos = (
                    max_loc[0] + novo_w // 2,
                    max_loc[1] + novo_h // 2
                )

    return melhor_confianca, melhor_pos


print("Carregando imagens...")
img_ref = cv2.imread(REFERENCIA)
img_foto = cv2.imread(FOTO_USUARIO)

if img_ref is None:
    raise Exception(f"Erro ao carregar {REFERENCIA}")
if img_foto is None:
    raise Exception(f"Erro ao carregar {FOTO_USUARIO}")

with open(PONTOS_CONTROLE, "r", encoding="utf-8") as f:
    pontos_controle = json.load(f)

altura, largura = img_ref.shape[:2]

# ====================================
# ETAPA 1: alinhamento grosseiro via 4 cantos
# ====================================
print("Detectando cantos (alinhamento grosseiro)...")
cantos_ref = encontrar_cantos(img_ref, "cantos_referencia.png")
cantos_foto = encontrar_cantos(img_foto, "cantos_foto.png")

# Validação básica: os 4 cantos devem formar um quadrilátero razoável
area_ref = cv2.contourArea(cantos_ref.reshape(-1, 1, 2).astype(np.int32))
area_foto = cv2.contourArea(cantos_foto.reshape(-1, 1, 2).astype(np.int32))
if area_foto < area_ref * 0.15:
    raise Exception(
        "A área detectada na foto do usuário é muito menor que o esperado. "
        "A cartela pode estar cortada, muito distante, ou os cantos não foram "
        "bem detectados. Peça uma nova foto, mais próxima e com a cartela inteira visível."
    )

H0 = cv2.getPerspectiveTransform(cantos_foto, cantos_ref)
alinhada_grosseira = cv2.warpPerspective(img_foto, H0, (largura, altura))
cv2.imwrite("debug/alinhada_grosseira.png", alinhada_grosseira)

gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
gray_grosseira = cv2.cvtColor(alinhada_grosseira, cv2.COLOR_BGR2GRAY)

# ====================================
# ETAPA 2: refina pontos de controle (multi-escala/rotação)
# ====================================
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

os.makedirs("debug", exist_ok=True)
cv2.imwrite("debug/pontos_controle_encontrados.png", debug_img)

print(f"\nPontos de controle válidos: {len(pts_ref_final)}")

# ====================================
# ETAPA 3: homografia de correção fina
# ====================================

# Parâmetros da checagem de distribuição espacial dos pontos.
# Sem pontos bem espalhados pela cartela, a homografia de correção
# encaixa bem perto dos pontos usados mas pode DISTORCER regiões
# sem cobertura (ex: só ter pontos na direita e estragar a esquerda).
MARGEM_QUADRANTE = 0.5  # fração mínima da largura/altura que os pontos devem cobrir
MIN_QUADRANTES_COBERTOS = 3  # de 4 quadrantes (topo-esq, topo-dir, base-esq, base-dir)


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
cv2.imwrite(SAIDA, alinhada)

print()
print("================================")
print("Cartela alinhada com sucesso")
print("================================")
print(SAIDA)