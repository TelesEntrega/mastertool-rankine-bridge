<#
.SYNOPSIS
    Cataloga, por reflection ESTATICA (Assembly.ReflectionOnlyLoadFrom — carrega
    apenas metadados, nao executa nenhum codigo do assembly), os tipos do
    MasterTool IEC XE relacionados a projetos, navegacao de arvore e leitura
    textual de POUs.

.DESCRIPTION
    Ferramenta externa (nao roda dentro do MasterTool). Le os assemblies
    instalados localmente e emite um catalogo JSON bruto dos tipos-semente
    listados em $SeedTypes, mais os tipos diretamente referenciados por eles
    (profundidade 1 — parametros de metodo, tipos de retorno, interfaces
    implementadas). Nao faz uma varredura de toda a instalacao: limita-se ao
    grafo alcancavel a partir das sementes.

    Nunca instancia nada, nunca chama metodo nenhum: so leitura de metadados
    (System.Reflection). Seguro para rodar quantas vezes quiser, mesmo sem o
    MasterTool aberto.

.PARAMETER MasterToolRoot
    Raiz da instalacao do MasterTool (pasta que contem Common/, PlugIns/, etc).

.PARAMETER OutputPath
    Caminho do JSON de saida. Por padrao, workspace/analysis/static-api/raw-catalog.json
    relativo a raiz do repositorio (dois niveis acima de tools/).

.EXAMPLE
    powershell -File tools/static-api-catalog.ps1
#>
param(
    [string]$MasterToolRoot = "C:\Program Files (x86)\Altus\MT8500 3.63\MT8500",
    [string]$OutputPath = $null
)

if (-not $OutputPath) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $OutputPath = Join-Path $repoRoot "workspace\analysis\static-api\raw-catalog.json"
}

# Sementes: assembly (BaseName) -> lista de FullName de tipos a inspecionar.
# Adicione aqui somente apos justificar em docs/api/mastertool-api-observations.md
# por que o tipo e relevante — isto NAO e uma varredura livre.
$Seeds = @(
    @{ Assembly = "ScriptDriverProjects.plugin"; Type = "_3S.CoDeSys.ScriptDriverProjects.ScriptProjects" },
    @{ Assembly = "ScriptDriverProjects.plugin"; Type = "_3S.CoDeSys.ScriptDriverProjects.ScriptApplication" },
    @{ Assembly = "ScriptDriverProjects.plugin"; Type = "_3S.CoDeSys.ScriptDriverProjects.ScriptTextDocument" },
    @{ Assembly = "ScriptEngine.plugin";         Type = "_3S.CoDeSys.ScriptEngine.ExtendedObject``1" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProject" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptTreeObject" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptObject" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptApplication" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptTextDocument" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptTextualObjectMarker" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptObjectWithTextualDeclaration" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptObjectWithTextualImplementation" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptPouObjectCollection" },
    @{ Assembly = "ScriptEngine3";               Type = "_3S.CoDeSys.ScriptEngine.BasicFunctionality.PouType" },
    @{ Assembly = "ScriptDriverSystem.plugin";    Type = "_3S.CoDeSys.ScriptDriverSystem.ScriptMessage" }
)

function Build-AssemblyIndex {
    param([string]$Root)
    $netfx = @(
        "C:\Windows\Microsoft.NET\Framework\v4.0.30319",
        "C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
    )
    $searchDirs = @("$Root\Common", "$Root\LacBinaries", "$Root\PlugIns", "$Root\CompatibilityInterfaces") + $netfx
    $index = @{}
    Get-ChildItem -Path $searchDirs -Recurse -Include *.dll, *.exe -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not $index.ContainsKey($_.BaseName)) { $index[$_.BaseName] = $_.FullName }
    }
    return $index
}

function Get-TypesSafely {
    param($Assembly)
    try {
        return $Assembly.GetTypes()
    } catch [System.Reflection.ReflectionTypeLoadException] {
        return $_.Exception.Types | Where-Object { $_ -ne $null }
    }
}

function Convert-Member {
    param($Type)
    $result = [ordered]@{
        full_name    = $Type.FullName
        is_public    = $Type.IsPublic
        is_interface = $Type.IsInterface
        is_enum      = $Type.IsEnum
        is_generic   = $Type.IsGenericType
        base_type    = if ($Type.BaseType) { $Type.BaseType.FullName } else { $null }
        interfaces   = @($Type.GetInterfaces() | ForEach-Object { $_.FullName })
        enum_values  = @()
        properties   = @()
        methods      = @()
        fields       = @()
    }
    if ($Type.IsEnum) {
        $result.enum_values = @($Type.GetEnumNames())
        return $result
    }
    $flags = [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::NonPublic `
        -bor [System.Reflection.BindingFlags]::Instance -bor [System.Reflection.BindingFlags]::Static
    foreach ($p in $Type.GetProperties($flags)) {
        $result.properties += [ordered]@{
            name       = $p.Name
            type       = $p.PropertyType.FullName
            can_read   = $p.CanRead
            can_write  = $p.CanWrite
        }
    }
    $declaredFlags = $flags -bor [System.Reflection.BindingFlags]::DeclaredOnly
    foreach ($m in ($Type.GetMethods($declaredFlags) | Where-Object { -not $_.IsSpecialName })) {
        $params = @()
        try {
            foreach ($p in $m.GetParameters()) {
                $params += [ordered]@{ name = $p.Name; type = $p.ParameterType.FullName; optional = $p.IsOptional }
            }
        } catch { }
        $result.methods += [ordered]@{
            name       = $m.Name
            is_static  = $m.IsStatic
            is_public  = $m.IsPublic
            return_type = $m.ReturnType.FullName
            parameters = $params
        }
    }
    foreach ($f in $Type.GetFields($flags)) {
        $result.fields += [ordered]@{ name = $f.Name; type = $f.FieldType.FullName }
    }
    return $result
}

Write-Host "Indexando assemblies em $MasterToolRoot ..."
$index = Build-AssemblyIndex -Root $MasterToolRoot
Write-Host ("Assemblies indexados: " + $index.Count)

$resolver = {
    param($sender, $resolveArgs)
    $asmName = New-Object System.Reflection.AssemblyName($resolveArgs.Name)
    if ($index.ContainsKey($asmName.Name)) {
        try { return [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($index[$asmName.Name]) } catch { return $null }
    }
    return $null
}
[System.AppDomain]::CurrentDomain.add_ReflectionOnlyAssemblyResolve($resolver)

$catalog = [ordered]@{
    generated_by = "tools/static-api-catalog.ps1"
    method       = "Assembly.ReflectionOnlyLoadFrom (metadados apenas, nenhum codigo executado)"
    mastertool_root = $MasterToolRoot
    types        = @()
    not_found    = @()
}

foreach ($seed in $Seeds) {
    if (-not $index.ContainsKey($seed.Assembly)) {
        $catalog.not_found += [ordered]@{ assembly = $seed.Assembly; type = $seed.Type; reason = "assembly nao indexado" }
        continue
    }
    try {
        $asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($index[$seed.Assembly])
        $types = Get-TypesSafely -Assembly $asm
        $t = $types | Where-Object { $_.FullName -eq $seed.Type }
        if (-not $t) {
            $catalog.not_found += [ordered]@{ assembly = $seed.Assembly; type = $seed.Type; reason = "tipo nao encontrado no assembly" }
            continue
        }
        $entry = Convert-Member -Type $t
        $entry.assembly = $asm.GetName().Name
        $entry.assembly_version = $asm.GetName().Version.ToString()
        $catalog.types += $entry
        Write-Host ("OK: " + $seed.Type)
    } catch {
        $catalog.not_found += [ordered]@{ assembly = $seed.Assembly; type = $seed.Type; reason = ("excecao: " + $_.Exception.Message) }
    }
}

$outDir = Split-Path -Parent $OutputPath
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
$catalog | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputPath -Encoding utf8
Write-Host ("Catalogo gravado em: " + $OutputPath)
