document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const content = document.getElementById('content');
    const sidebarToggle = document.getElementById('sidebarToggle');
    
    // Verificar se estamos em uma tela pequena ao carregar
    function checkScreenSize() {
        if (window.innerWidth <= 768) {
            sidebar.classList.add('collapsed');
            content.classList.add('collapsed');
            document.getElementById('username').style.display = 'none';
        } else {
            sidebar.classList.remove('collapsed');
            content.classList.remove('collapsed');
            document.getElementById('username').style.display = 'inline';
        }
    }
    
    // Alternar menu lateral
    sidebarToggle.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        content.classList.toggle('collapsed');
        
        // Atualizar texto do usuário quando o menu é recolhido
        const username = document.getElementById('username');
        if (sidebar.classList.contains('collapsed')) {
            username.style.display = 'none';
        } else {
            username.style.display = 'inline';
        }
    });
    
    // Ajustar para telas pequenas
    function handleResize() {
        if (window.innerWidth <= 768) {
            // Se for tela pequena, garantir que o menu está recolhido
            sidebar.classList.add('collapsed');
            content.classList.add('collapsed');
            document.getElementById('username').style.display = 'none';
        } else {
            // Se for tela grande, garantir que o menu está expandido
            sidebar.classList.remove('collapsed');
            content.classList.remove('collapsed');
            document.getElementById('username').style.display = 'inline';
        }
    }
    
    // Verificar tamanho da tela ao carregar e redimensionar
    window.addEventListener('resize', handleResize);
    
    // Inicializar
    checkScreenSize();
});

// Pre-preenchimento do campo cid
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select.auto-select-first").forEach(function(select) {
        if (select.options.length > 0) {
            select.selectedIndex = 0; // força selecionar a primeira opção
        }
    });
});

