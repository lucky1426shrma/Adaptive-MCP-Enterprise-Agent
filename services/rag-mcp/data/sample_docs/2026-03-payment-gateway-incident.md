# March 2026 Payment Gateway Timeout Incident

## Summary

On March 14, 2026, the payment service experienced an elevated failure
rate for approximately 90 minutes between 14:10 and 15:40 UTC. Roughly
6% of checkout attempts during the window failed with a gateway timeout
error. The root cause was identified as an undersized HTTP connection
pool between the payment-service and the external card-processing
gateway, which had not been resized after a traffic increase from the
February marketing campaign.

## Timeline

At 14:10 UTC, alerting fired on elevated 504 responses from the
payment-service checkout endpoint. On-call engineers confirmed the
errors originated from the connection pool used to reach the external
gateway, not from the gateway itself. Gateway-side status pages showed
no incident. At 14:45 UTC, the team applied a temporary mitigation by
increasing the connection pool size from 20 to 100 connections via a
configuration flag, without a code deploy. Error rates returned to
baseline by 15:40 UTC.

## Root Cause

The payment-service's outbound connection pool to the card gateway was
configured with a fixed maximum of 20 concurrent connections. This
limit was set during initial service rollout and was never revisited.
Checkout volume had grown roughly 3x since then, and during periods of
concurrent load spikes, requests queued waiting for a pool connection
and eventually timed out at the client-side 5 second timeout, even
though the gateway itself was healthy and responding normally to the
requests it did receive.

## Fix

The immediate mitigation (raising the pool size to 100) was made
permanent in the service's configuration. A follow-up change added
autoscaling of the connection pool based on observed queue depth, along
with a dedicated alert on connection pool saturation so this class of
issue is caught before it causes customer-facing failures.

## Related Systems

This incident affected only the payment-service's outbound gateway
calls. It did not involve the authentication service, the retry queue,
or the database layer. See the "Payment Retry and Failure Handling
Policy" document for how failed payments are retried, and the
"Infrastructure Runbook: Payment Service" for current operational
configuration.
