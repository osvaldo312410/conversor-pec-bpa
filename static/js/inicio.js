 document.addEventListener('DOMContentLoaded', function() {
            const statusText = document.getElementById('status');
            const startButton = document.getElementById('startButton');
            const particlesContainer = document.getElementById('particles');
            const spinnerContainer = document.getElementById('spinnerContainer');

            // Criar partículas de fundo
            createParticles();

            // Simular progresso de inicialização
            const statusMessages = [
                "Inicializando sistema...",
                "Carregando módulos...",
                "Configurando ambiente...",
                "Verificando conexões...",
                "Preparando interface...",
                "Sistema pronto!"
            ];

            let currentStatus = 0;
            const statusInterval = setInterval(() => {
                if (currentStatus < statusMessages.length) {
                    statusText.textContent = statusMessages[currentStatus];
                    currentStatus++;
                } else {
                    clearInterval(statusInterval);
                    
                    // Mostrar botão com animação
                    setTimeout(() => {
                        startButton.style.opacity = "1";
                        startButton.style.transform = "scale(1)";
                    }, 500);
                }
            }, 800); // Muda a mensagem a cada 800ms

            // Adicionar evento de clique ao botão
            startButton.addEventListener('click', function() {
                // Desabilita o botão para evitar múltiplos cliques
                startButton.disabled = true;
                
                // Mostra o spinner
                spinnerContainer.style.display = 'flex';
                statusText.textContent = "Processando solicitação...";
                
                // Simula um processo de carregamento
                setTimeout(function() {
                    // Redireciona para a próxima página após o "carregamento"
                    window.location.href = '/index';
                }, 2500); // 2.5 segundos de simulação
            });

            // Função para criar partículas animadas
            function createParticles() {
                const particleCount = 50;
                
                for (let i = 0; i < particleCount; i++) {
                    const particle = document.createElement('div');
                    particle.classList.add('particle');
                    
                    // Posição e tamanho aleatórios
                    const size = Math.random() * 10 + 2;
                    const posX = Math.random() * 100;
                    const posY = Math.random() * 100;
                    const delay = Math.random() * 5;
                    const duration = Math.random() * 5 + 3;
                    const moveX = Math.random() * 100 - 50;
                    const moveY = Math.random() * 100 - 50;
                    
                    particle.style.width = `${size}px`;
                    particle.style.height = `${size}px`;
                    particle.style.left = `${posX}%`;
                    particle.style.top = `${posY}%`;
                    particle.style.setProperty('--move-x', `${moveX}px`);
                    particle.style.setProperty('--move-y', `${moveY}px`);
                    particle.style.animation = `
                        fadeIn 1s ease-in-out ${delay}s infinite alternate,
                        moveParticle ${duration}s ease-in-out ${delay}s infinite alternate
                    `;
                    
                    particlesContainer.appendChild(particle);
                }
            }
        });