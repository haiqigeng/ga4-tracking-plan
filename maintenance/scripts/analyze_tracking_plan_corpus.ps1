param(
    [Parameter(Mandatory = $true)]
    [string]$InputFolder,

    [Parameter(Mandatory = $true)]
    [string]$OutputJson,

    [Parameter(Mandatory = $false)]
    [int]$MaxCellTextsPerWorkbook = 25000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Normalize-Text {
    param([AllowNull()][string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    return ($Text -replace "\s+", " ").Trim().ToLowerInvariant()
}

function Count-Pattern {
    param(
        [string[]]$Texts,
        [string]$Pattern
    )
    $count = 0
    foreach ($text in $Texts) {
        if ($text -match $Pattern) { $count++ }
    }
    return $count
}

function Get-ZipText {
    param(
        [System.IO.Compression.ZipArchive]$Zip,
        [string]$Path
    )
    $entry = $Zip.GetEntry($Path)
    if ($null -eq $entry) { return $null }
    $stream = $entry.Open()
    try {
        $reader = [System.IO.StreamReader]::new($stream)
        try { return $reader.ReadToEnd() }
        finally { $reader.Dispose() }
    }
    finally { $stream.Dispose() }
}

function Get-XmlDocument {
    param([AllowNull()][string]$XmlText)
    if ([string]::IsNullOrWhiteSpace($XmlText)) { return $null }
    $doc = [System.Xml.XmlDocument]::new()
    $doc.PreserveWhitespace = $false
    $doc.LoadXml($XmlText)
    return $doc
}

function Get-SharedStrings {
    param([System.IO.Compression.ZipArchive]$Zip)

    $xml = Get-ZipText -Zip $Zip -Path "xl/sharedStrings.xml"
    if ($null -eq $xml) { return @() }
    $doc = Get-XmlDocument -XmlText $xml
    $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
    $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

    $values = New-Object System.Collections.Generic.List[string]
    foreach ($si in $doc.SelectNodes("//x:si", $ns)) {
        $parts = New-Object System.Collections.Generic.List[string]
        foreach ($t in $si.SelectNodes(".//x:t", $ns)) {
            [void]$parts.Add($t.InnerText)
        }
        [void]$values.Add(($parts -join ""))
    }
    return $values.ToArray()
}

function Get-WorkbookSheets {
    param([System.IO.Compression.ZipArchive]$Zip)

    $workbookXml = Get-ZipText -Zip $Zip -Path "xl/workbook.xml"
    $relsXml = Get-ZipText -Zip $Zip -Path "xl/_rels/workbook.xml.rels"
    if ($null -eq $workbookXml -or $null -eq $relsXml) { return @() }

    $workbook = Get-XmlDocument -XmlText $workbookXml
    $rels = Get-XmlDocument -XmlText $relsXml

    $bookNs = [System.Xml.XmlNamespaceManager]::new($workbook.NameTable)
    $bookNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    $bookNs.AddNamespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")

    $relsNs = [System.Xml.XmlNamespaceManager]::new($rels.NameTable)
    $relsNs.AddNamespace("rel", "http://schemas.openxmlformats.org/package/2006/relationships")

    $targetById = @{}
    foreach ($rel in $rels.SelectNodes("//rel:Relationship", $relsNs)) {
        $target = $rel.GetAttribute("Target")
        if (-not $target.StartsWith("/")) {
            $target = "xl/" + $target.TrimStart("/")
        } else {
            $target = $target.TrimStart("/")
        }
        $targetById[$rel.GetAttribute("Id")] = $target
    }

    $sheets = New-Object System.Collections.Generic.List[object]
    foreach ($sheet in $workbook.SelectNodes("//x:sheets/x:sheet", $bookNs)) {
        $rid = $sheet.GetAttribute("id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
        [void]$sheets.Add([ordered]@{
            name = $sheet.GetAttribute("name")
            sheet_id = $sheet.GetAttribute("sheetId")
            path = $targetById[$rid]
        })
    }
    return $sheets.ToArray()
}

function Get-SheetTexts {
    param(
        [System.IO.Compression.ZipArchive]$Zip,
        [string]$SheetPath,
        [string[]]$SharedStrings,
        [int]$Limit
    )

    $xml = Get-ZipText -Zip $Zip -Path $SheetPath
    if ($null -eq $xml) {
        return [ordered]@{ dimension = ""; texts = @(); cell_count = 0 }
    }

    $dimension = ""
    $dimensionMatch = [regex]::Match($xml, '<dimension\s+ref="([^"]+)"')
    if ($dimensionMatch.Success) { $dimension = $dimensionMatch.Groups[1].Value }

    # For corpus-level learning, sharedStrings already contains nearly all human-authored
    # labels and examples. Avoid scanning every worksheet cell because image-heavy plans
    # can make that unnecessarily slow.
    $cellCount = ([regex]::Matches($xml, "<c\b")).Count

    return [ordered]@{
        dimension = $dimension
        texts = @()
        cell_count = $cellCount
    }
}

function Get-PatternMatches {
    param([string[]]$Texts)

    $joined = ($Texts -join "`n")
    $defs = [ordered]@{
        ga4 = @("ga4", "google analytics 4", "\bevent_name\b", "\bview_item\b", "\bselect_item\b", "\badd_to_cart\b", "\bbegin_checkout\b", "\bpurchase\b", "\bitems\[\]\b", "\bitem_id\b", "\bsearch_term\b", "gtag\('event", "\bg-[a-z0-9]+")
        universal_analytics_legacy = @("universal analytics", "\bga3\b", "\bgau\b", "\bga360\b", "eventcategory", "event category", "eventaction", "event action", "eventlabel", "event label", "noninteraction", "enhanced ecommerce", "ua-[0-9]+", "dimension[0-9]+", "metric[0-9]+")
        gtm_datalayer = @("\bgtm\b", "gtm-[a-z0-9]+", "datalayer", "datalayer\.push", "\becommerce\b")
        ecommerce = @("ecommerce", "e-commerce", "product", "produit", "cart", "panier", "checkout", "paiement", "purchase", "transaction", "add_to_cart", "remove_from_cart", "view_item", "select_item", "item_list")
        lead_generation = @("lead", "formulaire", "\bform\b", "devis", "quote", "callback", "rappel", "appointment", "rdv", "contact")
        search_listing = @("search", "recherche", "filter", "filtre", "sort", "\btri\b", "listing", "plp", "category", "categorie", "result")
        account_support_content = @("login", "connexion", "signup", "inscription", "account", "compte", "espace", "faq", "support", "download", "telecharg", "newsletter", "article", "video")
        donation_nonprofit = @("don", "donation", "adhesion", "benevole", "petition", "newsletter")
        screenshots = @("screenshot", "screen shot", "capture", "capture d.ecran", "visuel", "maquette")
        pii_risk_terms = @("email", "e-mail", "mail", "phone", "telephone", "téléphone", "prenom", "prénom", "\bnom\b", "lastname", "firstname", "adresse", "address", "postal", "customer_id", "user_id", "client_id")
    }

    $result = [ordered]@{}
    foreach ($key in $defs.Keys) {
        $count = 0
        foreach ($pattern in $defs[$key]) {
            $count += ([regex]::Matches($joined, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        }
        $result[$key] = $count
    }
    return $result
}

function Get-SecretSignals {
    param([string[]]$Texts)

    $joined = ($Texts -join "`n")
    return [ordered]@{
        urls = ([regex]::Matches($joined, "https?://[^\s\)""']+", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        email_like = ([regex]::Matches($joined, "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        phone_like = ([regex]::Matches($joined, "(?<!\d)(?:\+33|0)\s*[1-9](?:[\s\.-]*\d{2}){4}(?!\d)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        gtm_ids = ([regex]::Matches($joined, "GTM-[A-Z0-9]+", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        ga4_measurement_ids = ([regex]::Matches($joined, "G-[A-Z0-9]+", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        ua_property_ids = ([regex]::Matches($joined, "UA-\d+-\d+", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
    }
}

function Classify-Platform {
    param([System.Collections.IDictionary]$Signals)

    $platforms = New-Object System.Collections.Generic.List[string]
    if ($Signals["ga4"] -gt 0) { [void]$platforms.Add("ga4") }
    if ($Signals["universal_analytics_legacy"] -gt 0) { [void]$platforms.Add("universal_analytics_legacy") }
    if ($platforms.Count -eq 0 -and $Signals["gtm_datalayer"] -gt 0) { [void]$platforms.Add("gtm_unknown_analytics") }
    if ($platforms.Count -eq 0) { [void]$platforms.Add("unknown") }
    return $platforms.ToArray()
}

$files = Get-ChildItem -LiteralPath $InputFolder -Recurse -File -Filter "*.xlsx" | Sort-Object FullName
$items = New-Object System.Collections.Generic.List[object]
$aggregate = [ordered]@{
    file_count = $files.Count
    platform_counts = [ordered]@{}
    scenario_counts = [ordered]@{}
    signal_totals = [ordered]@{}
    files_with_media = 0
    files_with_confidentiality_signals = 0
}

foreach ($file in $files) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($file.FullName)
    try {
        $sharedStrings = Get-SharedStrings -Zip $zip
        $sheets = Get-WorkbookSheets -Zip $zip
        $sheetSummaries = New-Object System.Collections.Generic.List[object]
        $allTexts = New-Object System.Collections.Generic.List[string]
        [void]$allTexts.Add((Normalize-Text -Text $file.Name))
        foreach ($value in $sharedStrings | Select-Object -First $MaxCellTextsPerWorkbook) {
            $normalized = Normalize-Text -Text $value
            if ($normalized.Length -gt 0) { [void]$allTexts.Add($normalized) }
        }

        foreach ($sheet in $sheets) {
            [void]$allTexts.Add((Normalize-Text -Text $sheet.name))
            $sheetInfo = Get-SheetTexts -Zip $zip -SheetPath $sheet.path -SharedStrings $sharedStrings -Limit 0
            [void]$sheetSummaries.Add([ordered]@{
                name = $sheet.name
                dimension = $sheetInfo.dimension
                cell_count = $sheetInfo.cell_count
                sampled_text_count = 0
            })
        }

        $texts = $allTexts.ToArray()
        $signals = Get-PatternMatches -Texts $texts
        $secretSignals = Get-SecretSignals -Texts $texts
        $platforms = Classify-Platform -Signals $signals
        $mediaCount = ($zip.Entries | Where-Object { $_.FullName -like "xl/media/*" }).Count

        foreach ($platform in $platforms) {
            if (-not $aggregate.platform_counts.Contains($platform)) { $aggregate.platform_counts[$platform] = 0 }
            $aggregate.platform_counts[$platform]++
        }

        foreach ($scenario in @("ecommerce", "lead_generation", "search_listing", "account_support_content", "donation_nonprofit")) {
            if ($signals[$scenario] -gt 0) {
                if (-not $aggregate.scenario_counts.Contains($scenario)) { $aggregate.scenario_counts[$scenario] = 0 }
                $aggregate.scenario_counts[$scenario]++
            }
        }

        foreach ($key in $signals.Keys) {
            if (-not $aggregate.signal_totals.Contains($key)) { $aggregate.signal_totals[$key] = 0 }
            $aggregate.signal_totals[$key] += $signals[$key]
        }

        if ($mediaCount -gt 0) { $aggregate.files_with_media++ }
        $secretTotal = 0
        foreach ($value in $secretSignals.Values) { $secretTotal += [int]$value }
        if ($secretTotal -gt 0) { $aggregate.files_with_confidentiality_signals++ }

        [void]$items.Add([ordered]@{
            file_name = $file.Name
            relative_path = Resolve-Path -LiteralPath $file.FullName -Relative
            size_bytes = $file.Length
            last_write_time = $file.LastWriteTime.ToString("s")
            platforms_detected = $platforms
            signals = $signals
            confidentiality_signal_counts = $secretSignals
            has_embedded_media = ($mediaCount -gt 0)
            embedded_media_count = $mediaCount
            sheets = $sheetSummaries.ToArray()
        })
    }
    catch {
        [void]$items.Add([ordered]@{
            file_name = $file.Name
            relative_path = Resolve-Path -LiteralPath $file.FullName -Relative
            error = $_.Exception.Message
        })
    }
    finally {
        $zip.Dispose()
    }
}

$report = [ordered]@{
    generated_at = (Get-Date).ToString("s")
    source_folder = $InputFolder
    note = "Privacy-safe inventory: no raw workbook rows or cell values are retained; only counts, sheet names, dimensions, and signal classifications."
    aggregate = $aggregate
    workbooks = $items.ToArray()
}

$outputDirectory = Split-Path -Parent $OutputJson
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
Write-Host "Wrote $OutputJson"
