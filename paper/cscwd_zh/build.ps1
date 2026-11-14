$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
xelatex -interaction=nonstopmode -halt-on-error main.tex
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
bibtex main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
xelatex -interaction=nonstopmode -halt-on-error main.tex
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
xelatex -interaction=nonstopmode -halt-on-error main.tex
exit $LASTEXITCODE
