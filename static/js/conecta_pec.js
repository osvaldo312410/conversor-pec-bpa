// Elementos DOM
const form = document.getElementById('configForm');
const togglePassword = document.getElementById('togglePassword');
const passwordInput = document.getElementById('password');
const testConnectionBtn = document.getElementById('testConnection');
const saveButton = document.getElementById('saveButton');
const successToast = new bootstrap.Toast(document.getElementById('successToast'));
const errorToast = new bootstrap.Toast(document.getElementById('errorToast'));

// Mostrar/ocultar senha
togglePassword.addEventListener('click', function() {
    const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
    passwordInput.setAttribute('type', type);
    
    // Alternar ícone
    const icon = this.querySelector('i');
    icon.classList.toggle('bi-eye');
    icon.classList.toggle('bi-eye-slash');
});

// Testar conexão
testConnectionBtn.addEventListener('click', async function() {
    const formData = getFormData();
    
    // Validar dados antes de testar
    if (!validateFormData(formData)) {
        showError('Preencha todos os campos corretamente antes de testar a conexão');
        return;
    }
    
    // Alterar texto do botão para indicar processamento
    const originalText = testConnectionBtn.innerHTML;
    testConnectionBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testando...';
    testConnectionBtn.disabled = true;
    
    try {
        const response = await fetch('/db_config/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.message || 'Conexão bem-sucedida! Configurações estão corretas.');
        } else {
            showError(data.error || 'Falha na conexão. Verifique suas configurações.');
        }
    } catch (error) {
        showError('Erro de conexão: ' + (error.message || 'Verifique suas configurações'));
    } finally {
        // Restaurar texto original do botão
        testConnectionBtn.innerHTML = originalText;
        testConnectionBtn.disabled = false;
    }
});

// Envio do formulário
form.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = getFormData();
    
    // Validar dados
    if (!validateFormData(formData)) {
        showError('Por favor, preencha todos os campos corretamente');
        return;
    }
    
    // Alterar texto do botão para indicar processamento
    const originalText = saveButton.innerHTML;
    saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';
    saveButton.disabled = true;
    
    try {
        const response = await fetch('/db_config/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.message || 'Configurações salvas com sucesso!');
            // Redirecionar para a página inicial após 2 segundos
            setTimeout(() => {
                window.location.href = '/index';
            }, 2000);
        } else {
            showError(data.error || 'Erro ao salvar configurações');
        }
    } catch (error) {
        showError('Erro de conexão: ' + error.message);
    } finally {
        // Restaurar texto original do botão
        saveButton.innerHTML = originalText;
        saveButton.disabled = false;
    }
});

// Funções auxiliares
function getFormData() {
    return {
        host: document.getElementById('host').value,
        database: document.getElementById('database').value,
        user: document.getElementById('user').value,
        password: document.getElementById('password').value,
        port: document.getElementById('port').value
    };
}

function validateFormData(data) {
    return data.host && data.database && data.user && data.password && data.port;
}

function showSuccess(message) {
    document.getElementById('successMessage').textContent = message;
    successToast.show();
}

function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    errorToast.show();
}

// Carregar configurações quando a página for carregada
document.addEventListener('DOMContentLoaded', function() {
    fetch('/db_config/get')
        .then(response => response.json())
        .then(config => {
            document.getElementById('host').value = config.host || '';
            document.getElementById('database').value = config.database || '';
            document.getElementById('user').value = config.user || '';
            document.getElementById('password').value = config.password || '';
            document.getElementById('port').value = config.port || '';
        })
        .catch(error => {
            console.error('Erro ao carregar configurações:', error);
            showError('Erro ao carregar configurações salvas');
        });
});