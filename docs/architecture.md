# Architecture and engineering roadmap

## Implemented boundaries

The analysis function is independent of SQLite and the HTTP transport. No component makes outbound requests. Browser assets use system fonts and no CDN; a same-origin content security policy restricts resources and scripts.

Canonical JSON gives records stable content IDs; the original payloads remain available for citation inspection. These hashes are reproducible references, not signed chain-of-custody attestations. Evidence sorting and deduplication are independent of upload order. Investigation fingerprints include the evidence snapshot and rule version.

The complete input batch is validated before persistence. SQLite transactions prevent partial writes, and primary keys make replay idempotent. WAL permits readers alongside a serialized writer; it does not provide distributed storage.

Rules separate observed thresholds from causal hypotheses. Confidence labels describe causal support, not the accuracy of input metrics. Missing evidence never establishes service health.

## Scaling path

The current release limits each request to 10,000 records and 5 MiB. Analysis and reporting execute in process. The list endpoint loads stored results and is intended for personal workloads. There is no measured distributed throughput or availability guarantee.

A larger deployment would require:

1. Durable ingestion and separate normalization/correlation workers. Acknowledge after durable acceptance; use tenant identity and content hashes for idempotency.
2. Evidence partitioning by project, environment, service, and event time. Explicit project/environment keys must precede multi-project correlation.
3. PostgreSQL for metadata and object storage for raw records. Paginate metadata and evidence separately; exclude blobs from summary queries.
4. Event-time windows, watermarks, late-event reanalysis, versioned rule runs, and historical evidence snapshots.
5. OIDC identity, tenant authorization, redaction, retention, encryption, audit trails, backpressure, retry budgets, and dead-letter handling.
6. Benchmarks for replay throughput, p95 investigation latency, queue lag, and peak memory. Set SLOs from measurement.

## GCP design mapping

These are future architecture mappings, not deployed infrastructure or existing connectors.

| Responsibility | GCP mapping | Current implementation |
| --- | --- | --- |
| Audit and application evidence | Cloud Logging export | JSON / NDJSON import |
| Metrics | Cloud Monitoring adapter | Normalized metric records |
| Durable ingestion | Pub/Sub | Synchronous HTTP request |
| API and workers | Cloud Run | Loopback Python server |
| Metadata | Cloud SQL for PostgreSQL | SQLite |
| Evidence archive | Cloud Storage | Raw records in SQLite |
| Identity and secrets | IAM / Secret Manager | Loopback isolation; no credentials |

No provisioning commands, SDK clients, credential discovery, or cloud resources are used. Deployment would require separate implementation, review, billing decisions, and capacity validation.

## Investigation limits

Change recognition matches method names containing update, replace, patch, or SetIamPolicy; it can miss other changes or include unrelated administrative operations. Permission detection uses text rules. Findings group signals by category within the submitted window, rather than sessionizing separate incidents. Dependency topology, traces, deployment diffs, recovery observations, and cross-service causality are future extensions.
