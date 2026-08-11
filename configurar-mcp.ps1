<#
    configurar-mcp.ps1

    Registra o servidor t2m-desktop-control na configuracao do app Claude,
    apontando direto para a pasta do projeto. Assim, alterar o codigo e
    reiniciar o app ja aplica a mudanca - sem precisar empacotar e subir zip.

    O script preserva qualquer outro servidor ja configurado e faz backup do
    arquivo antes de alterar.

    Uso (PowerShell, na pasta do projeto):
        powershell -ExecutionPolicy Bypass -File .\configurar-mcp.ps1

    Para desfazer, rode com -Remover:
        powershell -ExecutionPolicy Bypass -File .\configurar-mcp.ps1 -Remover
#>

param(
    [switch]$Remover
)

$ErrorActionPreference = 'Stop'
$nome = 't2m-desktop-control'

function Escreve($texto, $cor = 'Gray') { Write-Host $texto -ForegroundColor $cor }

Escreve ""
Escreve "=== Configurador MCP - $nome ===" 'Cyan'
Escreve ""

# ---------------------------------------------------------------------------
# 1. Localizar o servidor no projeto
# ---------------------------------------------------------------------------
$raizProjeto = Split-Path -Parent $MyInvocation.MyCommand.Path
$servidor = Join-Path $raizProjeto 'server\server.py'

if (-not (Test-Path $servidor)) {
    Escreve "ERRO: nao encontrei o servidor em:" 'Red'
    Escreve "      $servidor" 'Red'
    Escreve "Rode este script de dentro da pasta do projeto." 'Yellow'
    exit 1
}
Escreve "Servidor encontrado:" 'Green'
Escreve "  $servidor"

# Caminho no formato que o JSON prefere (barras normais)
$servidorJson = $servidor -replace '\\', '/'

# ---------------------------------------------------------------------------
# 2. Conferir o Python
# ---------------------------------------------------------------------------
$python = 'python'
try {
    $versao = & python --version 2>&1
    Escreve "Python detectado: $versao" 'Green'
} catch {
    Escreve "AVISO: o comando 'python' nao respondeu." 'Yellow'
    Escreve "       Se o servidor nao subir, troque 'command' no JSON pelo caminho completo do python.exe." 'Yellow'
}

# ---------------------------------------------------------------------------
# 3. Localizar o arquivo de configuracao do Claude
# ---------------------------------------------------------------------------
$candidatos = @()

# Instalacao via Microsoft Store (empacotada)
$pacotes = Join-Path $env:LOCALAPPDATA 'Packages'
if (Test-Path $pacotes) {
    Get-ChildItem $pacotes -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue | ForEach-Object {
        $candidatos += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')
    }
}
# Instalacao classica
$candidatos += (Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')

$config = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $config) {
    # Nenhum existe ainda: cria no primeiro caminho cuja pasta exista
    $config = $candidatos | Where-Object { Test-Path (Split-Path -Parent $_) } | Select-Object -First 1
    if (-not $config) {
        Escreve "ERRO: nao encontrei a pasta de configuracao do Claude." 'Red'
        Escreve "Caminhos testados:" 'Yellow'
        $candidatos | ForEach-Object { Escreve "  $_" 'Yellow' }
        exit 1
    }
    Escreve "Config ainda nao existe; sera criada em:" 'Yellow'
} else {
    Escreve "Config encontrada:" 'Green'
}
Escreve "  $config"

# ---------------------------------------------------------------------------
# 4. Ler o conteudo atual (preservando o que ja existe)
# ---------------------------------------------------------------------------
$dados = $null
if (Test-Path $config) {
    $bruto = Get-Content $config -Raw -Encoding UTF8
    if ($bruto.Trim()) {
        try {
            $dados = $bruto | ConvertFrom-Json
        } catch {
            Escreve "ERRO: o arquivo existe mas nao e um JSON valido." 'Red'
            Escreve "      Corrija ou renomeie o arquivo antes de rodar de novo." 'Yellow'
            exit 1
        }
    }

    # Backup antes de qualquer alteracao
    $carimbo = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$config.bak-$carimbo"
    Copy-Item $config $backup
    Escreve "Backup criado:" 'Green'
    Escreve "  $backup"
}

if (-not $dados) { $dados = [pscustomobject]@{} }
if (-not ($dados.PSObject.Properties.Name -contains 'mcpServers') -or ($null -eq $dados.mcpServers)) {
    $dados | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue ([pscustomobject]@{}) -Force
}

$existentes = @($dados.mcpServers.PSObject.Properties.Name | Where-Object { $_ })
if ($existentes.Count -gt 0) {
    Escreve "Servidores ja configurados (serao preservados):" 'Gray'
    $existentes | ForEach-Object { Escreve "  - $_" }
}

# ---------------------------------------------------------------------------
# 5. Adicionar ou remover a nossa entrada
# ---------------------------------------------------------------------------
if ($Remover) {
    if ($existentes -contains $nome) {
        $dados.mcpServers.PSObject.Properties.Remove($nome)
        Escreve "Entrada '$nome' removida." 'Yellow'
    } else {
        Escreve "Nada a remover: '$nome' nao estava configurado." 'Yellow'
        exit 0
    }
} else {
    $entrada = [pscustomobject]@{
        command = $python
        args    = @($servidorJson)
        env     = [pscustomobject]@{
            T2M_APPROVAL_MODE    = 'ask'
            T2M_APPROVAL_TIMEOUT = '45'
        }
    }
    $dados.mcpServers | Add-Member -NotePropertyName $nome -NotePropertyValue $entrada -Force
    if ($existentes -contains $nome) {
        Escreve "Entrada '$nome' atualizada." 'Green'
    } else {
        Escreve "Entrada '$nome' adicionada." 'Green'
    }
}

# ---------------------------------------------------------------------------
# 6. Gravar (UTF-8 sem BOM, que e o que o app espera)
# ---------------------------------------------------------------------------
$json = $dados | ConvertTo-Json -Depth 10
$semBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($config, $json, $semBom)

Escreve ""
Escreve "Configuracao gravada com sucesso." 'Green'
Escreve ""
Escreve "--- conteudo final ---" 'Cyan'
Escreve $json
Escreve ""
Escreve "PROXIMOS PASSOS:" 'Cyan'
Escreve "  1. Desligue o plugin 'T2m desktop control' em Configuracoes > Plugins"
Escreve "     (senao dois servidores iguais vao rodar ao mesmo tempo)."
Escreve "  2. Feche o app do Claude POR COMPLETO - inclusive pelo icone na bandeja,"
Escreve "     perto do relogio - e abra de novo."
Escreve ""
