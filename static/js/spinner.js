document.addEventListener("DOMContentLoaded", function () {
    const loader = document.getElementById("loader");
    if (!loader) return;

    function adicionarEventoLoader(seletor) {
        const elementos = document.querySelectorAll(seletor);
        elementos.forEach(elemento => {
            elemento.addEventListener("click", function () {
                // Verifica se o link não está desabilitado
                if (!this.classList.contains('disabled') &&
                    !this.parentElement.classList.contains('disabled') &&
                    this.getAttribute('href') !== '#') {
                    loader.style.display = "flex";
                }
            });
        });
    }

    // Aplica para diferentes links/buttons
    adicionarEventoLoader("a[href='/index']");
    adicionarEventoLoader(".btn_download");
    adicionarEventoLoader(".voltar-index");
    adicionarEventoLoader("nav[aria-label='Navegação de páginas'] a.page-link");
    adicionarEventoLoader("a[href*='/index?page=']");
});
