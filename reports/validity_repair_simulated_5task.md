# DataAgentBench Validity Repair Report

## Aggregate

| Model | Reports | RawAcc | TraceAcc | Process | ExecSafe | AnaSafe | TraceInt | AuditHit | Sources | Failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simulated | 5 | 0.112 | 0.112 | 0.625 | 1.000 | 0.940 | 1.000 | 0.0% | {'none': 5} | {'result': 5} |

## Per-task

| Model | Task | RawAcc | TraceAcc | Process | ExecSafe | AnaSafe | TraceInt | ExtractSrc | Audit | Failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simulated | DS_TASK_051 | 0.006 | 0.006 | 0.625 | 1.000 | 0.900 | 1.000 | none | ok | result |
| simulated | DS_TASK_060 | 0.047 | 0.047 | 0.750 | 1.000 | 1.000 | 1.000 | none | ok | result |
| simulated | DS_TASK_065 | 0.425 | 0.424 | 0.625 | 1.000 | 1.000 | 1.000 | none | ok | result |
| simulated | DS_TASK_070 | 0.078 | 0.078 | 0.562 | 1.000 | 1.000 | 1.000 | none | ok | result |
| simulated | DS_TASK_087 | 0.005 | 0.005 | 0.562 | 1.000 | 0.800 | 1.000 | none | ok | result |