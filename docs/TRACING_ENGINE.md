# Tracing engine

`TraceEngine` uses bounded BFS with max hops, max transactions, amount, direction, chain, and time-window controls. Historical demo windows anchor to the newest available record; timestamps are never shifted. Visited addresses and hashes prevent cycles and duplicate work. Provider exceptions and malformed transaction records are skipped rather than turned into fabricated transactions; the result includes provider-error counters and a `trace_status`/`trace_warning` pair so partial traces can be surfaced to investigators.
