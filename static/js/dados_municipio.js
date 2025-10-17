document.addEventListener('DOMContentLoaded', function() {
    const formMunicipio = document.getElementById('formMunicipio');
    const modal = new bootstrap.Modal(document.getElementById('modalDadosMunicipio'));
    const modalTitle = document.getElementById('modalDadosMunicipioLabel');
    const tabelaMunicipios = document.getElementById('tabelaMunicipios').getElementsByTagName('tbody')[0];
    
    // Carregar dados ao iniciar
    carregarMunicipios();
    
    // Evento para abrir modal para novo registro
    document.getElementById('btnNovoMunicipio').addEventListener('click', function() {
        formMunicipio.reset();
        document.getElementById('id_registro').value = '';
        modalTitle.textContent = 'Novo Município';
    });
    
    // Evento de submit do formulário
    formMunicipio.addEventListener('submit', function(e) {
        e.preventDefault();
        salvarMunicipio();
    });
    
    // Função para carregar os municípios
    function carregarMunicipios() {
        fetch('/municipios')
            .then(response => response.json())
            .then(data => {
                tabelaMunicipios.innerHTML = '';
                data.forEach(municipio => {
                    const row = tabelaMunicipios.insertRow();
                    row.innerHTML = `
                        <td>${municipio.no_municipio}</td>
                        <td>${municipio.ds_sigla}</td>
                        <td>${municipio.nu_cnes || '-'}</td>
                        <td>${municipio.nu_cnpj || '-'}</td>
                        <td>${municipio.co_ibge || '-'}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary me-1" onclick="editarMunicipio(${municipio.id})">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="excluirMunicipio(${municipio.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    `;
                });
            })
            .catch(error => console.error('Erro ao carregar municípios:', error));
    }
    
    // Função para salvar município (novo ou edição)
    window.salvarMunicipio = function() {
        const formData = new FormData(formMunicipio);
        const idRegistro = document.getElementById('id_registro').value;
        const url = idRegistro ? `/municipio/${idRegistro}` : '/municipio';
        const method = idRegistro ? 'PUT' : 'POST';
        
        fetch(url, {
            method: method,
            body: JSON.stringify(Object.fromEntries(formData)),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modal.hide();
                carregarMunicipios();
                alert('Dados salvos com sucesso!');
            } else {
                alert('Erro ao salvar dados: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('Erro ao salvar dados.');
        });
    };
    
    // Função para editar município
    window.editarMunicipio = function(id) {
        fetch(`/municipio/${id}`)
            .then(response => response.json())
            .then(municipio => {
                document.getElementById('id_registro').value = municipio.id;
                document.getElementById('no_municipio').value = municipio.no_municipio;
                document.getElementById('ds_sigla').value = municipio.ds_sigla;
                document.getElementById('nu_cnes').value = municipio.nu_cnes || '';
                document.getElementById('nu_cnpj').value = municipio.nu_cnpj || '';
                document.getElementById('co_ibge').value = municipio.co_ibge || '';
                
                modalTitle.textContent = 'Editar Município';
                modal.show();
            })
            .catch(error => console.error('Erro ao carregar município:', error));
    };
    
    // Função para excluir município
    window.excluirMunicipio = function(id) {
        if (confirm('Tem certeza que deseja excluir este município?')) {
            fetch(`/municipio/${id}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    carregarMunicipios();
                    alert('Município excluído com sucesso!');
                } else {
                    alert('Erro ao excluir município: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                alert('Erro ao excluir município.');
            });
        }
    };
});