---
name: fix-dependency-model
description: Fixes AWS deploy crash "Could not load file or assembly 'Microsoft.Extensions.DependencyModel'" in Shine/Playon .NET services. Root cause is Dockerfile `dotnet publish` of the whole solution into one flat out/ folder — test projects (coverlet.collector) overwrite the host's DependencyModel. Fix by setting IsPublishable false on test projects. Use immediately when this exception, assembly-not-found for DependencyModel, or a coverlet/test-publish version clash appears. Do not add a Host PackageReference for DependencyModel.
---

# Fix Microsoft.Extensions.DependencyModel publish clash

## Error

```
Unhandled exception. System.IO.FileNotFoundException: Could not load file or assembly
'Microsoft.Extensions.DependencyModel, Version=10.0.0.0, Culture=neutral, PublicKeyToken=adb9793829ddae60'
```

Serilog raises this while reading its configuration. It is a race: last writer to `out/` wins, so it only shows up after test-project or publish-order changes.

## Root cause

The Dockerfile runs `dotnet publish` on the **whole solution** into a single flat `out/` folder that becomes the runtime image.

The solution includes test projects. `coverlet.collector` ships `Microsoft.Extensions.DependencyModel` 8.0.2; the Host needs 10.x. Both write the same filename. When coverlet's copy wins, the host asks the CLR for assembly version `10.0.0.0` and gets `8.0.0.0`.

Do **not** pin or add `Microsoft.Extensions.DependencyModel` on the Host csproj / `Directory.Packages.props`. That papers over the clash; the next test dependency can still overwrite `out/`.

## Fix

1. Find every test project (`*Tests*.csproj`, `*Test*.csproj`).
2. Add `<IsPublishable>false</IsPublishable>` beside the existing `<IsPackable>false</IsPackable>` (add `IsPackable` too if missing):

```xml
<PropertyGroup>
  <IsPackable>false</IsPackable>
  <IsPublishable>false</IsPublishable>
</PropertyGroup>
```

3. Verify with the **exact** `dotnet publish` from that repo's Dockerfile (usually `dotnet publish "<Solution>.sln" --no-restore -c Release -o out`).
4. Confirm `out/` has no test binaries: no `Moq.dll`, no `*.Tests.dll`, no `coverlet.collector.deps.json`.
5. Confirm the host `*.deps.json` has a single `Microsoft.Extensions.DependencyModel` expectation at the host version (e.g. `10.0.12`).
6. Confirm tests still build and run (`dotnet test`).
