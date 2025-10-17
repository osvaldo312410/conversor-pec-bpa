document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM carregado - Iniciando configuração...');
    
    let isProcessing = false;

    // Criar botão de processamento automático
    const processarBtn = document.createElement('button');
    processarBtn.type = 'button';
    processarBtn.className = 'btn btn-info mb-3';
    processarBtn.innerHTML = '<i class="bi bi-play-circle"></i> Processar Automaticamente';
    processarBtn.id = 'processarAutoBtn';

    async function preencherCampos(input) {
        const proced = input.value.trim();
        if (!proced) {
            console.log(`Procedimento vazio, ignorando:`, input);
            return true;
        }

        console.log(`Processando procedimento: ${proced}`);
        const startTime = performance.now();

        const row = input.closest('.d-flex');
        if (!row) {
            console.error('Linha não encontrada para o input:', input);
            return true;
        }

        const cidSel = row.querySelector('.cid-select');
        const servSel = row.querySelector('.servico-select');
        const classSel = row.querySelector('.class-select');

        if (!cidSel || !servSel || !classSel) {
            console.error('Elementos select não encontrados na linha:', row);
            return true;
        }

        // 🔄 Mostra "Carregando..." nos selects
        [cidSel, servSel, classSel].forEach(sel => {
            sel.innerHTML = '';
            const opt = document.createElement('option');
            opt.textContent = 'Carregando...';
            opt.disabled = true;
            opt.selected = true;
            sel.appendChild(opt);
            sel.classList.add('loading');
        });

        const formData = new FormData();
        formData.append('proced', proced);

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            console.log(`Enviando requisição para: ${proced}`);
            const resp = await fetch('/config', {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            }

            const data = await resp.json();
            const requestTime = performance.now() - startTime;
            console.log(`Resposta recebida para ${proced} em ${requestTime.toFixed(0)}ms`);

            // ✅ preencher CIDs
            cidSel.innerHTML = '';
            if (data.cids && data.cids.length > 0) {
                data.cids.forEach(cid => {
                    const opt = document.createElement('option');
                    opt.value = cid;
                    opt.textContent = cid;
                    cidSel.appendChild(opt);
                });
                cidSel.selectedIndex = 0;
                console.log(`${data.cids.length} CIDs carregados para ${proced}`);
            } else {
                const opt = document.createElement('option');
                opt.textContent = 'Nenhum CID encontrado';
                opt.disabled = true;
                cidSel.appendChild(opt);
            }

            // ✅ preencher Serviços e Classificação
            servSel.innerHTML = '';
            classSel.innerHTML = '';
            
            if (data.servico && data.servico.length > 0) {
                data.servico.forEach(s => {
                    const optServ = document.createElement('option');
                    optServ.value = s.servico;
                    optServ.textContent = s.servico;
                    servSel.appendChild(optServ);

                    const optClass = document.createElement('option');
                    optClass.value = s.classificacao;
                    optClass.textContent = s.classificacao;
                    classSel.appendChild(optClass);
                });
                servSel.selectedIndex = 0;
                classSel.selectedIndex = 0;
                console.log(`${data.servico.length} serviços carregados para ${proced}`);
            } else {
                const optServ = document.createElement('option');
                optServ.textContent = 'Nenhum serviço encontrado';
                optServ.disabled = true;
                servSel.appendChild(optServ);

                const optClass = document.createElement('option');
                optClass.textContent = 'Nenhuma classificação';
                optClass.disabled = true;
                classSel.appendChild(optClass);
            }

            return true;

        } catch (err) {
            const errorTime = performance.now() - startTime;
            console.error(`Erro ao carregar ${proced} após ${errorTime.toFixed(0)}ms:`, err);
            
            [cidSel, servSel, classSel].forEach(sel => {
                sel.innerHTML = '';
                const opt = document.createElement('option');
                opt.textContent = err.name === 'AbortError' ? 'Timeout - Clique para tentar' : 'Erro ao carregar';
                opt.disabled = true;
                opt.selected = true;
                sel.appendChild(opt);
                
                sel.addEventListener('click', function onClick() {
                    sel.removeEventListener('click', onClick);
                    preencherCampos(input);
                });
            });
            
            return true;
        } finally {
            [cidSel, servSel, classSel].forEach(sel => sel.classList.remove('loading'));
            const totalTime = performance.now() - startTime;
            console.log(`Processamento concluído para ${proced} em ${totalTime.toFixed(0)}ms`);
        }
    }

    async function processarTodosSequencialmente() {
        if (isProcessing) {
            console.log('Já está processando, aguarde...');
            return;
        }
        
        isProcessing = true;
        console.log('Iniciando processamento sequencial...');
        
        const procedInputs = document.querySelectorAll('.proced-input');
        const inputsComValor = Array.from(procedInputs).filter(input => input.value.trim());
        
        console.log(`${inputsComValor.length} inputs com valor para processar`);
        
        for (let i = 0; i < inputsComValor.length; i++) {
            const input = inputsComValor[i];
            console.log(`Processando item ${i + 1} de ${inputsComValor.length}: ${input.value.trim()}`);
            
            const continuar = await preencherCampos(input);
            
            if (!continuar) {
                console.log('Processamento interrompido');
                break;
            }
            
            if (i < inputsComValor.length - 1) {
                console.log('Aguardando 1 segundo antes do próximo...');
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }
        
        isProcessing = false;
        console.log('Processamento sequencial concluído!');
    }

    async function salvarConfiguracoes() {
        console.log('Iniciando salvamento das configurações...');
        const startTime = performance.now();
        
        const procedimentos = [];
        
        document.querySelectorAll('.d-flex').forEach((row, index) => {
            const procedInput = row.querySelector('.proced-input');
            const cidSelect = row.querySelector('.cid-select');
            const servicoSelect = row.querySelector('.servico-select');
            const classSelect = row.querySelector('.class-select');
            
            if (procedInput && procedInput.value.trim()) {
                procedimentos.push({
                    proced: procedInput.value.trim(),
                    cid: cidSelect ? (cidSelect.value || '') : '',
                    servico: servicoSelect ? (servicoSelect.value || '') : '',
                    classificacao: classSelect ? (classSelect.value || '') : ''
                });
                console.log(`Coletado procedimento ${index + 1}: ${procedInput.value.trim()}`);
            }
        });
        
        console.log(`Total de ${procedimentos.length} procedimentos para salvar`);
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);

            const response = await fetch('/salvar-configuracoes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ procedimentos: procedimentos }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            const result = await response.json();
            const saveTime = performance.now() - startTime;
            
            if (result.success) {
                console.log(`Configurações salvas com sucesso em ${saveTime.toFixed(0)}ms`);
                alert(result.message);
            } else {
                console.error(`Erro ao salvar em ${saveTime.toFixed(0)}ms:`, result.message);
                alert('Erro ao salvar: ' + result.message);
            }
        } catch (error) {
            const errorTime = performance.now() - startTime;
            console.error(`Erro no salvamento após ${errorTime.toFixed(0)}ms:`, error);
            alert(error.name === 'AbortError' ? 'Timeout ao salvar configurações' : 'Erro ao salvar configurações.');
        }
    }

    // Configurar eventos
    function setupEvents() {
        // Botão de salvar
        const salvarBtn = document.querySelector('button[type="submit"]');
        if (salvarBtn) {
            salvarBtn.addEventListener('click', function(e) {
                e.preventDefault();
                salvarConfiguracoes();
            });
            console.log('Botão de salvar configurado');
        } else {
            console.warn('Botão de salvar não encontrado');
        }

        // Botão de processamento automático
        processarBtn.addEventListener('click', function() {
            console.log('Processamento automático iniciado manualmente');
            processarTodosSequencialmente();
        });

        // Inserir botão de processamento automático
        const form = document.querySelector('form');
        if (form && salvarBtn) {
            form.insertBefore(processarBtn, salvarBtn);
            console.log('Botão de processamento automático adicionado');
        }

        // Clique manual nos inputs
        const procedInputs = document.querySelectorAll('.proced-input');
        console.log(`${procedInputs.length} inputs de procedimento encontrados`);
        
        procedInputs.forEach(input => {
            input.style.cursor = 'pointer';
            input.addEventListener('click', () => {
                console.log('Clique manual no input:', input.value.trim());
                preencherCampos(input);
            });
        });

        // Inicia automaticamente após 2 segundos
        setTimeout(() => {
            console.log('Iniciando processamento automático sequencial...');
            processarTodosSequencialmente();
        }, 2000);
    }

    // Inicializar
    setupEvents();
    console.log('Sistema de configuração inicializado com sucesso');
});