# Memory Management and Performance

### Span and Memory Usage

```csharp
public static int CountOccurrences(ReadOnlySpan<char> text, char target) {
    var count = 0;
    foreach (var c in text) {
        if (c == target) count++;
    }
    return count;
}

public static ReadOnlySpan<char> TrimQuotes(ReadOnlySpan<char> input) {
    if (input.Length >= 2 && input[0] == '"' && input[^1] == '"') return input[1..^1];
    return input;
}
```

### String.Create

```csharp
public string BuildPath(string root, string folder, string file) {
    var separator = Path.DirectorySeparatorChar;
    return string.Create(
        root.Length + folder.Length + file.Length + 2,
        (root, folder, file, separator),
        (span, state) => {
            var pos = 0;
            state.root.CopyTo(span);
            pos += state.root.Length;
            span[pos++] = state.separator;
            state.folder.CopyTo(span[pos..]);
            pos += state.folder.Length;
            span[pos++] = state.separator;
            state.file.CopyTo(span[pos..]);
        });
}
```

### ArrayPool Usage

```csharp
public async Task ProcessLargeDataAsync(Stream source, CancellationToken ct) {
    var buffer = ArrayPool<byte>.Shared.Rent(81920);
    try {
        int bytesRead;
        while ((bytesRead = await source.ReadAsync(buffer.AsMemory(), ct)) > 0) {
            ProcessChunk(buffer.AsSpan(0, bytesRead));
        }
    } finally {
        ArrayPool<byte>.Shared.Return(buffer);
    }
}
```

### Object Pooling

```csharp
services.AddSingleton<ObjectPoolProvider, DefaultObjectPoolProvider>();
services.AddSingleton(sp => sp.GetRequiredService<ObjectPoolProvider>().Create<StringBuilder>());

public sealed class ReportGenerator(ObjectPool<StringBuilder> builderPool) {
    public string Generate(ReportData data) {
        var builder = builderPool.Get();
        try {
            builder.AppendLine($"Report: {data.Title}");
            foreach (var line in data.Lines) builder.AppendLine(line);
            return builder.ToString();
        } finally {
            builder.Clear();
            builderPool.Return(builder);
        }
    }
}
```

### Disposal Patterns

```csharp
public sealed class ResourceHolder : IDisposable {
    private readonly Stream _stream;
    private bool _disposed;

    public ResourceHolder(Stream stream) => _stream = stream;

    public void Dispose() {
        if (_disposed) return;
        _stream.Dispose();
        _disposed = true;
    }
}
```

Prefer `using` declarations for scoped disposal:

```csharp
using var stream = File.OpenRead(path);
using var reader = new StreamReader(stream);
var content = await reader.ReadToEndAsync();
```

---
[Back to Overview](./OVERVIEW.md)
