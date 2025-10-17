document.getElementById("formExport").addEventListener("submit", function(e) {
    e.preventDefault(); // impede o submit normal

    const msgDiv = document.getElementById("msgExport");
    msgDiv.innerText = "Salvando arquivo...";

    fetch("/export", { method: "POST" })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            msgDiv.innerText = data.msg;
        } else {
            msgDiv.innerText = "Erro ao salvar arquivo!";
        }
    })
    .catch(err => {
        console.error(err);
        msgDiv.innerText = "Erro na requisição!";
    });
});