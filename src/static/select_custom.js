/*
  Transforma <select class="select-bonito"> em um dropdown customizado
  (já que <option> nativa não pode ser estilizada de forma confiável entre
  navegadores). O <select> original fica escondido, mas continua existindo
  no DOM -- então o formulário envia os dados exatamente como sempre,
  sem precisar mudar nada no backend.
*/

function inicializarSelectBonito(select) {
  if (select.dataset.aprimorado === "true") {
    atualizarOpcoesSelectBonito(select);
    return;
  }
  select.dataset.aprimorado = "true";
  select.style.display = "none";

  const wrapper = document.createElement("div");
  wrapper.className = "select-bonito-wrapper";

  const gatilho = document.createElement("button");
  gatilho.type = "button";
  gatilho.className = "select-bonito-gatilho";

  const lista = document.createElement("div");
  lista.className = "select-bonito-lista";
  lista.hidden = true;

  wrapper.appendChild(gatilho);
  wrapper.appendChild(lista);
  select.insertAdjacentElement("afterend", wrapper);

  select._selectBonito = { wrapper, gatilho, lista };

  gatilho.addEventListener("click", () => {
    const aberto = !lista.hidden;
    fecharTodosSelectsBonitos();
    if (!aberto) {
      lista.hidden = false;
      gatilho.classList.add("aberto");
    }
  });

  document.addEventListener("click", (evento) => {
    if (!wrapper.contains(evento.target)) {
      lista.hidden = true;
      gatilho.classList.remove("aberto");
    }
  });

  atualizarOpcoesSelectBonito(select);
}

function fecharTodosSelectsBonitos() {
  document.querySelectorAll(".select-bonito-lista").forEach((l) => (l.hidden = true));
  document.querySelectorAll(".select-bonito-gatilho").forEach((g) => g.classList.remove("aberto"));
}

function atualizarOpcoesSelectBonito(select) {
  const { gatilho, lista } = select._selectBonito;
  lista.innerHTML = "";

  const opcaoAtual = select.options[select.selectedIndex];
  gatilho.textContent = opcaoAtual ? opcaoAtual.textContent : "Selecione";
  gatilho.classList.toggle("select-bonito-placeholder", !select.value);

  Array.from(select.options).forEach((opt) => {
    const item = document.createElement("div");
    item.className = "select-bonito-opcao";
    item.textContent = opt.textContent;
    if (opt.value === select.value) item.classList.add("selecionado");

    item.addEventListener("click", () => {
      select.value = opt.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      lista.hidden = true;
      gatilho.classList.remove("aberto");
      atualizarOpcoesSelectBonito(select);
    });

    lista.appendChild(item);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("select.select-bonito").forEach(inicializarSelectBonito);
});