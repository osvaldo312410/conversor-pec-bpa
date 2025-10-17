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

// Carregar municípios
async function loadMunicipios() {
    try {
        const response = await fetch('/api/municipios');
        const municipios = await response.json();
        
        const tbody = document.getElementById('tbodyMunicipios');
        tbody.innerHTML = '';
        
        municipios.forEach(municipio => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${municipio.rowid}</td>
                <td>${municipio.no_municipio}</td>
                <td>${municipio.ds_sigla}</td>
                <td>${municipio.nu_cnes}</td>
                <td>${municipio.nu_cnpj}</td>
                <td>${municipio.co_ibge}</td>
                <td>
                    <button class="btn btn-sm btn-warning me-1" onclick="editMunicipio(${municipio.rowid})">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteMunicipio(${municipio.rowid})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showError('Erro ao carregar municípios: ' + error.message);
    }
}

// Salvar município
document.getElementById('btnSalvar').addEventListener('click', async () => {
    const form = document.getElementById('formMunicipio');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    try {
        const response = await fetch('/api/municipio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            showSuccess('Município salvo com sucesso!');
            form.reset();
            document.getElementById('id_registro').value = '';
            loadMunicipios();
        } else {
            const error = await response.json();
            showError('Erro ao salvar: ' + error.message);
        }
    } catch (error) {
        showError('Erro ao salvar município: ' + error.message);
    }
});

// Editar município
async function editMunicipio(id) {
    try {
        const response = await fetch(`/api/municipio/${id}`);
        const municipio = await response.json();
        
        document.getElementById('id_registro').value = municipio.rowid;
        document.getElementById('no_municipio').value = municipio.no_municipio;
        document.getElementById('ds_sigla').value = municipio.ds_sigla;
        document.getElementById('nu_cnes').value = municipio.nu_cnes;
        document.getElementById('nu_cnpj').value = municipio.nu_cnpj;
        document.getElementById('co_ibge').value = municipio.co_ibge;
        
        // Scroll para o formulário
        document.getElementById('formMunicipio').scrollIntoView();
    } catch (error) {
        showError('Erro ao carregar município: ' + error.message);
    }
}

// Excluir município
async function deleteMunicipio(id) {
    if (!confirm('Tem certeza que deseja excluir este município?')) return;
    
    try {
        const response = await fetch(`/api/municipio/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showSuccess('Município excluído com sucesso!');
            loadMunicipios();
        } else {
            const error = await response.json();
            showError('Erro ao excluir: ' + error.message);
        }
    } catch (error) {
        showError('Erro ao excluir município: ' + error.message);
    }
}

// Cancelar edição
document.getElementById('btnCancelar').addEventListener('click', () => {
    document.getElementById('formMunicipio').reset();
    document.getElementById('id_registro').value = '';
});

// Carregar dados ao iniciar
document.addEventListener('DOMContentLoaded', loadMunicipios);