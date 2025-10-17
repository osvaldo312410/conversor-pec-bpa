(function(){
  const btn = document.getElementById("btnDownload");
  const btnConvert = document.getElementById("btnConvert");
  const convertProgressWrapper = document.getElementById("convert-progress-wrapper");
  const convertProgressBar = document.getElementById("convert-progress-bar");
  const convertProgressText = document.getElementById("convert-progress-text");
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");
  const fileNameEl = document.getElementById("file-name");
  const downloadInfo = document.getElementById("download-info");
  let pollInterval = null;

  // --- DOWNLOAD ---
btn.addEventListener("click", async () => {
  const competencia = document.getElementById("competencia").value.trim();
  if (!competencia) { alert("Informe a competência (ex: 202508)"); return; }

  btn.disabled = true;
  btnConvert.disabled = true;
  progressBar.style.width = "0%";
  progressBar.innerText = "0%";
  progressText.innerText = "Procurando arquivo...";
  downloadInfo.style.display = "none";

  try {
    const res = await fetch("/start_download_bdsia", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ competencia })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erro iniciando download");

    const downloadId = data.download_id;
    const filename = data.filename;

    fileNameEl.innerText = "Arquivo escolhido: " + filename;
    downloadInfo.style.display = "block";

    // Variáveis para o cronômetro
    let countdownInterval = null;
    let secondsLeft = 15;

    // inicia polling do download
    pollInterval = setInterval(async () => {
      try {
        const r = await fetch(`/download_progress/${downloadId}`);
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || "Erro no progresso");

        const downloaded = j.downloaded || 0;
        const total = j.total || 0;
        const status = j.status;
        const percent = j.percent;

        if (percent !== null && percent !== undefined) {
          progressBar.style.width = percent + "%";
          progressBar.innerText = percent + "%";
        } else {
          progressBar.style.width = "100%";
          progressBar.innerText = humanFileSize(downloaded) + " baixados";
        }

        progressText.innerText = `Status: ${status}. ${humanFileSize(downloaded)} de ${ total ? humanFileSize(total) : "tamanho desconhecido" }`;

        if (status === "done") {
          clearInterval(pollInterval);
          progressBar.style.width = "100%";
          progressBar.innerText = "100% - Concluído";
          
          // Inicia o cronômetro de 15 segundos
          secondsLeft = 15;
          progressText.innerText = `Download concluído. Aguarde ${secondsLeft} segundos para instalação...`;
          
          countdownInterval = setInterval(() => {
            secondsLeft--;
            
            if (secondsLeft > 0) {
              progressText.innerText = `Download concluído. Aguarde ${secondsLeft} segundos para instalação...`;
              btn.disabled = true;
              btnConvert.disabled = true;
            } else {
              // Cronômetro terminou
              clearInterval(countdownInterval);
              progressText.innerText = "Download concluído. Pronto para instalação.";
              btn.disabled = false;
              btnConvert.disabled = false; // habilita conversão
            }
          }, 1000);
          
        } else if (status === "error") {
          clearInterval(pollInterval);
          if (countdownInterval) clearInterval(countdownInterval);
          progressBar.classList.remove("progress-bar-animated");
          progressBar.innerText = "Erro";
          progressText.innerText = "Erro: " + (j.error || "erro desconhecido");
          btn.disabled = false;
        }

        if (status === "installing" || status === "installation_started") {
            clearInterval(pollInterval);
            if (countdownInterval) clearInterval(countdownInterval);
            progressBar.style.width = "100%";
            progressBar.innerText = "100% - Instalando";
            progressText.innerText = j.message || "Instalação do BDSIA em andamento...";
            btn.disabled = false;
            btnConvert.disabled = true; // Mantém desabilitado até instalação completa
            
            // Mostra mensagem informativa
            alert("Instalação do BDSIA iniciada. Aguarde a conclusão da instalação antes de clicar em 'Converter tabelas'.");
        }
      } catch (err) {
        console.error("Erro polling:", err);
      }
    }, 700);

  } catch (err) {
    alert("Erro: " + err.message);
    btn.disabled = false;
    progressText.innerText = "";
  }
});

  

// --- CONVERSÃO ---
btnConvert.addEventListener("click", async () => {
  // Primeiro verifica se todos os arquivos estão disponíveis
  try {
    const checkRes = await fetch("/check_files_status");
    const checkData = await checkRes.json();
    
    if (!checkRes.ok) {
      throw new Error(checkData.error || "Erro ao verificar arquivos");
    }
    
    const { files_available, total_files, ready_for_conversion } = checkData;
    
    if (!ready_for_conversion) {
      alert(`Aguarde! Apenas ${files_available} de ${total_files} arquivos estão disponíveis para conversão. É necessário aguardar todos os ${total_files} arquivos estarem prontos.`);
      return;
    }
    
  } catch (err) {
    alert("Erro ao verificar status dos arquivos: " + err.message);
    return;
  }
  
  // Se passou da verificação, prossegue com a conversão
  btnConvert.disabled = true;
  convertProgressWrapper.style.display = "block";
  convertProgressBar.style.width = "0%";
  convertProgressBar.innerText = "0%";
  convertProgressText.innerText = "Iniciando conversão...";

  const res = await fetch("/start_convert_bdsia", { method: "POST" });
  const data = await res.json();
  const convertId = data.download_id;

  const interval = setInterval(async () => {
    const r = await fetch(`/download_progress/${convertId}`);
    const j = await r.json();

    if (j.percent !== undefined) {
      convertProgressBar.style.width = j.percent + "%";
      convertProgressBar.innerText = j.percent + "%";
    }

    convertProgressText.innerText = `Status: ${j.status} (${j.downloaded}/${j.total} arquivos)`;

    if (j.status === "done") {
      clearInterval(interval);
      convertProgressBar.style.width = "100%";
      convertProgressBar.innerText = "100% - Concluído";
      convertProgressText.innerText += "\nConversão concluída. Banco SQLite criado na raiz do Sistema.";
      btnConvert.disabled = false;
    } else if (j.status === "error") {
      clearInterval(interval);
      convertProgressBar.classList.remove("progress-bar-animated");
      convertProgressBar.innerText = "Erro";
      convertProgressText.innerText = "Erro: " + (j.error || "desconhecido");
      btnConvert.disabled = false;
    }
  }, 700);
});

  function humanFileSize(bytes) {
    if (!bytes) return "0 B";
    const thresh = 1024;
    if (Math.abs(bytes) < thresh) return bytes + ' B';
    const units = ['KB','MB','GB','TB','PB','EB','ZB','YB'];
    let u = -1;
    do {
      bytes /= thresh;
      ++u;
    } while(Math.abs(bytes) >= thresh && u < units.length - 1);
    return bytes.toFixed(1)+' '+units[u];
  }

  // --- VERIFICAÇÃO DE INSTALAÇÃO ---
const btnCheckInstall = document.getElementById('btnCheckInstall');

btnCheckInstall.addEventListener('click', async () => {
    btnCheckInstall.disabled = true;
    btnCheckInstall.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Verificando...';
    
    try {
        const response = await fetch('/check_installation');
        const data = await response.json();
        
        if (data.installed) {
            showSuccess('BDSIA instalado com sucesso! Agora você pode converter as tabelas.');
            btnCheckInstall.style.display = 'none';
            btnConvert.disabled = false;
        } else {
            showError('BDSIA ainda não foi instalado completamente. Aguarde e tente novamente.');
            btnCheckInstall.disabled = false;
            btnCheckInstall.innerHTML = '<i class="bi bi-check-circle me-2"></i>Verificar Instalação';
        }
    } catch (error) {
        showError('Erro ao verificar instalação: ' + error.message);
        btnCheckInstall.disabled = false;
        btnCheckInstall.innerHTML = '<i class="bi bi-check-circle me-2"></i>Verificar Instalação';
    }
});

// Funções para mostrar toasts
function showSuccess(message) {
    const toast = new bootstrap.Toast(document.getElementById('successToast'));
    document.getElementById('successMessage').textContent = message;
    toast.show();
}

function showError(message) {
    const toast = new bootstrap.Toast(document.getElementById('errorToast'));
    document.getElementById('errorMessage').textContent = message;
    toast.show();
}
})();
