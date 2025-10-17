console.log("=== PROCESSADOR ESUS-PEC CARREGADO ===");

// Esperar até que o modal esteja totalmente carregado
document.addEventListener('shown.bs.modal', function(e) {
    console.log("Modal aberto:", e.target);
    
    // Agora sim buscar os elementos dentro do modal
    const modal = e.target;
    const inputCompetencia = modal.querySelector('#competencia');
    const inputCnes = modal.querySelector('#cnes');
    const progressBar = modal.querySelector('#progress-bar');
    const progressText = modal.querySelector('#progress-text');
    const btnDownload = modal.querySelector('#btnDownload');
    
    console.log("Elementos encontrados no modal:");
    console.log("- inputCompetencia:", inputCompetencia);
    console.log("- inputCnes:", inputCnes);
    console.log("- progressBar:", progressBar);
    console.log("- progressText:", progressText);
    console.log("- btnDownload:", btnDownload);
    
    if (btnDownload) {
        btnDownload.addEventListener('click', function() {
            console.log("Botão clicado dentro do modal!");
            
            if (!inputCompetencia) {
                alert("Erro: campo competência não encontrado.");
                return;
            }
            
            // Não é mais obrigatório verificar se inputCnes existe
            // pois agora o CNES pode ser vazio
            
            const competencia = inputCompetencia.value.trim();
            const cnes = inputCnes ? inputCnes.value.trim() : ''; // Permite CNES vazio
            
            console.log("Valores dos inputs:");
            console.log("- Competência:", competencia);
            console.log("- CNES:", cnes);
            
            if (!competencia) {
                alert("Por favor, informe a competência no formato AAAAMM.");
                return;
            }
            
            // REMOVIDA a validação que exigia CNES
            // if (!cnes) {
            //     alert("Por favor, informe o número do CNES.");
            //     return;
            // }
            
            // Adicionar spinner ao botão
            const originalText = btnDownload.innerHTML;
            btnDownload.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...';
            btnDownload.disabled = true;
            
            // Resto do seu código de processamento...
            processarCompetencia(competencia, cnes, progressBar, progressText, btnDownload, originalText);
        });
    }
});

// Função separada para o processamento
function processarCompetencia(competencia, cnes, progressBar, progressText, btnDownload, originalText) {
    console.log("Processando competência:", competencia);
    console.log("Processando CNES:", cnes);
    
    // Reseta progresso
    if (progressBar) {
        progressBar.style.width = "0%";
        progressBar.innerText = "0%";
    }
    if (progressText) {
        progressText.innerText = "Iniciando processamento...";
    }

    // Criar conexão SSE para acompanhar progresso
    console.log("Criando EventSource...");
    const eventSource = new EventSource('/progress/producao');
    
    eventSource.onmessage = function(event) {
        console.log("Mensagem do SSE:", event.data);
        try {
            const data = JSON.parse(event.data);
            
            // Atualizar barra de progresso
            if (progressBar) {
                progressBar.style.width = data.progress + "%";
                progressBar.innerText = data.progress + "%";
            }
            if (progressText) {
                progressText.innerText = data.message;
            }
            
            // Se concluído ou erro, fechar conexão e restaurar botão
            if (data.progress === 100 || data.error) {
                console.log("Processamento concluído ou erro ocorreu");
                eventSource.close();
                
                // Restaurar botão
                if (btnDownload && originalText) {
                    btnDownload.innerHTML = originalText;
                    btnDownload.disabled = false;
                }
                
                // Se sucesso, redirecionar após pequeno delay
                if (!data.error) {
                    setTimeout(() => {
                        window.location.href = '/index';
                    }, 1000);
                }
            }
        } catch (error) {
            console.error("Erro ao parsear JSON:", error);
        }
    };

    eventSource.onerror = function() {
        console.error("Erro no EventSource");
        if (progressText) {
            progressText.innerText = "Conexão com servidor perdida.";
        }
        eventSource.close();
        
        // Restaurar botão em caso de erro
        if (btnDownload && originalText) {
            btnDownload.innerHTML = originalText;
            btnDownload.disabled = false;
        }
    };

    // Enviar requisição AJAX para iniciar processamento
    console.log("Enviando requisição para /processar_producao");
    fetch("/processar_producao", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ 
            competencia: competencia,
            cnes: cnes 
        })
    })
    .then(response => {
        console.log("Status:", response.status);
        if (!response.ok) {
            throw new Error("Erro na resposta do servidor: " + response.status);
        }
        return response.json();
    })
    .then(data => {
        console.log("Resposta JSON:", data);
        // Aqui você pode tratar a resposta se necessário
    })
    .catch(error => {
        console.error("Erro no fetch:", error);
        if (progressText) {
            progressText.innerText = "Erro ao iniciar processamento.";
        }
        eventSource.close();
        
        // Restaurar botão em caso de erro
        if (btnDownload && originalText) {
            btnDownload.innerHTML = originalText;
            btnDownload.disabled = false;
        }
    });
}