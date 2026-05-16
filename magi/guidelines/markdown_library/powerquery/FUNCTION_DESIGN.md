# Function Design

### Function Structure

```powerquery
// Basic
(inputValue as text) as text => Text.Upper(Text.Trim(inputValue))

// Multi-parameter
(startDate as date, endDate as date, status as text) as table =>
    let
        Source = Sql.Database("server", "database"),
        Filtered = Table.SelectRows(Source, each
            [OrderDate] >= startDate and
            [OrderDate] <= endDate and
            [Status] = status)
    in
        Filtered

// Optional parameter
(requiredParam as text, optional optionalParam as number) as number =>
    let
        DefaultValue = if optionalParam = null then 1 else optionalParam
    in
        Text.Length(requiredParam) * DefaultValue
```

### Function Documentation

Document functions using metadata for Power Query UI display:

```powerquery
let
    Function = (inputDate as date) as number => Date.DayOfYear(inputDate),
    Documentation = [
        Documentation.Name = "fn_GetDayOfYear",
        Documentation.Description = "Returns the day of year (1-366) for a given date.",
        Documentation.LongDescription = "Calculates the ordinal day within the calendar year. January 1 returns 1; December 31 returns 365 or 366.",
        Documentation.Category = "Date Functions",
        Documentation.Examples = {[
            Description = "Get day of year for a date",
            Code = "fn_GetDayOfYear(#date(2025, 3, 15))",
            Result = "74"
        ]}
    ]
in
    Value.ReplaceType(Function, Value.Type(Function) meta Documentation)
```

### Recursive Pagination

```powerquery
let
    fn_GetAllPages = (baseUrl as text) as table =>
        let
            GetPage = (url as text) as record =>
                let
                    Response = Json.Document(Web.Contents(url)),
                    Data     = Response[items],
                    NextLink = try Response[nextLink] otherwise null
                in
                    [Data = Data, Next = NextLink],

            AllPages = List.Generate(
                () => GetPage(baseUrl),
                each [Data] <> null,
                each GetPage([Next]),
                each [Data]
            ),
            Combined = Table.FromList(List.Combine(AllPages), Splitter.SplitByNothing())
        in
            Combined
in
    fn_GetAllPages
```

### Higher-Order Functions

```powerquery
let
    fn_CreateValidator = (minValue as number, maxValue as number) as function =>
        (value as number) as logical =>
            value >= minValue and value <= maxValue,
    ValidateAge        = fn_CreateValidator(0, 150),
    ValidatePercentage = fn_CreateValidator(0, 100)
in
    [ValidateAge = ValidateAge, ValidatePercentage = ValidatePercentage]
```

### Common Patterns

Safe type conversion:

```powerquery
(value as any, targetType as type) as any =>
    try
        if value = null then null
        else Value.As(value, targetType)
    otherwise null
```

Text cleaning:

```powerquery
(inputText as text) as text =>
    let
        Trimmed       = Text.Trim(inputText),
        NoExtraSpaces = Text.Combine(List.Select(Text.Split(Trimmed, " "), each _ <> ""), " "),
        Cleaned       = Text.Clean(NoExtraSpaces)
    in
        Cleaned
```

### Function Invocation

```powerquery
// Direct call
fn_CleanText("  messy   text  ")

// Apply to column
Table.TransformColumns(Source, {{"CustomerName", fn_CleanText, type text}})

// Apply to each row (when function needs multiple column values)
Table.AddColumn(Source, "FullAddress", each fn_BuildAddress([Street], [City], [State], [Zip]), type text)
```

---
[Back to Overview](./OVERVIEW.md)
