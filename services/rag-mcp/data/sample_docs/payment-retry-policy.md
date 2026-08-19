# Payment Retry and Failure Handling Policy

## Overview

This document defines how the payment-service classifies and retries
failed payment attempts, so on-call engineers and downstream teams have
a shared reference for what "normal" failure behavior looks like versus
what indicates an active incident.

## Failure Categories

Payment failures are classified into three categories. Declines are
failures where the card issuer explicitly rejects the transaction
(insufficient funds, fraud hold, expired card); these are not retried
automatically since retrying would not change the outcome. Gateway
errors are failures where the payment-service could not complete the
round trip to the external card gateway at all, due to timeouts,
connection errors, or 5xx responses from the gateway; these ARE
retried, with exponential backoff starting at 2 seconds, up to 3
attempts. Validation errors are failures caught before ever reaching
the gateway, such as malformed card data; these fail immediately with
no retry.

## Baseline Failure Rate

Under normal operating conditions, the overall payment failure rate
(all categories combined) is typically between 1.5% and 2.5% of
attempts, driven mostly by ordinary card declines. A gateway-error rate
above roughly 3% sustained for more than a few minutes is considered
anomalous and should trigger investigation, since it suggests a
problem in the connection path to the gateway rather than routine
customer-side declines.

## Alerting Thresholds

Automated alerts fire when the gateway-error rate exceeds 3% over a
5-minute rolling window, or when retry exhaustion (payments that fail
all 3 retry attempts) exceeds 0.5% of total attempts. These thresholds
were informed by the March 2026 payment gateway timeout incident, where
the gateway-error rate spiked well above this threshold due to
connection pool exhaustion rather than gateway-side problems.

## Escalation

If gateway-error rate alerts fire, the on-call engineer should first
check connection pool saturation metrics for the payment-service's
outbound gateway client, since connection pool exhaustion has been the
most common root cause of gateway-error spikes historically, before
assuming the external gateway itself is degraded.
