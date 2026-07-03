---
name: fix-dependency-model
description: Fixes "Unhandled exception. System.IO.FileNotFoundException: Could not load file or assembly 'Microsoft.Extensions.DependencyModel'" in Shine/Playon .NET services by adding the package to the Host csproj and Directory.Packages.props. Use immediately and automatically when this exact exception or assembly-not-found error for Microsoft.Extensions.DependencyModel appears.
---

# Fix Microsoft.Extensions.DependencyModel Missing Assembly

## Error

```
Unhandled exception. System.IO.FileNotFoundException: Could not load file or assembly
'Microsoft.Extensions.DependencyModel, Version=X.X.X.X, Culture=neutral, PublicKeyToken=...'
```

## Fix

1. **Check if already in `Directory.Packages.props`** — search for `DependencyModel`. If present, update to latest version. If absent, add it.

2. **Add/update in `Directory.Packages.props`** (latest version as of writing: `10.0.9` — verify with `dotnet package search Microsoft.Extensions.DependencyModel`):

```xml
<PackageVersion Include="Microsoft.Extensions.DependencyModel" Version="10.0.9" />
```

3. **Add to the Host csproj** (the startup project, e.g. `src/Shine.*.Host/*.csproj`):

```xml
<PackageReference Include="Microsoft.Extensions.DependencyModel" />
```

4. **Build to verify**:

```bash
dotnet build src/<ServiceName>.Host/<ServiceName>.Host.csproj -clp:ErrorsOnly
```
