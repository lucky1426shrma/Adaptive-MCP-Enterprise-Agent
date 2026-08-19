# Infrastructure Runbook: Payment Service

## Service Overview

The payment-service handles checkout payment processing, calling out to
an external card-processing gateway for authorization and capture. It
runs as three replicas behind an internal load balancer, backed by a
dedicated PostgreSQL database for transaction records and a Redis
instance for idempotency key caching.

## Current Configuration

The outbound HTTP client used to reach the card gateway is configured
with a connection pool that autoscales between 40 and 150 connections
based on observed queue depth, with a target queue depth of under 5
pending requests. This autoscaling behavior was introduced as a
follow-up to the March 2026 timeout incident, replacing the previous
fixed pool size of 20 connections that caused that incident. Client-side
timeout for gateway calls is 5 seconds, with 3 retry attempts on
gateway-error-classified failures (see the Payment Retry and Failure
Handling Policy document).

## Monitoring

Key dashboards for this service track: checkout success rate, gateway
call latency (p50/p95/p99), connection pool utilization and queue
depth, and retry exhaustion rate. Connection pool saturation is alerted
on directly, independent of the downstream failure-rate alert, so
saturation is caught before it produces customer-facing failures.

## Deploy Cadence

The payment-service deploys on a standard weekly cadence via the CI/CD
pipeline, with additional ad-hoc deploys for urgent fixes. Configuration
changes (such as connection pool sizing) can be applied without a full
deploy via the service's dynamic configuration flags, which was how the
March 2026 incident was initially mitigated before the permanent
autoscaling fix was deployed the following week.

## On-Call Notes

If checkout failure rate spikes and gateway status pages show no
external incident, check connection pool queue depth and utilization
first — this has historically been the most common internal root cause,
as documented in the March 2026 incident postmortem.
