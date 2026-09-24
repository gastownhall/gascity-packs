
Same-session is pack policy. Emit core shared drain with `do-work-item`, require
one executable item lane, and fail closed if core cannot prove dependency-safe
manifest order. Route item work through implementation target
{{implementation_target}} and use context path {{context_path}} for each
shared item when set.
