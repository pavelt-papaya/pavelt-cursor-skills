---
name: introduce-metrics
description: >-
  Introduces metrics instrumentation to a .NET Shine service. Creates a feature-specific metrics
  interface, adds its implementation to the shared metrics class, registers it in DI, and exports
  the meter in Program.cs. Use this skill immediately and automatically whenever the user says
  "introduce metrics", "add metrics", "use metrics", "create metrics", "implement metrics",
  "metrics in code", or asks to instrument or add observability to a Shine service — for example
  "introduce metrics for repository queue", "add metrics to the media service", "use metrics in code",
  "create metrics for X". Do not ask for clarification, just execute the workflow.
---

# Introduce Metrics

Adds metrics to a Shine .NET service following the established pattern:

1. Feature-scoped **interface** → `Domain/Services/{Feature}/I{Feature}Metrics.cs`
2. **Implementation** in the shared `{ServiceName}Metrics` class → `Domain/{ServiceName}Metrics.cs`
3. **DI registration** in `DomainDI.cs`
4. **Meter export** in `Program.cs`

Uses only `System.Diagnostics.Metrics` (BCL) — no extra NuGet packages needed.

---

## Step 1 – Create the interface

File: `src/{ServiceName}.Domain/Services/{Feature}/I{Feature}Metrics.cs`

```csharp
namespace {ServiceNamespace}.Domain.Services.{Feature};

public interface I{Feature}Metrics
{
    void Record{EventA}(double value);
    void Record{EventB}(double value, string tag);
}
```

Name methods `Record*`, accept only the tag values (strings/enums) needed for the metric dimensions.

---

## Step 2 – Implement in the shared metrics class

File: `src/{ServiceName}.Domain/{ServiceName}Metrics.cs`

If the file **does not exist yet**, create it from this template:

```csharp
using System.Diagnostics.Metrics;
// add interface namespaces

namespace {ServiceNamespace}.Domain;

public class {ServiceName}Metrics : I{Feature}Metrics  // add more interfaces as they appear
{
    public const string MeterName = "{servicename}";  // lowercase, e.g. "tournaments"

    // tag name constants
    private const string SomeTag = "some_tag";

    // instrument fields
    private readonly Histogram<double> _{eventA}Histogram;
    private readonly Histogram<double> _{eventB}Histogram;

    public {ServiceName}Metrics(IMeterFactory meterFactory, string appName)
    {
        string MetricName(string name) => $"{appName}.{name}";

        var meter = meterFactory.Create(MeterName);

        _{eventA}Histogram = meter.CreateHistogram<double>(MetricName("{feature}.{event_a}"));
        _{eventB}Histogram = meter.CreateHistogram<double>(MetricName("{feature}.{event_b}"));
    }

    public void Record{EventA}(double value)
    {
        _{eventA}Histogram.Record(value);
    }

    public void Record{EventB}(double value, string someTag)
    {
        _{eventB}Histogram.Record(value, new KeyValuePair<string, object?>(SomeTag, someTag));
    }
}
```

If the class **already exists**, just:
- Add `I{Feature}Metrics` to the `implements` list
- Add the new instrument fields to the constructor
- Add the new `Record*` method implementations

Histograms are the default. Use `Counter<long>` with `.Add(1, tags)` only when you need a pure count with no distribution (e.g. error counts).

---

## Step 3 – Register in DI

In `DomainDI.RegisterDomainMappings`, add one line per interface inside the chained `.AddSingleton` block:

```csharp
.AddSingleton<I{Feature}Metrics, {ServiceName}Metrics>(sp =>
    ActivatorUtilities.CreateInstance<{ServiceName}Metrics>(sp, appName))
```

If multiple interfaces map to the same class, add a separate `.AddSingleton` line for each interface (the factory instantiates the class once per interface — that is fine because `{ServiceName}Metrics` is cheap and stateless beyond its counters).

> **`appName` origin:** `appName` is resolved in `Program.cs` via:
> ```csharp
> var appName = settings.Configuration.GetAppName(settings.Environment);
> ```
> `GetAppName` is defined in `Shine.Infra.Configuration.ConfigurationExtensions` — ensure `using Shine.Infra.Configuration;` is present wherever this call is made. The value is then passed into `RegisterDomainMappings` as a parameter, so it is already available there — no extra work needed when adding the `.AddSingleton` line.

---

## Step 4 – Export the meter in Program.cs

Inside `settings.SetTelemetry(metricsAction: ...)`:

```csharp
settings.SetTelemetry(metricsAction: meterProviderBuilder =>
{
    meterProviderBuilder.AddMeter({ServiceName}Metrics.MeterName);
});
```

If `SetTelemetry` with `metricsAction` is **not yet present**, add it inside `.ConfigureServices(settings => { ... })`.

---

## Metric naming conventions

| Concept | Convention | Example |
|---------|-----------|---------|
| Default instrument | `Histogram<double>` | — |
| Meter name | `{servicename}` (lowercase) | `"tournaments"` |
| Metric name | `{appName}.{feature}.{event}` (dots, lowercase) | `"tournaments-service.geolocation.resolution.failures"` |
| Tag names | `snake_case` | `"provider"`, `"resolution_type"` |
| Tag constant fields | `private const string {Name}Tag` | `private const string ProviderTag = "provider";` |

---

## Real example from `backend-tournaments-service`

**Interface** (`IGeolocationMetrics.cs`):
```csharp
namespace Shine.Tournaments.Domain.Services.GeoLocation;

public interface IGeolocationMetrics
{
    void RecordResolutionSuccess(string providerAlias, string resolutionType);
    void RecordResolutionFailure(string resolutionType);
    void RecordProviderFailure(string providerAlias, string reason);
}
```

**Implementation** (excerpt from `TournamentsMetrics.cs`):
```csharp
public class TournamentsMetrics : IGeolocationMetrics
{
    public const string MeterName = "tournaments";

    private const string ProviderTag       = "provider";
    private const string ReasonTag         = "reason";
    private const string ResolutionTypeTag = "resolution_type";

    private readonly Counter<long> _geolocationResolutionFailures;
    private readonly Counter<long> _geolocationResolutionSuccesses;
    private readonly Counter<long> _geolocationProviderFailures;

    public TournamentsMetrics(IMeterFactory meterFactory, string appName)
    {
        string MetricName(string name) => $"{appName}.{name}";
        var meter = meterFactory.Create(MeterName);

        _geolocationResolutionFailures  = meter.CreateCounter<long>(MetricName("geolocation.resolution.failures"));
        _geolocationResolutionSuccesses = meter.CreateCounter<long>(MetricName("geolocation.resolution.successes"));
        _geolocationProviderFailures    = meter.CreateCounter<long>(MetricName("geolocation.provider.failures"));
    }

    public void RecordResolutionSuccess(string providerAlias, string resolutionType) =>
        _geolocationResolutionSuccesses.Add(1,
            new KeyValuePair<string, object?>(ProviderTag, providerAlias),
            new KeyValuePair<string, object?>(ResolutionTypeTag, resolutionType));

    public void RecordResolutionFailure(string resolutionType) =>
        _geolocationResolutionFailures.Add(1, new KeyValuePair<string, object?>(ResolutionTypeTag, resolutionType));

    public void RecordProviderFailure(string providerAlias, string reason) =>
        _geolocationProviderFailures.Add(1,
            new KeyValuePair<string, object?>(ProviderTag, providerAlias),
            new KeyValuePair<string, object?>(ReasonTag, reason));
}
```

**DI registration** (`DomainDI.cs`):
```csharp
.AddSingleton<IGeolocationMetrics, TournamentsMetrics>(sp =>
    ActivatorUtilities.CreateInstance<TournamentsMetrics>(sp, appName))
```

**Meter export** (`Program.cs`):
```csharp
settings.SetTelemetry(metricsAction: meterProviderBuilder =>
{
    meterProviderBuilder.AddMeter(TournamentsMetrics.MeterName);
});
```
