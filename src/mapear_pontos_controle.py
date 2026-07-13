import cv2
import json
import os

MODELO = "rh_300_150"
IMAGEM = f"modelos/{MODELO}/referencia.png"
SAIDA_JSON = f"modelos/{MODELO}/pontos_controle.json"

imagem = cv2.imread(IMAGEM)
if imagem is None:
    raise Exception(f"Não foi possível abrir {IMAGEM}")

pontos = []
clone = imagem.copy()

def redesenhar():
    global clone
    clone = imagem.copy()
    for i, (x, y) in enumerate(pontos, start=1):
        cv2.circle(clone, (x, y), 5, (0, 0, 255), -1)
        cv2.putText(clone, f"C{i}", (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.imshow("Pontos de Controle (clique, Z=desfazer, ENTER=salvar, ESC=sair)", clone)

def clique(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        pontos.append((x, y))
        redesenhar()

cv2.namedWindow("Pontos de Controle (clique, Z=desfazer, ENTER=salvar, ESC=sair)")
cv2.setMouseCallback("Pontos de Controle (clique, Z=desfazer, ENTER=salvar, ESC=sair)", clique)

print()
print("===================================")
print("PONTOS DE CONTROLE PARA ALINHAMENTO")
print("===================================")
print("Clique em 6-10 detalhes ÚNICOS e nítidos, espalhados pela cartela.")
print("Bons exemplos: cantos do logo Lupin, cantos do texto 'B.No.AA...',")
print("cantos de números do lote/validade, quinas de caixas de texto.")
print("EVITE pontos no meio de blocos de texto repetido (os 6 idiomas).")
print()
print("Z = desfaz | ENTER = salva | ESC = cancela")
print()

redesenhar()

while True:
    tecla = cv2.waitKey(20) & 0xFF
    if tecla == 13:
        break
    elif tecla == 27:
        cv2.destroyAllWindows()
        exit()
    elif tecla in (ord('z'), ord('Z')):
        if pontos:
            pontos.pop()
            redesenhar()

cv2.destroyAllWindows()

if len(pontos) < 4:
    raise Exception("Marque pelo menos 4-6 pontos pra um alinhamento robusto.")

dados = {f"C{i}": [x, y] for i, (x, y) in enumerate(pontos, start=1)}

os.makedirs(os.path.dirname(SAIDA_JSON), exist_ok=True)
with open(SAIDA_JSON, "w", encoding="utf-8") as f:
    json.dump(dados, f, indent=4)

print(f"\n{len(pontos)} pontos de controle salvos em {SAIDA_JSON}")