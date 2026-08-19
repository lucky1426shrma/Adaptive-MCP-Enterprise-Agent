# Authentication Architecture Overview

## Purpose

This document describes how user and service authentication works
across the platform, for engineers onboarding onto services that need
to verify identity or call authenticated internal APIs.

## User Authentication

End users authenticate via OAuth 2.0 authorization code flow against
the identity provider. On successful login, the frontend receives a
short-lived access token (15 minute expiry) and a longer-lived refresh
token. Access tokens are JWTs signed with an asymmetric key; any
backend service can verify a token's signature and claims locally
without calling the identity provider on every request, using the
identity provider's published public key set.

## Service-to-Service Authentication

Internal services authenticate to one another using scoped bearer
tokens issued per service pair, not shared secrets. Each service has
its own credential for each downstream service it calls, following the
principle of least privilege — a compromised credential for one
service-to-service relationship does not grant access elsewhere. MCP
servers in the agent platform follow this same pattern: the FastAPI
backend holds a distinct bearer token for each MCP server it calls
(RAG, database, GitHub), and each MCP server validates that token
independently as its own trust boundary.

## Token Rotation

Service-to-service credentials are rotated on a 90 day schedule by
default, or immediately upon suspected compromise. Rotation is designed
to be zero-downtime: both the old and new credential are accepted for a
grace window while callers pick up the new value from their
configuration.

## Common Pitfalls

A recurring source of incidents is services that cache a downstream
token far longer than its actual expiry, leading to a wave of
authentication failures when the token is later rotated or revoked.
Services should always respect the token's stated expiry rather than
assuming a fixed cache lifetime.
